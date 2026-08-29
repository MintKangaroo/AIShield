"""PostgreSQL-backed metadata store for multi-process deployments.

The schema deliberately mirrors the journal: one append-only row per metadata
record, holding the same canonical JSON. That keeps the two backends behaviourally
identical and makes the migration verifiable — a journal can be replayed into the
database and produce the same registry state.

Identity columns are lifted out of the payload so a worker can filter by model or
dataset without scanning every row, but they are a projection of the payload, never
a second source of truth.
"""

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from aishield.registry.errors import RegistryError
from aishield.registry.store import indexable_fields

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy import Engine

logger = logging.getLogger("aishield.registry.postgres")

#: Bumped only when the table definition below changes incompatibly.
SCHEMA_VERSION = 1

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS registry_metadata (
    sequence          BIGSERIAL PRIMARY KEY,
    kind              TEXT        NOT NULL,
    record_id         UUID,
    model_version_id  UUID,
    dataset_id        UUID,
    recorded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload           JSONB       NOT NULL
)
"""

_CREATE_INDEXES = (
    "CREATE INDEX IF NOT EXISTS registry_metadata_kind_idx ON registry_metadata (kind)",
    "CREATE INDEX IF NOT EXISTS registry_metadata_record_idx"
    " ON registry_metadata (kind, record_id)",
    "CREATE INDEX IF NOT EXISTS registry_metadata_model_idx"
    " ON registry_metadata (model_version_id)",
    "CREATE INDEX IF NOT EXISTS registry_metadata_dataset_idx ON registry_metadata (dataset_id)",
)

_INSERT = """
INSERT INTO registry_metadata (kind, record_id, model_version_id, dataset_id, payload)
VALUES (:kind, :record_id, :model_version_id, :dataset_id, :payload)
"""

_SELECT_ALL = "SELECT kind, payload FROM registry_metadata ORDER BY sequence"


def create_engine(database_url: str, *, pool_size: int = 5) -> "Engine":
    """Build a SQLAlchemy engine, translating a missing driver into a clear error."""

    try:
        from sqlalchemy import create_engine as sqlalchemy_create_engine
    except ModuleNotFoundError as error:  # pragma: no cover - optional dependency
        raise RegistryError(
            "PostgreSQL metadata storage needs the 'postgres' extra: pip install -e \".[postgres]\""
        ) from error
    # psycopg3 is the supported driver; accept the bare scheme Compose already uses.
    url = database_url
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return sqlalchemy_create_engine(url, pool_size=pool_size, pool_pre_ping=True, future=True)


class PostgresMetadataStore:
    """Append registry metadata to a shared PostgreSQL table."""

    def __init__(self, database_url: str, *, pool_size: int = 5) -> None:
        from sqlalchemy import text

        self._text = text
        self._engine = create_engine(database_url, pool_size=pool_size)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create the table and indexes if this is the first process to connect."""

        from sqlalchemy.exc import SQLAlchemyError

        try:
            with self._engine.begin() as connection:
                connection.execute(self._text(_CREATE_TABLE))
                for statement in _CREATE_INDEXES:
                    connection.execute(self._text(statement))
        except SQLAlchemyError as error:
            raise RegistryError(f"could not prepare the metadata schema: {error}") from error
        logger.info("metadata schema ready", extra={"schema_version": SCHEMA_VERSION})

    def append(self, kind: str, record: BaseModel) -> None:
        """Write one record inside its own transaction, committed before returning."""

        from sqlalchemy.exc import SQLAlchemyError

        payload = record.model_dump(mode="json")
        record_id = payload.get("id")
        if not isinstance(record_id, str):
            # An experiment envelope carries its identity one level down.
            nested = payload.get("experiment")
            record_id = nested.get("id") if isinstance(nested, dict) else None
        indexed = indexable_fields(payload)
        try:
            with self._engine.begin() as connection:
                connection.execute(
                    self._text(_INSERT),
                    {
                        "kind": kind,
                        "record_id": record_id,
                        "model_version_id": indexed["model_version_id"],
                        "dataset_id": indexed["dataset_id"],
                        "payload": json.dumps(payload, sort_keys=True, separators=(",", ":")),
                    },
                )
        except SQLAlchemyError as error:
            raise RegistryError(f"could not persist {kind} metadata: {error}") from error

    def read(self) -> list[dict[str, Any]]:
        """Return every entry in insertion order, shaped like a journal read."""

        from sqlalchemy.exc import SQLAlchemyError

        try:
            with self._engine.connect() as connection:
                rows = connection.execute(self._text(_SELECT_ALL)).all()
        except SQLAlchemyError as error:
            raise RegistryError(f"could not read stored metadata: {error}") from error
        entries: list[dict[str, Any]] = []
        for kind, payload in rows:
            if isinstance(payload, dict):
                entries.append({"kind": kind, "record": payload})
        return entries

    def check_ready(self) -> None:
        """Confirm the database is reachable, so readiness never guesses."""

        from sqlalchemy.exc import SQLAlchemyError

        try:
            with self._engine.connect() as connection:
                connection.execute(self._text("SELECT 1"))
        except SQLAlchemyError as error:
            raise RegistryError(f"metadata database is unreachable: {error}") from error

    def close(self) -> None:
        self._engine.dispose()
