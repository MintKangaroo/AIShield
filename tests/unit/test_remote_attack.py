"""End-to-end contract for the authorized remote black-box attack.

The point of this feature is attacking a model we do not own the weights of, over
the network, using only its responses. So one test stands up a real HTTP server
serving a model's scores and attacks it query-only. The rest pin down the
authorization gates that keep this from being a tool for hitting arbitrary hosts.
"""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.attacks.contracts import RemoteAttackConfig
from aishield.attacks.remote import RemoteEndpoint, RemoteImageClassifier
from aishield.core.config import Settings
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.errors import RegistryAuthorizationError, RegistryError
from aishield.registry.service import RegistryService

CLASSES = 4


def _quadrant_scores(images: torch.Tensor) -> torch.Tensor:
    return (
        torch.stack(
            [
                images[:, :, :4, :4].mean((1, 2, 3)),
                images[:, :, :4, 4:].mean((1, 2, 3)),
                images[:, :, 4:, :4].mean((1, 2, 3)),
                images[:, :, 4:, 4:].mean((1, 2, 3)),
            ],
            dim=1,
        )
        * 5.0
    )


class _ModelHandler(BaseHTTPRequestHandler):
    """Serves class scores for a batch of images — a stand-in for a deployed model."""

    query_count = 0

    def log_message(self, *args: Any) -> None:  # noqa: D401 - silence test server logs
        return

    def do_POST(self) -> None:  # noqa: N802 - required handler name
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        images = torch.tensor(payload["images"], dtype=torch.float32)
        type(self).query_count += int(images.shape[0])
        scores = _quadrant_scores(images).tolist()
        body = json.dumps({"scores": scores}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def served_model() -> Iterator[str]:
    _ModelHandler.query_count = 0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host!s}:{port}/score"
    finally:
        server.shutdown()
        server.server_close()


class QuadrantDatasetAdapter(MNISTAdapter):
    """A 4-class 8x8 dataset whose label is the brightest quadrant."""

    num_classes = CLASSES  # type: ignore[misc]  # test fixture overrides the base default

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "quadrant.fixture").write_bytes(b"quadrant")
        generator = torch.Generator().manual_seed(3)
        images = torch.rand(16, 1, 8, 8, generator=generator) * 0.3
        labels = torch.randint(0, CLASSES, (16,), generator=generator)
        for index, label in enumerate(labels):
            row = 0 if label < 2 else 4
            column = 0 if label % 2 == 0 else 4
            images[index, :, row : row + 4, column : column + 4] += 0.35
        return TensorDataset(images.clamp(0, 1), labels)


def _service(tmp_path: Path, allowlist: list[str] | None = None) -> RegistryService:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
        attack_targets_allowlist=allowlist or [],
    )
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: QuadrantDatasetAdapter()})


def _load_dataset(service: RegistryService) -> str:
    record = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    return str(record.id)


def _config() -> RemoteAttackConfig:
    return RemoteAttackConfig(epsilon=0.4, max_queries=300, seed=7, batch_size=16, max_samples=16)


# --- the real thing: attack a model over the network --------------------------


def test_attacks_a_real_served_model_over_http(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])
    dataset_id = _load_dataset(service)

    record = service.run_remote_attack(
        UUID(dataset_id),
        RemoteEndpoint(url=served_model, num_classes=CLASSES),
        config=_config(),
        authorized=True,
    )

    # The model was queried over HTTP, never introspected.
    assert _ModelHandler.query_count > 0
    assert record.metrics.total_queries == _ModelHandler.query_count
    assert record.target_host == "127.0.0.1"
    assert record.metrics.maximum_observed_linf <= 0.4 + 1e-6
    # A 0.4 bound overcomes the 0.35 signal, so the attack should land.
    assert record.metrics.attack_success_rate > 0.0
    assert record.metrics.robust_accuracy < record.metrics.clean_accuracy
    assert record.authorized is True


