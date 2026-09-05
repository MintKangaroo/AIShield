"""Small bounded worker queue with a Redis-replaceable interface.

The queue is deliberately conservative: it refuses work rather than growing an
unbounded backlog, it evicts completed records so a long-lived process cannot
leak memory, and it reports worker failures as job evidence *and* as a logged
traceback.
"""

import logging
from collections.abc import Callable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from aishield.jobs.contracts import (
    JobNotCancellableError,
    JobQueueFullError,
    JobRecord,
    JobStatus,
)
from aishield.jobs.tasks import TaskDescriptor

logger = logging.getLogger("aishield.jobs")

#: Default number of queued-or-running jobs accepted before submissions are refused.
DEFAULT_MAX_PENDING = 16
#: Default number of terminal job records retained for status queries.
DEFAULT_RETAINED_JOBS = 256

JobObserver = Callable[[JobRecord], None]
#: Runs one described task and returns the identifier of the record it produced.
TaskExecutor = Callable[[TaskDescriptor], UUID | None]


class JobQueue:
    """Execute bounded background work and retain a queryable status record."""

    def __init__(
        self,
        executor: TaskExecutor,
        max_workers: int = 2,
        *,
        max_pending: int = DEFAULT_MAX_PENDING,
        retained_jobs: int = DEFAULT_RETAINED_JOBS,
        max_attempts: int = 1,
        observer: JobObserver | None = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        if max_pending < 1:
            raise ValueError("max_pending must be at least 1")
        if retained_jobs < 1:
            raise ValueError("retained_jobs must be at least 1")
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._run_task = executor
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="aishield")
        self._jobs: dict[UUID, JobRecord] = {}
        self._futures: dict[UUID, Future[UUID | None]] = {}
        self._max_pending = max_pending
        self._retained_jobs = retained_jobs
        self._max_attempts = max_attempts
        self._observer = observer
        self._tasks: dict[UUID, TaskDescriptor] = {}
        self._lock = RLock()

    @property
    def pending(self) -> int:
        """Jobs that are queued or already running."""

        with self._lock:
            return sum(1 for job in self._jobs.values() if not job.is_terminal)

    def submit(self, task: TaskDescriptor) -> JobRecord:
        """Accept one unit of background work, or refuse it when the backlog is full."""

        kind = task.kind.value
        job = JobRecord.queued(uuid4(), kind)
        with self._lock:
            pending = sum(1 for existing in self._jobs.values() if not existing.is_terminal)
            if pending >= self._max_pending:
                logger.warning(
                    "job rejected: queue is full",
                    extra={"job_kind": kind, "pending": pending, "max_pending": self._max_pending},
                )
                raise JobQueueFullError(
                    f"the worker queue already holds {pending} unfinished jobs; "
                    f"retry once one completes"
                )
            self._jobs[job.id] = job
            self._tasks[job.id] = task
            self._evict_terminal_jobs()
        self._publish(job)
        logger.info("job queued", extra={"job_id": str(job.id), "job_kind": kind})
        future = self._executor.submit(self._run, job.id, task)
        with self._lock:
            self._futures[job.id] = future
        future.add_done_callback(lambda completed: self._finish(job.id, completed))
        return job

    def _run(self, job_id: UUID, task: TaskDescriptor) -> UUID | None:
        with self._lock:
            attempts = self._jobs[job_id].attempts + 1
        started = self._transition(
            job_id, status=JobStatus.RUNNING, started_at=datetime.now(UTC), attempts=attempts
        )
        logger.info(
            "job started",
            extra={"job_id": str(job_id), "job_kind": started.kind, "attempt": attempts},
        )
        return self._run_task(task)

    def _finish(self, job_id: UUID, future: Future[UUID | None]) -> None:
        with self._lock:
            self._futures.pop(job_id, None)
        finished_at = datetime.now(UTC)
        try:
            result_id = future.result()
        except CancelledError:
            record = self._transition(job_id, status=JobStatus.CANCELLED, finished_at=finished_at)
            logger.info("job cancelled", extra={"job_id": str(job_id), "job_kind": record.kind})
        except Exception as error:  # noqa: BLE001 - persist worker failure as job evidence
            with self._lock:
                attempts = self._jobs[job_id].attempts
                task = self._tasks.get(job_id)
            if task is not None and attempts < self._max_attempts:
                # Retry: requeue the same task; a dead-letter only after exhaustion.
                record = self._transition(job_id, status=JobStatus.QUEUED, error=str(error))
                logger.warning(
                    "job failed; retrying",
                    extra={
                        "job_id": str(job_id),
                        "job_kind": record.kind,
                        "attempt": attempts,
                        "max_attempts": self._max_attempts,
                    },
                )
                self._publish(record)
                future = self._executor.submit(self._run, job_id, task)
                with self._lock:
                    self._futures[job_id] = future
                future.add_done_callback(lambda completed: self._finish(job_id, completed))
                return
            record = self._transition(
                job_id,
                status=JobStatus.FAILED,
                error=str(error),
                finished_at=finished_at,
            )
            logger.exception(
                "job dead-lettered",
                extra={"job_id": str(job_id), "job_kind": record.kind, "attempts": attempts},
            )
        else:
            record = self._transition(
                job_id,
                status=JobStatus.SUCCEEDED,
                result_id=result_id,
                finished_at=finished_at,
            )
            logger.info(
                "job succeeded",
                extra={
                    "job_id": str(job_id),
                    "job_kind": record.kind,
                    "result_id": str(result_id) if result_id else None,
                },
            )
        self._publish(record)

    def _transition(self, job_id: UUID, **update: object) -> JobRecord:
        with self._lock:
            record = self._jobs[job_id].model_copy(update=update)
            self._jobs[job_id] = record
            self._evict_terminal_jobs()
            return record

    def _evict_terminal_jobs(self) -> None:
        """Drop the oldest finished records once the retention limit is exceeded."""

        terminal = [job for job in self._jobs.values() if job.is_terminal]
        excess = len(terminal) - self._retained_jobs
        if excess <= 0:
            return
        for job in sorted(terminal, key=lambda item: item.created_at)[:excess]:
            del self._jobs[job.id]

    def _publish(self, record: JobRecord) -> None:
        if self._observer is None:
            return
        try:
            self._observer(record)
        except Exception:  # noqa: BLE001 - observability must not break the worker
            logger.exception("job observer failed", extra={"job_id": str(record.id)})

    def cancel(self, job_id: UUID) -> JobRecord:
        """Cancel a job that has not started yet; a running job is left alone."""

        with self._lock:
            record = self._jobs[job_id]
            if record.is_terminal:
                return record
            future = self._futures.get(job_id)
        if future is not None and future.cancel():
            # The done callback observes the cancellation and writes the record.
            return self.get(job_id)
        raise JobNotCancellableError(f"job {job_id} has already started and cannot be cancelled")

    def get(self, job_id: UUID) -> JobRecord:
        with self._lock:
            return self._jobs[job_id]

    def list(self) -> list[JobRecord]:
        with self._lock:
            return [self._jobs[key] for key in sorted(self._jobs, key=str)]

    def check_ready(self) -> None:
        """Always ready: the work runs on this process's own threads."""

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop accepting work and release worker threads."""

        self._executor.shutdown(wait=wait, cancel_futures=True)
