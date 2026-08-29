"""End-to-end registry behaviour when metadata lives in PostgreSQL.

These tests are the migration evidence: the same run sequence must produce the
same registry state through the database backend as it does through the journal,
including restart recovery.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.core.config import Settings
from aishield.evaluation.contracts import BaselineConfig
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.service import RegistryService

POSTGRES_URL = os.environ.get("AISHIELD_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_URL, reason="set AISHIELD_TEST_DATABASE_URL to run PostgreSQL registry tests"
)


class PostgresFixtureAdapter(MNISTAdapter):
    """A deterministic split so a reload reproduces the same manifest hash."""

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "postgres.fixture").write_bytes(b"postgres-dataset")
        generator = torch.Generator().manual_seed(11)
        return TensorDataset(
            torch.rand(6, 1, 28, 28, generator=generator), torch.tensor([0, 1, 2, 3, 4, 5])
        )


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    from sqlalchemy import text

    from aishield.registry.postgres import create_engine

    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS registry_metadata"))
    engine.dispose()
    yield Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "artifacts" / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
        replay_journal_on_start=False,
        metadata_backend="postgresql",
        database_url=POSTGRES_URL,
    )


def _service(settings: Settings) -> RegistryService:
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: PostgresFixtureAdapter()})


def _seed(service: RegistryService) -> tuple[UUID, UUID, UUID]:
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
    return dataset.id, model.id, baseline.id


def test_runs_are_persisted_to_the_database(settings: Settings) -> None:
    from sqlalchemy import text

    from aishield.registry.postgres import create_engine

    service = _service(settings)
    _seed(service)

    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT kind, count(*) FROM registry_metadata GROUP BY kind ORDER BY kind")
        ).all()
    engine.dispose()
    counts = {str(row[0]): int(row[1]) for row in rows}

    assert counts == {"attack": 1, "baseline": 1, "dataset": 1, "model": 1}


def test_a_restarted_process_recovers_from_the_database(settings: Settings) -> None:
    original = _service(settings)
    dataset_id, model_id, baseline_id = _seed(original)

    # A fresh service shares nothing but the database and the artifact directory.
    restarted = _service(settings)
    assert restarted.list_baselines() == []

    summary = restarted.replay_journal()

    assert summary.skipped == ()
    assert summary.datasets_restored == 1
    assert summary.models_restored == 1
    assert summary.baselines_restored == 1
    assert summary.attacks_restored == 1
    assert restarted.get_baseline(baseline_id).id == baseline_id
    assert restarted.get_model_bundle(model_id).record.id == model_id
    assert restarted.get_dataset_bundle(dataset_id).record.id == dataset_id


def test_two_processes_share_one_registry(settings: Settings) -> None:
    """The point of the database backend: a second process sees the first one's runs."""

    writer = _service(settings)
    _, _, baseline_id = _seed(writer)

    reader = _service(settings)
    reader.replay_journal()

    assert [record.id for record in reader.list_baselines()] == [baseline_id]
    assert len(reader.list_attacks()) == 1


def test_database_backed_runs_export_the_same_envelope(settings: Settings) -> None:
    service = _service(settings)
    _, _, baseline_id = _seed(service)

    envelope = service.export_experiment(baseline_id)

    assert envelope.experiment.id == baseline_id
    assert len(envelope.attack_runs) == 1
    assert envelope.robustness_score is not None


def test_the_api_replays_the_database_at_startup(settings: Settings) -> None:
    _seed(_service(settings))
    replaying = settings.model_copy(update={"replay_journal_on_start": True})

    with TestClient(create_app(replaying, _service(replaying))) as client:
        assert len(client.get("/api/v1/registry/baselines").json()) == 1
        assert len(client.get("/api/v1/registry/attacks").json()) == 1
        assert len(client.get("/api/v1/registry/journal").json()) == 4