def test_the_run_is_recorded_and_listed_through_the_api(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])
    dataset_id = _load_dataset(service)

    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(
            "/api/v1/registry/remote-attacks",
            json={
                "endpoint_url": served_model,
                "num_classes": CLASSES,
                "dataset_id": dataset_id,
                "authorized": True,
                "epsilon": 0.4,
                "max_queries": 300,
                "batch_size": 16,
                "max_samples": 16,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["target_host"] == "127.0.0.1"
        listed = client.get("/api/v1/registry/remote-attacks")

    assert listed.status_code == 200
    assert len(listed.json()) == 1


# --- authorization gates ------------------------------------------------------


def test_refused_without_the_authorized_confirmation(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])
    dataset_id = _load_dataset(service)

    with pytest.raises(RegistryAuthorizationError, match="authorized to test"):
        service.run_remote_attack(
            UUID(dataset_id),
            RemoteEndpoint(url=served_model, num_classes=CLASSES),
            config=_config(),
            authorized=False,
        )


def test_refused_when_the_allowlist_is_empty(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=[])
    dataset_id = _load_dataset(service)

    with pytest.raises(RegistryAuthorizationError, match="no attack targets are allowlisted"):
        service.run_remote_attack(
            UUID(dataset_id),
            RemoteEndpoint(url=served_model, num_classes=CLASSES),
            config=_config(),
            authorized=True,
        )


def test_refused_when_the_host_is_not_allowlisted(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=["only.example.com"])
    dataset_id = _load_dataset(service)

    with pytest.raises(RegistryAuthorizationError, match="not in the configured allowlist"):
        service.run_remote_attack(
            UUID(dataset_id),
            RemoteEndpoint(url=served_model, num_classes=CLASSES),
            config=_config(),
            authorized=True,
        )


def test_query_ceiling_is_enforced(tmp_path: Path, served_model: str) -> None:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
        attack_targets_allowlist=["127.0.0.1"],
        remote_attack_max_queries=100,
    )
    service = RegistryService(
        settings, dataset_adapters={DatasetName.MNIST: QuadrantDatasetAdapter()}
    )
    dataset_id = _load_dataset(service)

    with pytest.raises(RegistryError, match="exceeds the configured ceiling"):
        service.run_remote_attack(
            UUID(dataset_id),
            RemoteEndpoint(url=served_model, num_classes=CLASSES),
            config=RemoteAttackConfig(
                epsilon=0.4, max_queries=300, seed=7, batch_size=16, max_samples=16
            ),
            authorized=True,
        )


def test_api_returns_403_for_an_unauthorized_target(tmp_path: Path, served_model: str) -> None:
    service = _service(tmp_path, allowlist=["only.example.com"])
    dataset_id = _load_dataset(service)

    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(
            "/api/v1/registry/remote-attacks",
            json={
                "endpoint_url": served_model,
                "num_classes": CLASSES,
                "dataset_id": dataset_id,
                "authorized": True,
                "epsilon": 0.4,
                "max_queries": 300,
                "batch_size": 16,
                "max_samples": 16,
            },
        )

    assert response.status_code == 403
    assert "allowlist" in response.json()["detail"]


# --- transport guards ---------------------------------------------------------


def test_a_non_http_scheme_is_refused() -> None:
    with pytest.raises(RegistryError, match="http"):
        RemoteImageClassifier(RemoteEndpoint(url="file:///etc/passwd", num_classes=CLASSES))


def test_a_malformed_response_shape_is_rejected(tmp_path: Path) -> None:
    class BadHandler(_ModelHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            self.rfile.read(length)
            body = json.dumps({"scores": [[0.1, 0.2]]}).encode("utf-8")  # wrong class count
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), BadHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        classifier = RemoteImageClassifier(
            RemoteEndpoint(url=f"http://{host!s}:{port}/score", num_classes=CLASSES)
        )
        with pytest.raises(RegistryError, match="num_classes"):
            classifier.score(torch.rand(1, 1, 8, 8))
    finally:
        server.shutdown()
        server.server_close()
