"""Selection of the background job backend.

Both backends present the same surface to the registry, so the API code does not
know whether the work runs on its own threads or in a separate process.
"""

from typing import TYPE_CHECKING, Protocol, runtime_checkable
from uuid import UUID

from aishield.jobs.contracts import JobRecord
from aishield.jobs.tasks import TaskDescriptor

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aishield.core.config import Settings
    from aishield.jobs.queue import JobObserver, TaskExecutor


@runtime_checkable
class JobBackend(Protocol):
    """Accept background work and report on it, wherever it actually runs."""

    def submit(self, task: TaskDescriptor) -> JobRecord: ...

    def get(self, job_id: UUID) -> JobRecord: ...

    def list(self) -> list[JobRecord]: ...

    def cancel(self, job_id: UUID) -> JobRecord: ...

    def check_ready(self) -> None: ...

    def shutdown(self, *, wait: bool = True) -> None: ...


def build_job_backend(
    settings: "Settings",
    executor: "TaskExecutor",
    observer: "JobObserver | None" = None,
) -> JobBackend:
    """Construct the configured backend.

    The in-process queue is the default so the demo stack stays one container.
    The executor is only used by that backend; a Redis worker resolves the task
    itself, which is precisely what moves the compute out of the API process.
    The observer records each transition this process observes as audit evidence.
    """

    if settings.job_backend == "redis":
        from aishield.jobs.redis_queue import RedisJobQueue

        return RedisJobQueue(
            settings.redis_url,
            max_pending=settings.job_max_pending,
            retained_jobs=settings.job_retained_records,
            max_attempts=settings.job_max_attempts,
            observer=observer,
        )

    from aishield.jobs.queue import JobQueue

    return JobQueue(
        executor,
        max_workers=settings.job_max_workers,
        max_pending=settings.job_max_pending,
        retained_jobs=settings.job_retained_records,
        max_attempts=settings.job_max_attempts,
        observer=observer,
    )
