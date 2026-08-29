"""Service-level contract for bounded concurrency and background training jobs."""

import threading
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
import torch
from fastapi.testclient import TestClient
from torch.utils.data import Dataset, TensorDataset

from aishield.api.main import create_app
from aishield.core.config import Settings
from aishield.jobs.contracts import JobStatus
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import MNISTAdapter
from aishield.registry.errors import RegistryBusyError, RegistryNotFoundError
from aishield.registry.service import RegistryService


class JobFixtureAdapter(MNISTAdapter):
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "jobs.fixture").write_bytes(b"jobs-dataset")
        return TensorDataset(torch.zeros(4, 1, 28, 28), torch.tensor([0, 1, 2, 3]))


def _service(tmp_path: Path, **overrides: Any) -> RegistryService:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
        **overrides,
    )
    return RegistryService(settings, dataset_adapters={DatasetName.MNIST: JobFixtureAdapter()})


def _loaded(service: RegistryService) -> tuple[UUID, UUID]:
    dataset = service.load_dataset(DatasetName.MNIST, DatasetSplit.TEST, download=False)
    model = service.load_small_cnn(dataset.id, seed=1729, checkpoint=None)
    return model.id, dataset.id


def test_run_slot_rejects_a_second_concurrent_api_run(tmp_path: Path) -> None:
    service = _service(tmp_path, max_concurrent_runs=1)
    entered = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with service._run_slot("test"):
            entered.set()
            release.wait(5.0)

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(5.0)

    try:
        with pytest.raises(RegistryBusyError), service._run_slot("test"):
            pass
    finally:
        release.set()
        holder.join(5.0)


def test_run_slot_is_released_after_a_failed_run(tmp_path: Path) -> None:
    service = _service(tmp_path, max_concurrent_runs=1)

    with pytest.raises(RuntimeError), service._run_slot("test"):
        raise RuntimeError("run exploded")

    # The slot must be free again, otherwise one failure wedges the process.
    with service._run_slot("test"):
        pass


def test_worker_mode_waits_instead_of_failing(tmp_path: Path) -> None:
    service = _service(tmp_path, max_concurrent_runs=1, job_slot_timeout_seconds=5.0)
    entered = threading.Event()
    release = threading.Event()
    acquired = threading.Event()

    def hold() -> None:
        with service._run_slot("test"):
            entered.set()
            release.wait(5.0)

    def worker() -> None:
        with service._worker_mode(), service._run_slot("test"):
            acquired.set()

    holder = threading.Thread(target=hold)
    holder.start()
    assert entered.wait(5.0)

    waiter = threading.Thread(target=worker)
    waiter.start()
    assert not acquired.wait(0.2)  # still blocked behind the holder

    release.set()
    holder.join(5.0)
    assert acquired.wait(5.0)
    waiter.join(5.0)


def test_queued_training_job_reaches_a_terminal_status(tmp_path: Path) -> None:
    service = _service(tmp_path)
    model_id, dataset_id = _loaded(service)

    from aishield.training.contracts import TrainingConfig, TrainingStrategy

    job = service.submit_training_job(
        model_id,
        dataset_id,
        config=TrainingConfig(
            strategy=TrainingStrategy.ADVERSARIAL,
            seed=1729,
            epochs=1,
            batch_size=2,
            max_samples=4,
            epsilon=8 / 255,
            step_size=2 / 255,
            attack_iterations=1,
            learning_rate=1e-3,
            trades_beta=6.0,
        ),
    )

    for _ in range(600):
        record = service.get_job(job.id)
        if record.is_terminal:
            break
        threading.Event().wait(0.05)

    assert record.status is JobStatus.SUCCEEDED, record.error
    assert record.result_id is not None
    assert any(entry["kind"] == "job" for entry in service.read_journal())


def test_queueing_a_job_for_a_missing_model_fails_immediately(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _, dataset_id = _loaded(service)

    from aishield.training.contracts import TrainingConfig, TrainingStrategy

    with pytest.raises(RegistryNotFoundError):
        service.submit_training_job(
            uuid4(),
            dataset_id,
            config=TrainingConfig(
                strategy=TrainingStrategy.ADVERSARIAL,
                seed=1729,
                epochs=1,
                batch_size=2,
                max_samples=4,
                epsilon=8 / 255,
                step_size=2 / 255,
                attack_iterations=1,
                learning_rate=1e-3,
                trades_beta=6.0,
            ),
        )


def test_cancelling_an_unknown_job_is_a_not_found(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(RegistryNotFoundError):
        service.cancel_job(uuid4())


def test_cancel_endpoint_reports_404_for_an_unknown_job(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(f"/api/v1/registry/jobs/{uuid4()}/cancel")

    assert response.status_code == 404
