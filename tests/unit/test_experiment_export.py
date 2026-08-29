"""Round-trip contract for the portable experiment envelope."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.core.config import Settings
from aishield.defenses.contracts import DefenseConfig, DefenseKind
from aishield.evaluation.contracts import BaselineConfig
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.errors import RegistryError, RegistryNotFoundError
from aishield.registry.experiment import build_experiment_result
from aishield.registry.service import RegistryService
from aishield.schemas.experiment import ExperimentResult, RunStatus


class ExportFixtureAdapter(MNISTAdapter):
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "export.fixture").write_bytes(b"export-dataset")
        return TensorDataset(torch.rand(6, 1, 28, 28), torch.tensor([0, 1, 2, 3, 4, 5]))


@pytest.fixture
def service(tmp_path: Path) -> RegistryService:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
    )
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: ExportFixtureAdapter()})


def _prepare(service: RegistryService) -> tuple[UUID, UUID, UUID]:
    dataset = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    model = service.load_small_cnn(dataset.id, seed=1729, checkpoint=None)
    baseline = service.run_clean_baseline(
        model.id,
        dataset.id,
        config=BaselineConfig(seed=1729, batch_size=2, max_samples=4, warmup_batches=0),
    )
    return baseline.id, model.id, dataset.id


def _attack(service: RegistryService, model_id: UUID, dataset_id: UUID) -> None:
    service.run_attack(
        model_id,
        dataset_id,
        config=AttackConfig(
            algorithm=AttackAlgorithm.FGSM,
            epsilon=0.1,
            step_size=0.1,
            iterations=1,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )


def test_export_produces_a_schema_valid_envelope(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    _attack(service, model_id, dataset_id)

    envelope = service.export_experiment(baseline_id)

    assert envelope.schema_version == "1.0"
    assert envelope.experiment.id == baseline_id
    assert envelope.experiment.status is RunStatus.SUCCEEDED
    assert envelope.dataset.id == dataset_id
    assert envelope.model.id == model_id
    assert envelope.baseline is not None
    assert len(envelope.attack_runs) == 1
    assert envelope.robustness_score is not None
    # Re-validating the serialized form proves the envelope is genuinely portable.
    ExperimentResult.model_validate(envelope.model_dump(mode="json"))


def test_export_keeps_raw_metrics_behind_the_score(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    _attack(service, model_id, dataset_id)

    envelope = service.export_experiment(baseline_id)

    assert envelope.robustness_score is not None
    metric_ids = {metric.id for metric in envelope.metrics}
    assert set(envelope.robustness_score.raw_metric_ids) <= metric_ids
    assert {metric.name for metric in envelope.metrics} >= {
        "clean_accuracy",
        "mean_loss",
        "robust_accuracy",
        "attack_success_rate",
    }


def test_export_links_the_confusion_matrix_artifact(service: RegistryService) -> None:
    baseline_id, _, _ = _prepare(service)

    envelope = service.export_experiment(baseline_id)

    assert envelope.baseline is not None
    matrix_id = envelope.baseline.confusion_matrix_artifact_id
    assert matrix_id is not None
    assert matrix_id in {artifact.id for artifact in envelope.artifacts}


def test_export_without_attacks_omits_the_score(service: RegistryService) -> None:
    baseline_id, _, _ = _prepare(service)

    envelope = service.export_experiment(baseline_id)

    assert envelope.attack_runs == []
    assert envelope.robustness_score is None


def test_export_includes_defense_before_and_after(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    service.run_defense(
        model_id,
        dataset_id,
        defense=DefenseConfig(kind=DefenseKind.BIT_DEPTH, bit_depth=4),
        attack=AttackConfig(
            algorithm=AttackAlgorithm.FGSM,
            epsilon=0.1,
            step_size=0.1,
            iterations=1,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )

    envelope = service.export_experiment(baseline_id)

    assert len(envelope.defense_runs) == 1
    defense = envelope.defense_runs[0]
    assert defense.before is not None
    assert defense.after is not None
    assert defense.adaptive_attack_evaluated is True


def test_identifiers_are_stable_across_repeated_exports(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    _attack(service, model_id, dataset_id)

    first = service.export_experiment(baseline_id)
    second = service.export_experiment(baseline_id)

    assert first.model.artifact.id == second.model.artifact.id
    assert [metric.id for metric in first.metrics] == [metric.id for metric in second.metrics]


def test_export_rejects_a_run_from_a_different_target(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    baseline = service.get_baseline(baseline_id)
    dataset = service.get_dataset_bundle(dataset_id).record
    model = service.get_model_bundle(model_id).record
    other = service.load_small_cnn(dataset_id, seed=99, checkpoint=None)
    service.run_attack(
        other.id,
        dataset_id,
        config=AttackConfig(
            algorithm=AttackAlgorithm.FGSM,
            epsilon=0.1,
            step_size=0.1,
            iterations=1,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )
    foreign = service.list_attacks()[0]

    with pytest.raises(RegistryError, match="different model or dataset"):
        build_experiment_result(baseline, dataset, model, attacks=[foreign])


def test_export_of_an_unknown_baseline_is_not_found(service: RegistryService) -> None:
    with pytest.raises(RegistryNotFoundError):
        service.export_experiment(uuid4())


def test_import_retains_and_journals_the_envelope(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    _attack(service, model_id, dataset_id)
    envelope = service.export_experiment(baseline_id)

    imported = service.import_experiment(envelope)

    assert imported == envelope
    assert service.get_experiment(envelope.experiment.id) == envelope
    assert [item.experiment.id for item in service.list_experiments()] == [envelope.experiment.id]
    assert any(entry["kind"] == "experiment" for entry in service.read_journal())


def test_getting_an_unimported_experiment_is_not_found(service: RegistryService) -> None:
    with pytest.raises(RegistryNotFoundError):
        service.get_experiment(uuid4())


def test_export_and_import_round_trip_over_http(service: RegistryService) -> None:
    baseline_id, model_id, dataset_id = _prepare(service)
    _attack(service, model_id, dataset_id)

    with TestClient(create_app(service.settings, service)) as client:
        exported = client.get(f"/api/v1/registry/baselines/{baseline_id}/experiment")
        assert exported.status_code == 200

        imported = client.post("/api/v1/registry/experiments", json=exported.json())
        assert imported.status_code == 201
        assert imported.json() == exported.json()

        listed = client.get("/api/v1/registry/experiments")
        assert listed.status_code == 200
        assert len(listed.json()) == 1

        experiment_id = exported.json()["experiment"]["id"]
        fetched = client.get(f"/api/v1/registry/experiments/{experiment_id}")
        assert fetched.status_code == 200
        assert fetched.json()["experiment"]["id"] == experiment_id


def test_importing_a_malformed_envelope_is_rejected(service: RegistryService) -> None:
    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(
            "/api/v1/registry/experiments",
            json={"schema_version": "1.0", "experiment": {"id": str(uuid4())}},
        )

    assert response.status_code == 422


def test_exporting_an_unknown_baseline_over_http_is_404(service: RegistryService) -> None:
    with TestClient(create_app(service.settings, service)) as client:
        response = client.get(f"/api/v1/registry/baselines/{uuid4()}/experiment")

    assert response.status_code == 404
