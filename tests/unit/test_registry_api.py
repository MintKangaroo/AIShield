from pathlib import Path
from typing import Any
from uuid import uuid4

import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.core.config import Settings
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.service import RegistryService


class ApiFixtureMNISTAdapter(MNISTAdapter):
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "api.fixture").write_bytes(b"api-dataset")
        return TensorDataset(torch.zeros(4, 1, 28, 28), torch.tensor([0, 1, 2, 3]))


def test_registry_api_loads_lists_and_evaluates(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
    )
    registry = RegistryService(
        settings,
        dataset_adapters={DatasetName.MNIST: ApiFixtureMNISTAdapter()},
    )

    with TestClient(create_app(settings, registry)) as client:
        dataset_response = client.post(
            "/api/v1/registry/datasets",
            json={"name": "mnist", "split": "test", "download": False},
        )
        assert dataset_response.status_code == 201
        dataset = dataset_response.json()

        model_response = client.post(
            "/api/v1/registry/models/small-cnn",
            json={"dataset_id": dataset["id"], "seed": 1729},
        )
        assert model_response.status_code == 201
        model = model_response.json()

        evaluation_response = client.post(
            "/api/v1/registry/evaluations",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "seed": 1729,
                "batch_size": 2,
                "max_samples": 3,
            },
        )

        assert evaluation_response.status_code == 200
        assert evaluation_response.json()["evaluated_samples"] == 3
        assert evaluation_response.json()["robust_accuracy"] is None
        assert len(client.get("/api/v1/registry/datasets").json()) == 1
        assert len(client.get("/api/v1/registry/models").json()) == 1

        baseline_response = client.post(
            "/api/v1/registry/baselines",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "seed": 1729,
                "batch_size": 2,
                "max_samples": 3,
                "warmup_batches": 1,
            },
        )
        assert baseline_response.status_code == 201
        baseline = baseline_response.json()
        assert baseline["metrics"]["evaluated_samples"] == 3
        assert baseline["metrics"]["robust_accuracy"] is None
        assert len(baseline["metrics"]["confusion_matrix"]) == 10
        assert len(baseline["metrics"]["per_class"]) == 10
        assert len(baseline["artifacts"]) == 2
        image_artifact = next(
            artifact for artifact in baseline["artifacts"] if artifact["kind"] == "confusion_matrix"
        )
        artifact_response = client.get(
            f"/api/v1/registry/baselines/{baseline['id']}/artifacts/{image_artifact['id']}"
        )
        assert artifact_response.status_code == 200
        assert artifact_response.headers["content-type"] == "image/png"
        assert artifact_response.content.startswith(b"\x89PNG\r\n\x1a\n")
        assert len(client.get("/api/v1/registry/baselines").json()) == 1
        assert (
            client.get(f"/api/v1/registry/baselines/{baseline['id']}").json()["id"]
            == baseline["id"]
        )

        verification_response = client.post(f"/api/v1/registry/baselines/{baseline['id']}/verify")
        assert verification_response.status_code == 200
        assert verification_response.json()["reproducible"] is True
        assert len(client.get("/api/v1/registry/baselines").json()) == 2

        attack_response = client.post(
            "/api/v1/registry/attacks",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "fgsm",
                "epsilon": 0.1,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert attack_response.status_code == 201
        attack = attack_response.json()
        assert attack["metrics"]["evaluated_samples"] == 3
        assert 0.0 <= attack["metrics"]["robust_accuracy"] <= 1.0
        assert attack["metrics"]["maximum_observed_linf"] <= 0.1 + 1e-6
        assert len(client.get("/api/v1/registry/attacks").json()) == 1
        assert client.get(f"/api/v1/registry/attacks/{attack['id']}").json()["id"] == attack["id"]

        bim_response = client.post(
            "/api/v1/registry/attacks",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "bim",
                "epsilon": 0.1,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert bim_response.status_code == 201
        bim = bim_response.json()
        assert bim["config"]["algorithm"] == "bim"
        assert bim["config"]["random_start"] is False
        assert bim["config"]["iterations"] == 10
        assert len(client.get("/api/v1/registry/attacks").json()) == 2

        deepfool_response = client.post(
            "/api/v1/registry/attacks",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "deepfool",
                "epsilon": 0.5,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert deepfool_response.status_code == 201
        deepfool = deepfool_response.json()
        assert deepfool["config"]["norm"] == "l2"
        assert deepfool["config"]["iterations"] == 20
        assert deepfool["metrics"]["maximum_observed_l2"] <= 0.5 + 1e-6
        assert len(client.get("/api/v1/registry/attacks").json()) == 3

        cw_response = client.post(
            "/api/v1/registry/attacks",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "cw",
                "epsilon": 0.5,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert cw_response.status_code == 201
        cw = cw_response.json()
        assert cw["config"]["norm"] == "l2"
        assert cw["config"]["iterations"] == 50
        assert cw["config"]["random_start"] is False
        assert cw["metrics"]["maximum_observed_l2"] <= 0.5 + 1e-6
        assert len(client.get("/api/v1/registry/attacks").json()) == 4

        autoattack_response = client.post(
            "/api/v1/registry/attacks",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "autoattack",
                "epsilon": 0.1,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert autoattack_response.status_code == 201
        autoattack = autoattack_response.json()
        assert autoattack["config"]["norm"] == "linf"
        assert autoattack["config"]["random_start"] is False
        assert autoattack["metrics"]["maximum_observed_linf"] <= 0.1 + 1e-6
        assert len(client.get("/api/v1/registry/attacks").json()) == 5

        curve_response = client.post(
            "/api/v1/registry/attack-curves",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "pgd",
                "epsilons": [0.02, 0.05],
                "iterations": 1,
                "restarts": 2,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert curve_response.status_code == 201
        curve = curve_response.json()
        assert [point["config"]["epsilon"] for point in curve] == [0.02, 0.02, 0.05, 0.05]

        score_response = client.post(
            "/api/v1/registry/robustness-score",
            json={"attack_run_ids": [attack["id"]]},
        )
        assert score_response.status_code == 201
        score = score_response.json()
        assert score["formula_version"] == "mean-robust-accuracy-v1"
        assert score["attack_run_ids"] == [attack["id"]]

        defense_response = client.post(
            "/api/v1/registry/defenses",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "defense": "bit_depth",
                "bit_depth": 2,
                "attack_algorithm": "pgd",
                "epsilon": 0.1,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert defense_response.status_code == 201
        defense = defense_response.json()
        assert defense["defense"]["kind"] == "bit_depth"
        assert defense["metrics"]["evaluated_samples"] == 3
        assert len(client.get("/api/v1/registry/defenses").json()) == 1

        transfer_response = client.post(
            "/api/v1/registry/defenses/transfer",
            json={
                "surrogate_model_version_id": model["id"],
                "target_model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "algorithm": "pgd",
                "iterations": 1,
                "batch_size": 2,
                "max_samples": 3,
                "seed": 1729,
            },
        )
        assert transfer_response.status_code == 201
        transfer = transfer_response.json()
        assert transfer["metrics"]["evaluated_samples"] == 3
        assert len(client.get("/api/v1/registry/defenses/transfer").json()) == 1

        training_response = client.post(
            "/api/v1/registry/training",
            json={
                "model_version_id": model["id"],
                "dataset_id": dataset["id"],
                "strategy": "trades",
                "epochs": 1,
                "batch_size": 2,
                "max_samples": 3,
                "epsilon": 0.1,
                "step_size": 0.05,
                "attack_iterations": 1,
                "learning_rate": 0.001,
                "trades_beta": 2.0,
                "seed": 1729,
            },
        )
        assert training_response.status_code == 201
        training = training_response.json()
        assert training["config"]["strategy"] == "trades"
        assert training["metrics"]["training_samples"] == 3
        assert len(training["model_state_sha256"]) == 64
        assert len(client.get("/api/v1/registry/training").json()) == 1


def test_registry_api_enforces_download_policy_and_not_found(tmp_path: Path) -> None:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
    )
    registry = RegistryService(
        settings,
        dataset_adapters={DatasetName.MNIST: ApiFixtureMNISTAdapter()},
    )

    with TestClient(create_app(settings, registry)) as client:
        denied = client.post(
            "/api/v1/registry/datasets",
            json={"name": "mnist", "split": "test", "download": True},
        )
        missing = client.post(
            "/api/v1/registry/models/small-cnn",
            json={"dataset_id": str(uuid4()), "seed": 1},
        )
        pretrained = client.post(
            "/api/v1/registry/models/torchvision",
            json={"architecture": "resnet18", "weights": "DEFAULT", "seed": 1},
        )
        missing_baseline = client.get(f"/api/v1/registry/baselines/{uuid4()}")
        missing_artifact = client.get(f"/api/v1/registry/baselines/{uuid4()}/artifacts/{uuid4()}")
        missing_attack = client.get(f"/api/v1/registry/attacks/{uuid4()}")

    assert denied.status_code == 400
    assert "not approved" in denied.json()["detail"]
    assert missing.status_code == 404
    assert pretrained.status_code == 400
    assert missing_baseline.status_code == 404
    assert missing_artifact.status_code == 404
    assert missing_attack.status_code == 404
