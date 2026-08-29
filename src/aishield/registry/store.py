"""Metadata persistence boundary shared by the journal and database backends.

Runtime handles (torch modules, dataset objects) are process-local by nature and
never cross this boundary. What crosses is the immutable evidence record: the
same canonical JSON the API returns to a client. Keeping one narrow protocol for
that lets the durable layer move from a local file to a shared database without
touching orchestration or evaluation code.
"""

from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from aishield.core.config import Settings

#: Keys lifted out of a record into typed columns so a store can filter on them.
INDEXED_FIELDS = ("model_version_id", "dataset_id")


def indexable_fields(payload: dict[str, Any]) -> dict[str, UUID | None]:
    """Extract the identity columns a store can index, ignoring absent ones."""

    fields: dict[str, UUID | None] = {}
    for name in INDEXED_FIELDS:
        value = payload.get(name)
        try:
            fields[name] = UUID(value) if isinstance(value, str) else None
        except ValueError:
            fields[name] = None
    return fields


@runtime_checkable
class MetadataStore(Protocol):
    """Append-only durable storage for registry metadata."""

    def append(self, kind: str, record: BaseModel) -> None:
        """Durably record one metadata entry before the API returns it."""
        ...

    def read(self) -> list[dict[str, Any]]:
        """Return every valid entry in append order, as ``{kind, record}`` dicts."""
        ...

    def close(self) -> None:
        """Release any resources the store holds."""
        ...

    def check_ready(self) -> None:
        """Raise ``RegistryError`` when the store cannot currently be written to."""
        ...


def build_metadata_store(settings: "Settings") -> MetadataStore:
    """Construct the configured metadata store.

    The journal is the default so the demo stack stays a single process with no
    server to run; PostgreSQL is opt-in for deployments that need several
    processes to share one registry.
    """

    from aishield.registry.journal import RegistryJournal

    if settings.metadata_backend == "postgresql":
        from aishield.registry.postgres import PostgresMetadataStore

        return PostgresMetadataStore(settings.database_url, pool_size=settings.database_pool_size)
    return RegistryJournal(settings.artifact_root)
