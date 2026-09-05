"""Contract for artifact garbage collection.

The sweep must reclaim orphaned files while never removing anything a retained
baseline or model still references, and a dry run must report without deleting.
"""

from pathlib import Path
from typing import Any

import torch
from fastapi.testclient import TestClient
from pydantic import SecretStr
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.core.config import Settings
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.gc import collect_orphan_artifacts, uri_to_path
from aishield.registry.service import RegistryService


class GcFixtureAdapter(MNISTAdapter):
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "gc.fixture").write_bytes(b"gc-dataset")
        return TensorDataset(torch.zeros(4, 1, 28, 28), torch.tensor([0, 1, 2, 3]))


def _service(tmp_path: Path) -> RegistryService:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "artifacts" / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
    )
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: GcFixtureAdapter()})


def _seed_baseline(service: RegistryService) -> None:
    from aishield.evaluation.contracts import BaselineConfig

    dataset = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    model = service.load_small_cnn(dataset.id, seed=1729, checkpoint=None)
    service.run_clean_baseline(
        model.id,
        dataset.id,
        config=BaselineConfig(seed=1729, batch_size=2, max_samples=4, warmup_batches=0),
    )


# --- pure core ---------------------------------------------------------------


def test_orphans_are_removed_and_referenced_files_kept(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    (root / "models").mkdir(parents=True)
    (root / "baselines" / "kept").mkdir(parents=True)
    (root / "baselines" / "orphan").mkdir(parents=True)
    kept_ckpt = root / "models" / "kept.pt"
    kept_ckpt.write_bytes(b"k" * 10)
    (root / "models" / "orphan.pt").write_bytes(b"o" * 20)
    (root / "models" / ".half.tmp").write_bytes(b"t" * 5)
    kept_report = root / "baselines" / "kept" / "report.json"
    kept_report.write_bytes(b"{}")
    (root / "baselines" / "orphan" / "report.json").write_bytes(b"{}")

    report = collect_orphan_artifacts(root, {kept_ckpt, kept_report})

    assert kept_ckpt.exists()
    assert (root / "baselines" / "kept").exists()
    assert not (root / "models" / "orphan.pt").exists()
    assert not (root / "models" / ".half.tmp").exists()
    assert not (root / "baselines" / "orphan").exists()
    assert report.removed_count == 3
    assert report.reclaimed_bytes == 27


def test_dry_run_reports_without_deleting(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    (root / "models").mkdir(parents=True)
    orphan = root / "models" / "orphan.pt"
    orphan.write_bytes(b"o" * 42)

    report = collect_orphan_artifacts(root, set(), dry_run=True)

    assert orphan.exists()
    assert report.dry_run is True
    assert report.removed_count == 1
    assert report.reclaimed_bytes == 42


def test_a_symlinked_checkpoint_is_skipped_not_followed(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    (root / "models").mkdir(parents=True)
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"secret")
    link = root / "models" / "link.pt"
    link.symlink_to(outside)

    report = collect_orphan_artifacts(root, set())

    assert outside.exists()  # never followed/deleted
    assert str(link) in report.skipped


def test_uri_to_path_ignores_non_local_uris() -> None:
    assert uri_to_path("https://example.com/model.pt") is None
    assert uri_to_path("file:///var/models/model.pt") == Path("/var/models/model.pt")


def test_empty_root_is_a_no_op(tmp_path: Path) -> None:
    report = collect_orphan_artifacts(tmp_path / "artifacts", set())

    assert report.removed_count == 0


# --- service + API -----------------------------------------------------------


def test_gc_keeps_a_retained_baselines_artifacts(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seed_baseline(service)
    baseline = service.list_baselines()[0]

    report = service.collect_artifact_garbage()

    # Nothing retained should be collected.
    assert report.removed_count == 0
    for artifact in baseline.artifacts:
        path = uri_to_path(artifact.uri)
        assert path is not None and path.exists()


def test_gc_removes_a_checkpoint_for_an_unreferenced_model(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seed_baseline(service)
    # A stray checkpoint no model record points at.
    stray = tmp_path / "artifacts" / "models" / "stray.pt"
    stray.write_bytes(b"stray" * 100)

    report = service.collect_artifact_garbage()

    assert not stray.exists()
    assert str(stray) in report.removed_files


def test_gc_endpoint_reports_a_summary(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _seed_baseline(service)
    (tmp_path / "artifacts" / "models" / "orphan.pt").write_bytes(b"x" * 64)

    with TestClient(create_app(service.settings, service)) as client:
        preview = client.post("/api/v1/registry/artifacts/gc?dry_run=true")
        assert preview.status_code == 200
        assert preview.json()["dry_run"] is True
        assert preview.json()["reclaimed_bytes"] == 64

        swept = client.post("/api/v1/registry/artifacts/gc")
        assert swept.status_code == 200
        assert swept.json()["reclaimed_bytes"] == 64

    assert not (tmp_path / "artifacts" / "models" / "orphan.pt").exists()


def test_gc_requires_the_api_key_when_configured(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "artifacts" / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
        api_key=SecretStr("a-key-long-enough"),
    )
    service = RegistryService(settings, dataset_adapters={DatasetName.MNIST: GcFixtureAdapter()})

    with TestClient(create_app(settings, service)) as client:
        assert client.post("/api/v1/registry/artifacts/gc").status_code == 401
