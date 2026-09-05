"""Redis-backed job queue for out-of-process evaluation workers.

The in-process queue keeps job records in memory, so only the API process can
see them and only the API process can run the work. This backend puts both the
pending task list and the job records in Redis, which is what lets a separate
worker process — on another machine, with its own CPU and memory budget — pick
the work up.

The task payload carries no runtime objects: a worker reconstructs the model and
dataset handles from the shared metadata store, exactly as a restarted API does.
"""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID, uuid4

from aishield.jobs.contracts import (
    JobNotCancellableError,
    JobQueueFullError,
    JobRecord,
    JobStatus,
)
from aishield.jobs.queue import JobObserver
from aishield.jobs.tasks import TaskDescriptor, task_adapter
from aishield.registry.errors import RegistryError

if TYPE_CHECKING:  # pragma: no cover - typing only
    from redis import Redis

logger = logging.getLogger("aishield.jobs.redis")

#: Redis key holding the FIFO list of queued task envelopes.
PENDING_KEY = "aishield:jobs:pending"
#: Hash of job id -> serialized JobRecord.
RECORDS_KEY = "aishield:jobs:records"
#: Sorted set of job ids by creation time, so listing and eviction stay ordered.
ORDER_KEY = "aishield:jobs:order"


def create_client(redis_url: str) -> "Redis":
    """Build a Redis client, translating a missing driver into a clear error."""

    try:
        from redis import Redis
    except ModuleNotFoundError as error:  # pragma: no cover - optional dependency
        raise RegistryError(
            'Redis job queueing needs the "redis" extra: pip install -e ".[redis]"'
        ) from error
    return Redis.from_url(redis_url, decode_responses=True)


