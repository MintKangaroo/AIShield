"""Contract for the Redis job backend and the out-of-process worker.

The point of this backend is that the API process stops doing the heavy work.
These tests assert the properties that claim depends on: a task survives with no
worker running, exactly one worker claims each job, and status is visible to a
process that did not execute it.
"""

import os
import threading
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from aishield.jobs.contracts import JobNotCancellableError, JobQueueFullError, JobStatus
from aishield.jobs.redis_queue import PENDING_KEY, RedisJobQueue
from aishield.jobs.tasks import TrainingTask
from aishield.registry.errors import RegistryError
from aishield.training.contracts import TrainingConfig, TrainingStrategy

REDIS_URL = os.environ.get("AISHIELD_TEST_REDIS_URL")

pytestmark = pytest.mark.skipif(
    not REDIS_URL, reason="set AISHIELD_TEST_REDIS_URL to run Redis job tests"
)


def make_task() -> TrainingTask:
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


@pytest.fixture
def queue() -> Iterator[RedisJobQueue]:
    assert REDIS_URL is not None
    backend = RedisJobQueue(REDIS_URL)
    backend._client.flushdb()
    try:
        yield backend
    finally:
        backend._client.flushdb()
        backend.shutdown()


def test_a_queued_task_waits_when_no_worker_is_running(queue: RedisJobQueue) -> None:
    """The API accepts work without executing it; that is the whole point."""

    job = queue.submit(make_task())

    assert job.status is JobStatus.QUEUED
    assert queue.get(job.id).status is JobStatus.QUEUED
    assert queue._client.llen(PENDING_KEY) == 1


def test_claim_marks_the_job_running_and_returns_the_task(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())

    claimed = queue.claim(timeout=1)

    assert claimed is not None
    record, task = claimed
    assert record.id == submitted.id
    assert record.status is JobStatus.RUNNING
    assert record.started_at is not None
    assert task.kind.value == "training"


def test_claim_returns_nothing_when_the_queue_is_empty(queue: RedisJobQueue) -> None:
    assert queue.claim(timeout=1) is None


def test_only_one_worker_claims_each_job(queue: RedisJobQueue) -> None:
    """Two workers racing on one queue must never run the same task twice."""

    submitted = {queue.submit(make_task()).id for _ in range(6)}
    claimed: list[UUID] = []
    lock = threading.Lock()

    def consume() -> None:
        while True:
            result = queue.claim(timeout=1)
            if result is None:
                return
            with lock:
                claimed.append(result[0].id)

    workers = [threading.Thread(target=consume) for _ in range(3)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(30)

    assert sorted(claimed) == sorted(submitted)
    assert len(claimed) == len(set(claimed))


def test_completion_is_visible_to_a_process_that_did_not_run_it(
    queue: RedisJobQueue,
) -> None:
    assert REDIS_URL is not None
    submitted = queue.submit(make_task())
    claimed = queue.claim(timeout=1)
    assert claimed is not None
    result = uuid4()

    queue.complete(claimed[0].id, result)

    # A second client stands in for the API process reading a worker's outcome.
    observer = RedisJobQueue(REDIS_URL)
    try:
        seen = observer.get(submitted.id)
    finally:
        observer.shutdown()
    assert seen.status is JobStatus.SUCCEEDED
    assert seen.result_id == result
    assert seen.finished_at is not None


def test_failure_is_recorded_as_evidence(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    claimed = queue.claim(timeout=1)
    assert claimed is not None

    queue.fail(claimed[0].id, "dataset manifest changed under the run")

    record = queue.get(submitted.id)
    assert record.status is JobStatus.FAILED
    assert record.error == "dataset manifest changed under the run"
    assert record.result_id is None


def test_queue_refuses_work_beyond_the_pending_bound() -> None:
    assert REDIS_URL is not None
    bounded = RedisJobQueue(REDIS_URL, max_pending=2)
    bounded._client.flushdb()
    try:
        bounded.submit(make_task())
        bounded.submit(make_task())

        with pytest.raises(JobQueueFullError):
            bounded.submit(make_task())
    finally:
        bounded._client.flushdb()
        bounded.shutdown()


def test_an_unclaimed_job_can_be_cancelled_and_is_never_run(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())

    cancelled = queue.cancel(submitted.id)

    assert cancelled.status is JobStatus.CANCELLED
    # The envelope is still in the list, but claiming it must not execute anything.
    assert queue.claim(timeout=1) is None


def test_a_claimed_job_cannot_be_cancelled(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    queue.claim(timeout=1)

    with pytest.raises(JobNotCancellableError):
        queue.cancel(submitted.id)


def test_cancelling_a_finished_job_is_a_no_op(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    claimed = queue.claim(timeout=1)
    assert claimed is not None
    queue.complete(claimed[0].id, uuid4())

    assert queue.cancel(submitted.id).status is JobStatus.SUCCEEDED


def test_listing_is_ordered_by_creation(queue: RedisJobQueue) -> None:
    submitted = [queue.submit(make_task()).id for _ in range(5)]

    assert [record.id for record in queue.list()] == submitted


def test_finished_jobs_are_evicted_beyond_the_retention_limit() -> None:
    assert REDIS_URL is not None
    bounded = RedisJobQueue(REDIS_URL, retained_jobs=2)
    bounded._client.flushdb()
    try:
        for _ in range(5):
            submitted = bounded.submit(make_task())
            claimed = bounded.claim(timeout=1)
            assert claimed is not None
            bounded.complete(claimed[0].id, submitted.id)

        removed = bounded.evict_finished()

        assert removed == 3
        assert len(bounded.list()) == 2
    finally:
        bounded._client.flushdb()
        bounded.shutdown()


def test_unknown_job_raises_a_key_error(queue: RedisJobQueue) -> None:
    with pytest.raises(KeyError):
        queue.get(uuid4())


def test_observer_sees_every_transition(queue: RedisJobQueue) -> None:
    assert REDIS_URL is not None
    seen: list[JobStatus] = []
    watched = RedisJobQueue(REDIS_URL, observer=lambda record: seen.append(record.status))
    try:
        submitted = watched.submit(make_task())
        claimed = watched.claim(timeout=1)
        assert claimed is not None
        watched.complete(submitted.id, uuid4())
    finally:
        watched.shutdown()

    assert seen == [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED]


def test_an_unreachable_broker_is_reported() -> None:
    with pytest.raises(RegistryError, match="job broker is unreachable"):
        RedisJobQueue("redis://127.0.0.1:1/0")


@pytest.mark.parametrize(("max_pending", "retained"), [(0, 1), (1, 0)])
def test_queue_rejects_nonsensical_bounds(max_pending: int, retained: int) -> None:
    assert REDIS_URL is not None
    with pytest.raises(ValueError):
        RedisJobQueue(REDIS_URL, max_pending=max_pending, retained_jobs=retained)
