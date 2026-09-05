"""Numerical and behavioural contract for the bounded background worker queue."""

import threading
from contextlib import suppress
from uuid import UUID, uuid4

import pytest

from aishield.jobs.contracts import (
    JobNotCancellableError,
    JobQueueFullError,
    JobRecord,
    JobStatus,
)
from aishield.jobs.queue import JobQueue
from aishield.jobs.tasks import TaskDescriptor, TrainingTask
from aishield.training.contracts import TrainingConfig, TrainingStrategy


def make_task() -> TrainingTask:
    """A valid descriptor; the queue never inspects anything but its ``kind``."""

    return TrainingTask(
        model_version_id=uuid4(),
        dataset_id=uuid4(),
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
        ),
    )


def _drain(queue: JobQueue, job_id: UUID, timeout: float = 5.0) -> JobRecord:
    """Wait for one job to reach a terminal status."""

    waiter = threading.Event()
    for _ in range(int(timeout / 0.01)):
        record = queue.get(job_id)
        if record.is_terminal:
            return record
        waiter.wait(0.01)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_successful_job_records_result_and_timestamps() -> None:
    result = uuid4()
    queue = JobQueue(lambda task: result, max_workers=1)

    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert job.status is JobStatus.QUEUED
    assert job.kind == "training"
    assert finished.status is JobStatus.SUCCEEDED
    assert finished.result_id == result
    assert finished.error is None
    assert finished.started_at is not None
    assert finished.finished_at is not None
    assert finished.finished_at >= finished.started_at


def test_the_executor_receives_the_submitted_descriptor() -> None:
    seen: list[TaskDescriptor] = []

    def record(task: TaskDescriptor) -> None:
        seen.append(task)

    queue = JobQueue(record, max_workers=1)
    task = make_task()

    job = queue.submit(task)
    _drain(queue, job.id)
    queue.shutdown()

    assert seen == [task]


def test_failing_job_preserves_the_error_as_evidence() -> None:
    def explode(task: TaskDescriptor) -> UUID:
        raise RuntimeError("dataset manifest changed under the run")

    queue = JobQueue(explode, max_workers=1)

    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.FAILED
    assert finished.error == "dataset manifest changed under the run"
    assert finished.result_id is None


def test_queue_refuses_work_beyond_the_pending_bound() -> None:
    release = threading.Event()

    def block(task: TaskDescriptor) -> None:
        release.wait(5.0)

    queue = JobQueue(block, max_workers=1, max_pending=2)

    first = queue.submit(make_task())
    queue.submit(make_task())

    with pytest.raises(JobQueueFullError):
        queue.submit(make_task())

    release.set()
    _drain(queue, first.id)
    queue.shutdown()


def test_completed_jobs_are_evicted_once_retention_is_exceeded() -> None:
    queue = JobQueue(lambda task: None, max_workers=1, retained_jobs=2)

    jobs = [queue.submit(make_task()) for _ in range(5)]
    for job in jobs:
        # A record may already be evicted by a later completion, which is the behaviour
        # under test, so a missing key here is an expected outcome rather than a failure.
        with suppress(KeyError):
            _drain(queue, job.id)
    queue.shutdown()

    assert len(queue.list()) <= 2


def test_queued_job_can_be_cancelled_before_it_starts() -> None:
    release = threading.Event()

    def block(task: TaskDescriptor) -> None:
        release.wait(5.0)

    queue = JobQueue(block, max_workers=1)

    blocker = queue.submit(make_task())
    queued = queue.submit(make_task())

    cancelled = queue.cancel(queued.id)
    release.set()
    _drain(queue, blocker.id)
    queue.shutdown()

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.finished_at is not None


def test_running_job_cannot_be_cancelled() -> None:
    started = threading.Event()
    release = threading.Event()

    def run(task: TaskDescriptor) -> None:
        started.set()
        release.wait(5.0)

    queue = JobQueue(run, max_workers=1)

    job = queue.submit(make_task())
    assert started.wait(5.0)

    with pytest.raises(JobNotCancellableError):
        queue.cancel(job.id)

    release.set()
    _drain(queue, job.id)
    queue.shutdown()


def test_observer_sees_every_status_transition() -> None:
    seen: list[JobStatus] = []
    lock = threading.Lock()

    def observe(record: JobRecord) -> None:
        with lock:
            seen.append(record.status)

    queue = JobQueue(lambda task: None, max_workers=1, observer=observe)
    job = queue.submit(make_task())
    _drain(queue, job.id)
    queue.shutdown()

    assert seen == [JobStatus.QUEUED, JobStatus.SUCCEEDED]


def test_observer_failure_does_not_break_the_worker() -> None:
    def explode(record: JobRecord) -> None:
        raise RuntimeError("metadata store unavailable")

    result = uuid4()
    queue = JobQueue(lambda task: result, max_workers=1, observer=explode)

    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.SUCCEEDED
    assert finished.result_id == result


@pytest.mark.parametrize(
    ("max_workers", "max_pending", "retained"),
    [(0, 1, 1), (1, 0, 1), (1, 1, 0)],
)
def test_queue_rejects_nonsensical_bounds(
    max_workers: int, max_pending: int, retained: int
) -> None:
    with pytest.raises(ValueError):
        JobQueue(
            lambda task: None,
            max_workers=max_workers,
            max_pending=max_pending,
            retained_jobs=retained,
        )


# --- retry and dead-letter ----------------------------------------------------


def test_a_flaky_job_is_retried_until_it_succeeds() -> None:
    attempts = {"n": 0}
    result = uuid4()

    def flaky(task: TaskDescriptor) -> UUID:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RuntimeError("transient failure")
        return result

    queue = JobQueue(flaky, max_workers=1, max_attempts=3)
    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.SUCCEEDED
    assert finished.result_id == result
    assert finished.attempts == 3


def test_a_job_that_always_fails_is_dead_lettered_after_max_attempts() -> None:
    attempts = {"n": 0}

    def always_fails(task: TaskDescriptor) -> UUID:
        attempts["n"] += 1
        raise RuntimeError("permanent failure")

    queue = JobQueue(always_fails, max_workers=1, max_attempts=3)
    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.FAILED
    assert finished.error == "permanent failure"
    assert finished.attempts == 3
    assert attempts["n"] == 3


def test_the_default_is_a_single_attempt_no_retry() -> None:
    attempts = {"n": 0}

    def fails(task: TaskDescriptor) -> UUID:
        attempts["n"] += 1
        raise RuntimeError("boom")

    queue = JobQueue(fails, max_workers=1)  # default max_attempts=1
    job = queue.submit(make_task())
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.FAILED
    assert finished.attempts == 1
    assert attempts["n"] == 1


def test_max_attempts_must_be_positive() -> None:
    with pytest.raises(ValueError):
        JobQueue(lambda task: None, max_workers=1, max_attempts=0)
