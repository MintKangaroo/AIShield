"""Restart-recovery contract for journal replay."""

from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.core.config import Settings
from aishield.evaluation.contracts import BaselineConfig
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.journal import RegistryJournal
from aishield.registry.replay import group_entries
from aishield.registry.service import RegistryService


class ReplayFixtureAdapter(MNISTAdapter):
    """A deterministic split so a reload reproduces the same manifest hash."""

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "replay.fixture").write_bytes(b"replay-dataset")
        generator = torch.Generator().manual_seed(7)
        return TensorDataset(
            torch.rand(6, 1, 28, 28, generator=generator), torch.tensor([0, 1, 2, 3, 4, 5])
        )


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "artifacts" / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
        replay_journal_on_start=False,
    )


def _service(settings: Settings) -> RegistryService:
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: ReplayFixtureAdapter()})


def _seed_runs(service: RegistryService) -> tuple[str, str, str]:
    dataset = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    model = service.load_small_cnn(dataset.id, seed=1729, checkpoint=None)
    baseline = service.run_clean_baseline(
        model.id,
        dataset.id,
        config=BaselineConfig(seed=1729, batch_size=2, max_samples=4, warmup_batches=0),
    )
    service.run_attack(
        model.id,
        dataset.id,
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
    return str(dataset.id), str(model.id), str(baseline.id)


def test_group_entries_keeps_order_and_drops_unknown_kinds() -> None:
    grouped = group_entries(
        [
            {"kind": "dataset", "record": {"id": "a"}},
            {"kind": "nonsense", "record": {"id": "b"}},
            {"kind": "dataset", "record": {"id": "c"}},
            {"kind": "attack", "record": "not a dict"},
        ]
    )

    assert [record["id"] for record in grouped["dataset"]] == ["a", "c"]
    assert grouped["attack"] == []
    assert "nonsense" not in grouped


def test_replay_restores_runs_and_handles_in_a_fresh_process(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original = _service(settings)
    dataset_id, model_id, baseline_id = _seed_runs(original)

    # A fresh service stands in for a restarted process: memory is empty, disk is not.
    restarted = _service(settings)
    assert restarted.list_baselines() == []

    summary = restarted.replay_journal()

    assert summary.datasets_restored == 1
    assert summary.models_restored == 1
    assert summary.baselines_restored == 1
    assert summary.attacks_restored == 1
    assert summary.skipped == ()
    assert str(restarted.get_baseline(UUID(baseline_id)).id) == baseline_id
    assert str(restarted.get_dataset_bundle(UUID(dataset_id)).record.id) == dataset_id
    assert str(restarted.get_model_bundle(UUID(model_id)).record.id) == model_id


def test_replayed_state_supports_a_new_run(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original = _service(settings)
    dataset_id, model_id, _ = _seed_runs(original)

    restarted = _service(settings)
    restarted.replay_journal()

    record = restarted.run_attack(
        UUID(model_id),
        UUID(dataset_id),
        config=AttackConfig(
            algorithm=AttackAlgorithm.PGD,
            epsilon=0.1,
            step_size=0.025,
            iterations=2,
            random_start=True,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )

    assert record.metrics.evaluated_samples == 4


def test_replay_restores_a_trained_checkpoint(tmp_path: Path) -> None:
    """Trained checkpoints are not named after the state hash, so the record's URI wins."""

    settings = _settings(tmp_path)
    original = _service(settings)
    dataset_id, model_id, _ = _seed_runs(original)
    from aishield.training.contracts import TrainingConfig, TrainingStrategy

    trained, _, _ = original.train_model(
        UUID(model_id),
        UUID(dataset_id),
        config=TrainingConfig(
            strategy=TrainingStrategy.ADVERSARIAL,
            seed=1729,
            epochs=1,
            batch_size=2,
            max_samples=4,
            epsilon=0.1,
            step_size=0.05,
            attack_iterations=1,
            learning_rate=1e-3,
            trades_beta=6.0,
        ),
    )
    assert "trained-" in trained.artifact.uri

    restarted = _service(settings)
    summary = restarted.replay_journal()

    assert summary.skipped == ()
    assert summary.models_restored == 2
    restored = restarted.get_model_bundle(trained.id).record
    # The recorded identity survives: a trained model must not come back as a
    # freshly initialised SmallCNN with a different source and version.
    assert restored.id == trained.id
    assert restored.source is trained.source
    assert restored.version == trained.version
    assert restored.state_dict_sha256 == trained.state_dict_sha256


def test_replay_skips_a_model_whose_checkpoint_is_gone(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original = _service(settings)
    _seed_runs(original)
    for checkpoint in (settings.artifact_root / "models").glob("*.pt"):
        checkpoint.unlink()

    summary = _service(settings).replay_journal()

    assert summary.models_restored == 0
    assert any("checkpoint unavailable" in reason for reason in summary.skipped)
    # Run evidence survives even when the runnable handle cannot be rebuilt.
    assert summary.baselines_restored == 1


def test_replay_skips_a_dataset_whose_content_changed(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    original = _service(settings)
    _seed_runs(original)
    # An extra file the adapter does not rewrite still changes the directory manifest.
    (settings.dataset_root / "mnist" / "unexpected.bin").write_bytes(b"tampered")

    summary = _service(settings).replay_journal()

    assert summary.models_restored == 1
    assert summary.datasets_restored == 0
    assert any("manifest hash changed" in reason for reason in summary.skipped)


def test_replay_never_restores_background_jobs(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service = _service(settings)
    _seed_runs(service)
    from aishield.jobs.contracts import JobRecord

    service._store.append("job", JobRecord.queued(uuid4(), "training"))

    summary = _service(settings).replay_journal()

    assert summary.jobs_skipped == 1
    assert _service(settings).list_jobs() == []


def test_replay_tolerates_a_corrupted_record(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    service = _service(settings)
    _seed_runs(service)
    # Corrupt the file directly: only the journal backend has an on-disk form.
    journal = RegistryJournal(settings.artifact_root)
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write('{"kind":"baseline","record":{"id":"not-a-uuid"}}\n')

    summary = _service(settings).replay_journal()

    assert summary.baselines_restored == 1
    assert any("unreadable record" in reason for reason in summary.skipped)


def test_replay_on_an_empty_journal_reports_nothing(tmp_path: Path) -> None:
    summary = _service(_settings(tmp_path)).replay_journal()

    assert summary.entries_read == 0
    assert summary.runs_restored == 0


def test_startup_replay_restores_the_previous_process_state(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_runs(_service(settings))
    replaying = settings.model_copy(update={"replay_journal_on_start": True})

    with TestClient(create_app(replaying, _service(replaying))) as client:
        assert len(client.get("/api/v1/registry/baselines").json()) == 1
        assert len(client.get("/api/v1/registry/attacks").json()) == 1
        assert len(client.get("/api/v1/registry/datasets").json()) == 1


def test_replay_endpoint_reports_a_summary(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    _seed_runs(_service(settings))
    service = _service(settings)

    with TestClient(create_app(settings, service)) as client:
        response = client.post("/api/v1/registry/journal/replay")

    assert response.status_code == 200
    assert response.json()["baselines_restored"] == 1
    assert response.json()["attacks_restored"] == 1
