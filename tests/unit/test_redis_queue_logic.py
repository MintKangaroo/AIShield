"""Redis job-queue behaviour verified without a Redis server.

The integration tests in `test_redis_jobs.py` prove this class works against a
real broker, but they only run where one is available. These exercise the same
logic through an injected in-memory client so the behaviour stays covered in any
environment — and so a logic change fails fast without waiting on a container.
"""

import threading
from typing import Any, cast
from uuid import uuid4

import pytest

from aishield.jobs.contracts import JobNotCancellableError, JobQueueFullError, JobStatus
from aishield.jobs.redis_queue import ORDER_KEY, PENDING_KEY, RECORDS_KEY, RedisJobQueue
from aishield.jobs.tasks import TrainingTask
from aishield.registry.errors import RegistryError
from aishield.training.contracts import TrainingConfig, TrainingStrategy

pytest.importorskip("redis", reason="the redis extra provides the exception types")


class FakePipeline:
    """Collects commands and applies them together, like a Redis pipeline."""

    def __init__(self, client: "FakeRedis") -> None:
        self._client = client
        self._queued: list[tuple[str, tuple[Any, ...]]] = []

    def hset(self, key: str, field: str, value: str) -> "FakePipeline":
        self._queued.append(("hset", (key, field, value)))
        return self

    def zadd(self, key: str, mapping: dict[str, float]) -> "FakePipeline":
        self._queued.append(("zadd", (key, mapping)))
        return self

    def rpush(self, key: str, value: str) -> "FakePipeline":
        self._queued.append(("rpush", (key, value)))
        return self

    def hdel(self, key: str, *fields: str) -> "FakePipeline":
        self._queued.append(("hdel", (key, *fields)))
        return self

    def zrem(self, key: str, *members: str) -> "FakePipeline":
        self._queued.append(("zrem", (key, *members)))
        return self

    def execute(self) -> list[None]:
        with self._client._lock:
            for name, args in self._queued:
                getattr(self._client, f"_apply_{name}")(*args)
        self._queued.clear()
        return []


