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


def _drain(queue: JobQueue, job_id: UUID, timeout: float = 5.0) -> JobRecord:
    """Wait for one job to reach a terminal status."""

    deadline = threading.Event()
    for _ in range(int(timeout / 0.01)):
        record = queue.get(job_id)
        if record.is_terminal:
            return record
        deadline.wait(0.01)
    raise AssertionError(f"job {job_id} did not finish within {timeout}s")


def test_successful_job_records_result_and_timestamps() -> None:
    queue = JobQueue(max_workers=1)
    result = uuid4()

    job = queue.submit("training", lambda: result)
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert job.status is JobStatus.QUEUED
    assert finished.status is JobStatus.SUCCEEDED
    assert finished.result_id == result
    assert finished.error is None
    assert finished.started_at is not None
    assert finished.finished_at is not None
    assert finished.finished_at >= finished.started_at


def test_failing_job_preserves_the_error_as_evidence() -> None:
    queue = JobQueue(max_workers=1)

    def explode() -> UUID:
        raise RuntimeError("dataset manifest changed under the run")

    job = queue.submit("training", explode)
    finished = _drain(queue, job.id)
    queue.shutdown()

    assert finished.status is JobStatus.FAILED
    assert finished.error == "dataset manifest changed under the run"
    assert finished.result_id is None


def test_queue_refuses_work_beyond_the_pending_bound() -> None:
    release = threading.Event()
    queue = JobQueue(max_workers=1, max_pending=2)

    def block() -> None:
        release.wait(5.0)

    first = queue.submit("training", block)
    queue.submit("training", block)

    with pytest.raises(JobQueueFullError):
        queue.submit("training", block)

    release.set()
    _drain(queue, first.id)
    queue.shutdown()


def test_completed_jobs_are_evicted_once_retention_is_exceeded() -> None:
    queue = JobQueue(max_workers=1, retained_jobs=2)

    jobs = [queue.submit("training", lambda: None) for _ in range(5)]
    for job in jobs:
        # A record may already be evicted by a later completion, which is the behaviour
        # under test, so a missing key here is an expected outcome rather than a failure.
        with suppress(KeyError):
            _drain(queue, job.id)
    queue.shutdown()

    assert len(queue.list()) <= 2


def test_queued_job_can_be_cancelled_before_it_starts() -> None:
    release = threading.Event()
    queue = JobQueue(max_workers=1)

    def block() -> None:
        release.wait(5.0)

    blocker = queue.submit("training", block)
    queued = queue.submit("training", lambda: uuid4())

    cancelled = queue.cancel(queued.id)
    release.set()
    _drain(queue, blocker.id)
    queue.shutdown()

    assert cancelled.status is JobStatus.CANCELLED
    assert cancelled.finished_at is not None


def test_running_job_cannot_be_cancelled() -> None:
    started = threading.Event()
    release = threading.Event()
    queue = JobQueue(max_workers=1)

    def run() -> None:
        started.set()
        release.wait(5.0)

    job = queue.submit("training", run)
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

    queue = JobQueue(max_workers=1, observer=observe)
    job = queue.submit("training", lambda: None)
    _drain(queue, job.id)
    queue.shutdown()

    assert seen == [JobStatus.QUEUED, JobStatus.SUCCEEDED]


def test_observer_failure_does_not_break_the_worker() -> None:
    def explode(record: JobRecord) -> None:
        raise RuntimeError("journal unavailable")

    queue = JobQueue(max_workers=1, observer=explode)
    result = uuid4()

    job = queue.submit("training", lambda: result)
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
        JobQueue(max_workers=max_workers, max_pending=max_pending, retained_jobs=retained)