class RedisJobQueue:
    """Share pending work and job status across processes through Redis."""

    def __init__(
        self,
        redis_url: str,
        *,
        max_pending: int = 16,
        retained_jobs: int = 256,
        max_attempts: int = 1,
        observer: JobObserver | None = None,
        client: "Redis | None" = None,
    ) -> None:
        if max_pending < 1:
            raise ValueError("max_pending must be at least 1")
        if retained_jobs < 1:
            raise ValueError("retained_jobs must be at least 1")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._client = client if client is not None else create_client(redis_url)
        self._max_pending = max_pending
        self._retained_jobs = retained_jobs
        self._max_attempts = max_attempts
        self._observer = observer
        self.check_ready()

    def check_ready(self) -> None:
        """Confirm the broker is reachable so readiness never guesses."""

        from redis.exceptions import RedisError

        try:
            self._client.ping()
        except RedisError as error:
            raise RegistryError(f"job broker is unreachable: {error}") from error

    # -- writes ---------------------------------------------------------------

    def submit(self, task: TaskDescriptor) -> JobRecord:
        """Enqueue work for whichever worker claims it next.

        The pending bound is read and then acted on without a transaction, so
        simultaneous submitters can overshoot it slightly. It is back-pressure
        against an unbounded backlog, not a hard reservation.
        """

        from redis.exceptions import RedisError

        pending = self.pending
        if pending >= self._max_pending:
            logger.warning(
                "job rejected: queue is full",
                extra={"pending": pending, "max_pending": self._max_pending},
            )
            raise JobQueueFullError(
                f"the worker queue already holds {pending} unfinished jobs; "
                f"retry once one completes"
            )
        job = JobRecord.queued(uuid4(), task.kind.value)
        envelope = {"job_id": str(job.id), "task": task.model_dump(mode="json")}
        try:
            pipeline = self._client.pipeline()
            self._write(pipeline, job)
            pipeline.rpush(PENDING_KEY, _dumps(envelope))
            pipeline.execute()
        except RedisError as error:
            raise RegistryError(f"could not enqueue the job: {error}") from error
        self._publish(job)
        logger.info("job queued", extra={"job_id": str(job.id), "job_kind": job.kind})
        return job

    def claim(self, *, timeout: int = 5) -> tuple[JobRecord, TaskDescriptor] | None:
        """Block until work is available, then mark it running and return it.

        Redis pops the entry atomically, so two workers never claim the same job.
        """

        from redis.exceptions import RedisError

        try:
            popped = self._client.blpop([PENDING_KEY], timeout=timeout)
        except RedisError as error:
            raise RegistryError(f"could not read from the job queue: {error}") from error
        if popped is None:
            return None
        # redis-py shares type stubs between its sync and async clients, so the
        # synchronous return type is widened with Awaitable. Narrow it here.
        envelope = _loads(cast("tuple[str, str]", popped)[1])
        job_id = UUID(str(envelope["job_id"]))
        record = self.get(job_id)
        if record.status is JobStatus.CANCELLED:
            # Cancelled while it sat in the queue; drop it without running anything.
            logger.info("claimed job was already cancelled", extra={"job_id": str(job_id)})
            return None
        task = task_adapter.validate_python(envelope["task"])
        running = record.model_copy(
            update={
                "status": JobStatus.RUNNING,
                "started_at": datetime.now(UTC),
                "attempts": record.attempts + 1,
            }
        )
        self._save(running)
        logger.info("job started", extra={"job_id": str(job_id), "job_kind": running.kind})
        return running, task

    def complete(self, job_id: UUID, result_id: UUID | None) -> JobRecord:
        record = self.get(job_id).model_copy(
            update={
                "status": JobStatus.SUCCEEDED,
                "result_id": result_id,
                "finished_at": datetime.now(UTC),
            }
        )
        self._save(record)
        logger.info(
            "job succeeded",
            extra={"job_id": str(job_id), "result_id": str(result_id) if result_id else None},
        )
        return record

    def fail(self, job_id: UUID, error: str, *, task: TaskDescriptor | None = None) -> JobRecord:
        """Retry the job if attempts remain and the task is available; else dead-letter.

        A dead-lettered job is a FAILED record that exhausted its attempts. It stays
        in the job list as inspectable evidence rather than vanishing.
        """

        current = self.get(job_id)
        if task is not None and current.attempts < self._max_attempts:
            from redis.exceptions import RedisError

            requeued = current.model_copy(update={"status": JobStatus.QUEUED, "error": error})
            envelope = {"job_id": str(job_id), "task": task.model_dump(mode="json")}
            try:
                pipeline = self._client.pipeline()
                self._write(pipeline, requeued)
                pipeline.rpush(PENDING_KEY, _dumps(envelope))
                pipeline.execute()
            except RedisError as broker_error:
                raise RegistryError(f"could not requeue the job: {broker_error}") from broker_error
            self._publish(requeued)
            logger.warning(
                "job failed; retrying",
                extra={
                    "job_id": str(job_id),
                    "attempt": current.attempts,
                    "max_attempts": self._max_attempts,
                },
            )
            return requeued
        record = current.model_copy(
            update={
                "status": JobStatus.FAILED,
                "error": error,
                "finished_at": datetime.now(UTC),
            }
        )
        self._save(record)
        logger.warning(
            "job dead-lettered",
            extra={"job_id": str(job_id), "attempts": current.attempts, "detail": error},
        )
        return record

    def cancel(self, job_id: UUID) -> JobRecord:
        """Cancel a job that has not been claimed; a running job is left alone."""

        record = self.get(job_id)
        if record.is_terminal:
            return record
        if record.status is JobStatus.RUNNING:
            raise JobNotCancellableError(
                f"job {job_id} has already started and cannot be cancelled"
            )
        cancelled = record.model_copy(
            update={"status": JobStatus.CANCELLED, "finished_at": datetime.now(UTC)}
        )
        # The envelope stays in the list; `claim` drops it when it sees the status.
        self._save(cancelled)
        logger.info("job cancelled", extra={"job_id": str(job_id)})
        return cancelled

    # -- reads ----------------------------------------------------------------

    @property
    def pending(self) -> int:
        """Jobs that are queued or already running, across every process."""

        return sum(1 for record in self.list() if not record.is_terminal)

    def get(self, job_id: UUID) -> JobRecord:
        from redis.exceptions import RedisError

        try:
            raw = self._client.hget(RECORDS_KEY, str(job_id))
        except RedisError as error:
            raise RegistryError(f"could not read job {job_id}: {error}") from error
        if raw is None:
            raise KeyError(job_id)
        return JobRecord.model_validate(_loads(str(raw)))

    def list(self) -> list[JobRecord]:
        from redis.exceptions import RedisError

        try:
            ids = cast("list[str]", self._client.zrange(ORDER_KEY, 0, -1))
            raw = cast("list[str | None]", self._client.hmget(RECORDS_KEY, ids)) if ids else []
        except RedisError as error:
            raise RegistryError(f"could not list jobs: {error}") from error
        return [JobRecord.model_validate(_loads(item)) for item in raw if item is not None]

    # -- internals ------------------------------------------------------------

    def _save(self, record: JobRecord) -> None:
        from redis.exceptions import RedisError

        try:
            pipeline = self._client.pipeline()
            self._write(pipeline, record)
            pipeline.execute()
        except RedisError as error:
            raise RegistryError(f"could not update job {record.id}: {error}") from error
        self._publish(record)

    def _publish(self, record: JobRecord) -> None:
        """Record the transition as audit evidence without risking the worker."""

        if self._observer is None:
            return
        try:
            self._observer(record)
        except Exception:  # noqa: BLE001 - observability must not break the worker
            logger.exception("job observer failed", extra={"job_id": str(record.id)})

    def _write(self, pipeline: Any, record: JobRecord) -> None:
        """Queue the record write and its ordering entry onto an open pipeline."""

        pipeline.hset(RECORDS_KEY, str(record.id), record.model_dump_json())
        pipeline.zadd(ORDER_KEY, {str(record.id): record.created_at.timestamp()})

    def evict_finished(self) -> int:
        """Drop the oldest terminal records beyond the retention limit."""

        terminal = [record for record in self.list() if record.is_terminal]
        excess = len(terminal) - self._retained_jobs
        if excess <= 0:
            return 0
        stale = [str(record.id) for record in terminal[:excess]]
        pipeline = self._client.pipeline()
        pipeline.hdel(RECORDS_KEY, *stale)
        pipeline.zrem(ORDER_KEY, *stale)
        pipeline.execute()
        return len(stale)

    def shutdown(self, *, wait: bool = True) -> None:
        """Release the connection pool; queued work stays in Redis for a worker."""

        self._client.close()


def _dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _loads(raw: str) -> dict[str, Any]:
    import json

    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise RegistryError("job payload is not a JSON object")
    return loaded