class FakeRedis:
    """Just enough of the Redis surface this queue uses, in memory.

    Commands are serialized under one lock because a real Redis server executes
    them one at a time; without that the fake would report races the production
    broker cannot produce.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.hashes: dict[str, dict[str, str]] = {}
        self.zsets: dict[str, dict[str, float]] = {}
        self.lists: dict[str, list[str]] = {}
        self.closed = False
        self.fail_on: set[str] = set()

    # -- command surface ------------------------------------------------------

    def ping(self) -> bool:
        self._maybe_fail("ping")
        return True

    def pipeline(self) -> FakePipeline:
        self._maybe_fail("pipeline")
        return FakePipeline(self)

    def blpop(self, keys: list[str], timeout: int = 0) -> tuple[str, str] | None:
        with self._lock:
            self._maybe_fail("blpop")
            for key in keys:
                if self.lists.get(key):
                    return key, self.lists[key].pop(0)
            return None

    def hget(self, key: str, field: str) -> str | None:
        with self._lock:
            self._maybe_fail("hget")
            return self.hashes.get(key, {}).get(field)

    def hmget(self, key: str, fields: list[str]) -> list[str | None]:
        with self._lock:
            self._maybe_fail("hmget")
            return [self.hashes.get(key, {}).get(field) for field in fields]

    def zrange(self, key: str, start: int, stop: int) -> list[str]:
        with self._lock:
            self._maybe_fail("zrange")
            ordered = sorted(self.zsets.get(key, {}).items(), key=lambda item: item[1])
            members = [member for member, _ in ordered]
            return members[start:] if stop == -1 else members[start : stop + 1]

    def llen(self, key: str) -> int:
        return len(self.lists.get(key, []))

    def close(self) -> None:
        self.closed = True

    # -- internals ------------------------------------------------------------

    def _maybe_fail(self, command: str) -> None:
        if command in self.fail_on:
            from redis.exceptions import RedisError

            raise RedisError(f"simulated {command} failure")

    def _apply_hset(self, key: str, field: str, value: str) -> None:
        self.hashes.setdefault(key, {})[field] = value

    def _apply_zadd(self, key: str, mapping: dict[str, float]) -> None:
        self.zsets.setdefault(key, {}).update(mapping)

    def _apply_rpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).append(value)

    def _apply_hdel(self, key: str, *fields: str) -> None:
        for field in fields:
            self.hashes.get(key, {}).pop(field, None)

    def _apply_zrem(self, key: str, *members: str) -> None:
        for member in members:
            self.zsets.get(key, {}).pop(member, None)


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


def build_queue(client: FakeRedis, **kwargs: Any) -> RedisJobQueue:
    """Inject the fake. The queue only uses a narrow slice of the Redis surface,
    which the annotation cannot express, so the cast is confined to this helper."""

    return RedisJobQueue("redis://unused", client=cast(Any, client), **kwargs)


@pytest.fixture
def client() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def queue(client: FakeRedis) -> RedisJobQueue:
    return build_queue(client)


def test_submit_writes_the_record_and_the_pending_entry(
    queue: RedisJobQueue, client: FakeRedis
) -> None:
    job = queue.submit(make_task())

    assert job.status is JobStatus.QUEUED
    assert str(job.id) in client.hashes[RECORDS_KEY]
    assert str(job.id) in client.zsets[ORDER_KEY]
    assert len(client.lists[PENDING_KEY]) == 1


def test_claim_transitions_to_running_and_returns_the_task(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())

    claimed = queue.claim(timeout=1)

    assert claimed is not None
    record, task = claimed
    assert record.id == submitted.id
    assert record.status is JobStatus.RUNNING
    assert task.model_version_id is not None


def test_claim_on_an_empty_queue_returns_nothing(queue: RedisJobQueue) -> None:
    assert queue.claim(timeout=1) is None


def test_claim_drops_a_job_cancelled_while_queued(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    queue.cancel(submitted.id)

    assert queue.claim(timeout=1) is None
    assert queue.get(submitted.id).status is JobStatus.CANCELLED


def test_complete_and_fail_record_terminal_evidence(queue: RedisJobQueue) -> None:
    first = queue.submit(make_task())
    second = queue.submit(make_task())
    result = uuid4()

    queue.complete(first.id, result)
    queue.fail(second.id, "out of memory")

    assert queue.get(first.id).result_id == result
    assert queue.get(first.id).finished_at is not None
    assert queue.get(second.id).status is JobStatus.FAILED
    assert queue.get(second.id).error == "out of memory"


def test_pending_counts_only_unfinished_jobs(queue: RedisJobQueue) -> None:
    done = queue.submit(make_task())
    queue.submit(make_task())
    queue.complete(done.id, None)

    assert queue.pending == 1


def test_submit_refuses_work_past_the_bound(client: FakeRedis) -> None:
    bounded = build_queue(client, max_pending=1)
    bounded.submit(make_task())

    with pytest.raises(JobQueueFullError):
        bounded.submit(make_task())


def test_cancel_refuses_a_running_job(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    queue.claim(timeout=1)

    with pytest.raises(JobNotCancellableError):
        queue.cancel(submitted.id)


def test_cancelling_a_finished_job_returns_it_unchanged(queue: RedisJobQueue) -> None:
    submitted = queue.submit(make_task())
    queue.complete(submitted.id, None)

    assert queue.cancel(submitted.id).status is JobStatus.SUCCEEDED


def test_list_is_ordered_by_creation(queue: RedisJobQueue) -> None:
    submitted = [queue.submit(make_task()).id for _ in range(4)]

    assert [record.id for record in queue.list()] == submitted


def test_list_on_an_empty_queue_is_empty(queue: RedisJobQueue) -> None:
    assert queue.list() == []


def test_eviction_drops_the_oldest_finished_records(client: FakeRedis) -> None:
    bounded = build_queue(client, retained_jobs=2)
    for _ in range(5):
        submitted = bounded.submit(make_task())
        bounded.complete(submitted.id, None)

    removed = bounded.evict_finished()

    assert removed == 3
    assert len(bounded.list()) == 2


def test_eviction_is_a_no_op_below_the_limit(queue: RedisJobQueue) -> None:
    queue.complete(queue.submit(make_task()).id, None)

    assert queue.evict_finished() == 0


def test_get_raises_for_an_unknown_job(queue: RedisJobQueue) -> None:
    with pytest.raises(KeyError):
        queue.get(uuid4())


def test_observer_sees_each_transition(client: FakeRedis) -> None:
    seen: list[JobStatus] = []
    watched = build_queue(client, observer=lambda record: seen.append(record.status))
    submitted = watched.submit(make_task())
    watched.claim(timeout=1)
    watched.complete(submitted.id, None)

    assert seen == [JobStatus.QUEUED, JobStatus.RUNNING, JobStatus.SUCCEEDED]


def test_a_failing_observer_does_not_break_the_queue(client: FakeRedis) -> None:
    def explode(record: object) -> None:
        raise RuntimeError("metadata store unavailable")

    watched = build_queue(client, observer=explode)

    job = watched.submit(make_task())

    assert watched.get(job.id).status is JobStatus.QUEUED


@pytest.mark.parametrize(
    ("command", "action"),
    [
        ("ping", "check_ready"),
        ("blpop", "claim"),
        ("hget", "get"),
        ("zrange", "list"),
    ],
)
def test_broker_errors_surface_as_registry_errors(
    queue: RedisJobQueue, client: FakeRedis, command: str, action: str
) -> None:
    client.fail_on = {command}

    with pytest.raises(RegistryError):
        if action == "get":
            queue.get(uuid4())
        elif action == "claim":
            queue.claim(timeout=1)
        elif action == "list":
            queue.list()
        else:
            queue.check_ready()


def test_submit_errors_surface_as_registry_errors(queue: RedisJobQueue, client: FakeRedis) -> None:
    client.fail_on = {"pipeline"}

    with pytest.raises(RegistryError, match="could not enqueue"):
        queue.submit(make_task())


def test_shutdown_releases_the_client(queue: RedisJobQueue, client: FakeRedis) -> None:
    queue.shutdown()

    assert client.closed is True


def test_concurrent_submits_are_all_recorded(client: FakeRedis) -> None:
    """Every accepted submission must survive, with no lost update between writers."""

    spacious = build_queue(client, max_pending=64)

    def submit_many() -> None:
        for _ in range(10):
            spacious.submit(make_task())

    threads = [threading.Thread(target=submit_many) for _ in range(3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    records = spacious.list()
    assert len(records) == 30
    assert len({record.id for record in records}) == 30


def test_the_pending_bound_is_enforced_against_a_burst(client: FakeRedis) -> None:
    """The bound is back-pressure, not a hard reservation.

    It is read and then acted on without a transaction, so concurrent submitters
    can overshoot slightly. What must hold is that the queue refuses to grow
    without limit.
    """

    bounded = build_queue(client, max_pending=4)
    accepted = 0
    lock = threading.Lock()

    def submit_until_refused() -> None:
        nonlocal accepted
        for _ in range(10):
            try:
                bounded.submit(make_task())
            except JobQueueFullError:
                return
            with lock:
                accepted += 1

    threads = [threading.Thread(target=submit_until_refused) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert 4 <= accepted < 40


# --- retry and dead-letter ----------------------------------------------------


def test_fail_requeues_when_attempts_remain(client: FakeRedis) -> None:
    queue = build_queue(client, max_attempts=3)
    submitted = queue.submit(make_task())
    claimed = queue.claim(timeout=1)
    assert claimed is not None
    record, task = claimed
    assert record.attempts == 1  # claim counts the attempt

    requeued = queue.fail(submitted.id, "transient", task=task)

    assert requeued.status is JobStatus.QUEUED
    assert queue.get(submitted.id).status is JobStatus.QUEUED
    # The task envelope is back on the pending list for another worker.
    assert client.llen(PENDING_KEY) == 1


def test_fail_dead_letters_after_attempts_are_exhausted(client: FakeRedis) -> None:
    queue = build_queue(client, max_attempts=2)
    submitted = queue.submit(make_task())

    # Two claim+fail cycles exhaust the budget.
    for _ in range(2):
        claimed = queue.claim(timeout=1)
        assert claimed is not None
        record = queue.fail(submitted.id, "still failing", task=claimed[1])

    assert record.status is JobStatus.FAILED
    assert queue.get(submitted.id).attempts == 2
    assert client.llen(PENDING_KEY) == 0  # not requeued


def test_fail_without_a_task_dead_letters_immediately(client: FakeRedis) -> None:
    queue = build_queue(client, max_attempts=3)
    submitted = queue.submit(make_task())
    queue.claim(timeout=1)

    record = queue.fail(submitted.id, "no task to retry with")

    assert record.status is JobStatus.FAILED


def test_a_dead_lettered_job_stays_inspectable(client: FakeRedis) -> None:
    queue = build_queue(client, max_attempts=1)
    submitted = queue.submit(make_task())
    claimed = queue.claim(timeout=1)
    assert claimed is not None
    queue.fail(submitted.id, "boom", task=claimed[1])

    listed = queue.list()
    assert len(listed) == 1
    assert listed[0].status is JobStatus.FAILED
    assert listed[0].error == "boom"


def test_redis_queue_rejects_bad_max_attempts(client: FakeRedis) -> None:
    with pytest.raises(ValueError):
        build_queue(client, max_attempts=0)
