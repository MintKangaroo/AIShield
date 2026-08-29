"""End-to-end contract for the out-of-process evaluation worker.

The claim being tested is specific: the API accepts work without executing it,
and a worker sharing only the metadata store and the broker can rebuild what it
needs and finish the job.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.cli.worker import Worker
from aishield.core.config import Settings
from aishield.jobs.contracts import JobStatus
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.service import RegistryService
from aishield.training.contracts import TrainingConfig, TrainingStrategy

REDIS_URL = os.environ.get("AISHIELD_TEST_REDIS_URL")
POSTGRES_URL = os.environ.get("AISHIELD_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not (REDIS_URL and POSTGRES_URL),
    reason="set AISHIELD_TEST_REDIS_URL and AISHIELD_TEST_DATABASE_URL to run worker tests",
)


class WorkerFixtureAdapter(MNISTAdapter):
    """Deterministic data so a worker reload reproduces the same manifest hash."""

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "worker.fixture").write_bytes(b"worker-dataset")
        generator = torch.Generator().manual_seed(23)
        return TensorDataset(
            torch.rand(8, 1, 28, 28, generator=generator), torch.tensor([0, 1, 2, 3, 4, 5, 6, 7])
        )


@pytest.fixture
def settings(tmp_path: Path) -> Iterator[Settings]:
    from sqlalchemy import text

    from aishield.jobs.redis_queue import create_client
    from aishield.registry.postgres import create_engine

    assert POSTGRES_URL is not None and REDIS_URL is not None
    engine = create_engine(POSTGRES_URL)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS registry_metadata"))
    engine.dispose()
    client = create_client(REDIS_URL)
    client.flushdb()
    client.close()

    yield Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "artifacts" / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
        replay_journal_on_start=False,
        metadata_backend="postgresql",
        database_url=POSTGRES_URL,
        job_backend="redis",
        redis_url=REDIS_URL,
    )


def _api(settings: Settings) -> RegistryService:
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: WorkerFixtureAdapter()})


def _worker(settings: Settings) -> Worker:
    """A worker built the way the entry point builds it, with test adapters."""

    worker = Worker(settings, poll_timeout=1)
    worker.registry = _api(settings)
    worker.queue._observer = worker.registry.record_job
    return worker


def _seed(service: RegistryService) -> tuple[UUID, UUID]:
    dataset = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    model = service.load_small_cnn(dataset.id, seed=1729, checkpoint=None)
    return model.id, dataset.id


def _config() -> TrainingConfig:
    return TrainingConfig(
        strategy=TrainingStrategy.ADVERSARIAL,
        seed=1729,
        epochs=1,
        batch_size=2,
        max_samples=4,
        epsilon=0.1,
        step_size=0.05,
        attack_iterations=1,
        learning_rate=1e-3,
    )


def test_the_api_queues_without_executing(settings: Settings) -> None:
    api = _api(settings)
    model_id, dataset_id = _seed(api)

    job = api.submit_training_job(model_id, dataset_id, config=_config())

    assert job.status is JobStatus.QUEUED
    # Nothing ran: no training evidence exists yet anywhere.
    assert api.list_training() == []
    assert api.get_job(job.id).status is JobStatus.QUEUED
    api.shutdown()


def test_a_separate_worker_finishes_the_job(settings: Settings) -> None:
    api = _api(settings)
    model_id, dataset_id = _seed(api)
    job = api.submit_training_job(model_id, dataset_id, config=_config())

    worker = _worker(settings)
    try:
        worker.prepare()
        assert worker.run_once() is True
    finally:
        worker.close()

    finished = api.get_job(job.id)
    assert finished.status is JobStatus.SUCCEEDED, finished.error
    assert finished.result_id is not None
    api.shutdown()


def test_the_worker_rebuilds_handles_it_never_loaded(settings: Settings) -> None:
    """The worker shares no memory with the API, only the store and the broker."""

    api = _api(settings)
    model_id, dataset_id = _seed(api)
    api.submit_training_job(model_id, dataset_id, config=_config())

    worker = _worker(settings)
    try:
        assert worker.registry.list_models() == []  # nothing loaded yet
        worker.prepare()
        assert worker.registry.get_model_bundle(model_id).record.id == model_id
        assert worker.registry.get_dataset_bundle(dataset_id).record.id == dataset_id
        worker.run_once()
    finally:
        worker.close()
    api.shutdown()


def test_worker_evidence_reaches_the_api_through_the_shared_store(
    settings: Settings,
) -> None:
    api = _api(settings)
    model_id, dataset_id = _seed(api)
    api.submit_training_job(model_id, dataset_id, config=_config())

    worker = _worker(settings)
    try:
        worker.prepare()
        worker.run_once()
    finally:
        worker.close()

    assert api.list_training() == []  # the API has not looked yet
    api.replay_journal()
    training = api.list_training()
    assert len(training) == 1
    assert training[0].config.strategy is TrainingStrategy.ADVERSARIAL
    api.shutdown()


def test_a_failing_task_is_recorded_and_does_not_kill_the_worker(
    settings: Settings,
) -> None:
    api = _api(settings)
    model_id, dataset_id = _seed(api)
    job = api.submit_training_job(model_id, dataset_id, config=_config())

    worker = _worker(settings)
    try:
        worker.prepare()
        # Break the run after the handles were restored, the way a corrupt
        # checkpoint or an OOM would.
        worker.registry.execute_task = lambda task: (_ for _ in ()).throw(  # type: ignore[method-assign]
            RuntimeError("worker ran out of memory")
        )
        assert worker.run_once() is True
    finally:
        worker.close()

    failed = api.get_job(job.id)
    assert failed.status is JobStatus.FAILED
    assert failed.error == "worker ran out of memory"
    api.shutdown()


def test_run_once_reports_when_no_work_was_waiting(settings: Settings) -> None:
    worker = _worker(settings)
    try:
        worker.prepare()
        assert worker.run_once() is False
    finally:
        worker.close()


def test_job_transitions_are_journaled_by_both_processes(settings: Settings) -> None:
    api = _api(settings)
    model_id, dataset_id = _seed(api)
    api.submit_training_job(model_id, dataset_id, config=_config())

    worker = _worker(settings)
    try:
        worker.prepare()
        worker.run_once()
    finally:
        worker.close()

    records = [
        cast("dict[str, Any]", entry["record"])
        for entry in api.read_journal()
        if entry["kind"] == "job"
    ]
    statuses = [record["status"] for record in records]
    assert statuses == ["queued", "running", "succeeded"]
    api.shutdown()


def test_readiness_covers_the_broker_as_well_as_the_store(settings: Settings) -> None:
    service = _api(settings)

    with TestClient(create_app(settings, service)) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
