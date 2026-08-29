"""One behavioural contract that every metadata store backend must satisfy.

The journal and the database are meant to be interchangeable. Running the same
assertions against both is what makes that claim checkable, and it is what a
future migration relies on: a journal replayed into PostgreSQL must reconstruct
the same registry state.
"""

import os
import threading
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import BaseModel

from aishield.core.config import Settings
from aishield.registry.journal import RegistryJournal
from aishield.registry.store import MetadataStore, build_metadata_store, indexable_fields

POSTGRES_URL = os.environ.get("AISHIELD_TEST_DATABASE_URL")
requires_postgres = pytest.mark.skipif(
    not POSTGRES_URL, reason="set AISHIELD_TEST_DATABASE_URL to run PostgreSQL store tests"
)


class SampleRecord(BaseModel):
    id: str
    model_version_id: str | None = None
    dataset_id: str | None = None
    label: str = "sample"


def _postgres_store() -> Iterator[MetadataStore]:
    from sqlalchemy import text

    from aishield.registry.postgres import PostgresMetadataStore, create_engine

    assert POSTGRES_URL is not None
    engine = create_engine(POSTGRES_URL)
    store = PostgresMetadataStore(POSTGRES_URL)
    # Each test starts from an empty table so ordering assertions are meaningful.
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE registry_metadata"))
    try:
        yield store
    finally:
        store.close()
        engine.dispose()


@pytest.fixture(params=["journal", "postgresql"])
def store(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[MetadataStore]:
    if request.param == "journal":
        yield RegistryJournal(tmp_path)
        return
    if not POSTGRES_URL:
        pytest.skip("set AISHIELD_TEST_DATABASE_URL to run PostgreSQL store tests")
    yield from _postgres_store()


def test_empty_store_reads_no_entries(store: MetadataStore) -> None:
    assert store.read() == []


def test_appended_record_round_trips(store: MetadataStore) -> None:
    record = SampleRecord(id=str(uuid4()), label="first")

    store.append("dataset", record)
    entries = store.read()

    assert len(entries) == 1
    assert entries[0]["kind"] == "dataset"
    assert entries[0]["record"]["id"] == record.id
    assert entries[0]["record"]["label"] == "first"


def test_entries_are_returned_in_append_order(store: MetadataStore) -> None:
    labels = [f"record-{index:03d}" for index in range(50)]

    for label in labels:
        store.append("baseline", SampleRecord(id=str(uuid4()), label=label))

    assert [entry["record"]["label"] for entry in store.read()] == labels


def test_kinds_are_preserved_independently(store: MetadataStore) -> None:
    for kind in ("dataset", "model", "attack", "attack"):
        store.append(kind, SampleRecord(id=str(uuid4())))

    kinds = [entry["kind"] for entry in store.read()]

    assert kinds == ["dataset", "model", "attack", "attack"]


def test_the_store_is_append_only(store: MetadataStore) -> None:
    """Writing the same identity twice keeps both rows: history is never rewritten."""

    identity = str(uuid4())
    store.append("model", SampleRecord(id=identity, label="before"))
    store.append("model", SampleRecord(id=identity, label="after"))

    labels = [entry["record"]["label"] for entry in store.read()]

    assert labels == ["before", "after"]


def test_concurrent_appends_are_all_recorded(store: MetadataStore) -> None:
    writers = 6
    per_writer = 20

    def write() -> None:
        for _ in range(per_writer):
            store.append("attack", SampleRecord(id=str(uuid4())))

    threads = [threading.Thread(target=write) for _ in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    entries = store.read()
    assert len(entries) == writers * per_writer
    assert all(isinstance(entry["record"], dict) for entry in entries)


def test_close_is_safe_to_call(store: MetadataStore) -> None:
    store.append("dataset", SampleRecord(id=str(uuid4())))

    store.close()


def test_every_backend_satisfies_the_protocol(store: MetadataStore) -> None:
    assert isinstance(store, MetadataStore)


def test_indexable_fields_extracts_present_identities() -> None:
    model_id, dataset_id = str(uuid4()), str(uuid4())

    fields = indexable_fields({"model_version_id": model_id, "dataset_id": dataset_id})

    assert str(fields["model_version_id"]) == model_id
    assert str(fields["dataset_id"]) == dataset_id


def test_indexable_fields_tolerates_missing_or_invalid_values() -> None:
    fields = indexable_fields({"model_version_id": "not-a-uuid"})

    assert fields["model_version_id"] is None
    assert fields["dataset_id"] is None


def test_factory_defaults_to_the_journal(tmp_path: Path) -> None:
    settings = Settings(environment="test", artifact_root=tmp_path)

    built = build_metadata_store(settings)

    assert isinstance(built, RegistryJournal)


@requires_postgres
def test_factory_builds_the_configured_database_store(tmp_path: Path) -> None:
    from aishield.registry.postgres import PostgresMetadataStore

    assert POSTGRES_URL is not None
    settings = Settings(
        environment="test",
        artifact_root=tmp_path,
        metadata_backend="postgresql",
        database_url=POSTGRES_URL,
    )

    built = build_metadata_store(settings)

    try:
        assert isinstance(built, PostgresMetadataStore)
    finally:
        built.close()


@requires_postgres
def test_database_store_reports_an_unreachable_server() -> None:
    from aishield.registry.errors import RegistryError
    from aishield.registry.postgres import PostgresMetadataStore

    with pytest.raises(RegistryError, match="could not prepare the metadata schema"):
        PostgresMetadataStore("postgresql://aishield:aishield@127.0.0.1:1/aishield")


def test_ready_store_passes_its_readiness_check(store: MetadataStore) -> None:
    store.check_ready()


@requires_postgres
def test_a_closed_database_store_reports_itself_unready() -> None:
    from aishield.registry.errors import RegistryError
    from aishield.registry.postgres import PostgresMetadataStore, create_engine

    assert POSTGRES_URL is not None
    store = PostgresMetadataStore(POSTGRES_URL)
    # Repoint the pool at a port nothing listens on to simulate a lost server.
    store._engine.dispose()
    store._engine = create_engine("postgresql://aishield:aishield@127.0.0.1:1/aishield")

    with pytest.raises(RegistryError, match="unreachable"):
        store.check_ready()
