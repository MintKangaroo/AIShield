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


class JobRecord(RegistryModel):
    id: UUID
    kind: str = Field(min_length=1, max_length=64)
    status: JobStatus
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None
    result_id: UUID | None = None
    error: str | None = None

    @classmethod
    def queued(cls, job_id: UUID, kind: str) -> "JobRecord":
        return cls(id=job_id, kind=kind, status=JobStatus.QUEUED, created_at=datetime.now(UTC))
