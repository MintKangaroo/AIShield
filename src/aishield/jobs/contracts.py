"""Job status records shared by API and worker adapters."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import AwareDatetime, Field

from aishield.registry.contracts import RegistryModel


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Statuses a worker will never transition out of.
TERMINAL_STATUSES = frozenset({JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED})


class JobRecord(RegistryModel):
    id: UUID
    kind: str = Field(min_length=1, max_length=64)
    status: JobStatus
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    result_id: UUID | None = None
    error: str | None = None
    # How many times execution has been attempted; a retry increments this.
    attempts: int = Field(default=0, ge=0, le=100)

    @classmethod
    def queued(cls, job_id: UUID, kind: str) -> "JobRecord":
        return cls(id=job_id, kind=kind, status=JobStatus.QUEUED, created_at=datetime.now(UTC))

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


class JobQueueFullError(RuntimeError):
    """Raised when accepting another job would exceed the configured backlog."""


class JobNotCancellableError(RuntimeError):
    """Raised when a job has already started and cannot be cancelled safely."""
