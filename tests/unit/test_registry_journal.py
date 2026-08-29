"""Durability contract for the append-only metadata journal."""

import json
import threading
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel

from aishield.registry.journal import RegistryJournal


class SampleRecord(BaseModel):
    id: str
    label: str


def test_append_writes_canonical_json_lines(tmp_path: Path) -> None:
    journal = RegistryJournal(tmp_path)

    journal.append("dataset", SampleRecord(id="a", label="first"))
    journal.append("model", SampleRecord(id="b", label="second"))

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    # Canonical form: sorted keys and no incidental whitespace.
    assert lines[0] == '{"kind":"dataset","record":{"id":"a","label":"first"}}'
    assert [entry["kind"] for entry in journal.read()] == ["dataset", "model"]


def test_read_preserves_append_order(tmp_path: Path) -> None:
    journal = RegistryJournal(tmp_path)
    labels = [f"record-{index:03d}" for index in range(200)]

    for label in labels:
        journal.append("baseline", SampleRecord(id=label, label=label))

    assert [entry["record"]["label"] for entry in journal.read()] == labels


def test_read_skips_corrupted_lines_without_losing_valid_ones(tmp_path: Path) -> None:
    journal = RegistryJournal(tmp_path)
    journal.append("dataset", SampleRecord(id="a", label="first"))
    with journal.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json at all\n")
        handle.write('"a bare string"\n')
        handle.write('{"kind":"model"}\n')  # missing the record object
    journal.append("model", SampleRecord(id="b", label="second"))

    entries = journal.read()

    assert [entry["record"]["id"] for entry in entries] == ["a", "b"]


def test_read_on_a_missing_journal_returns_no_entries(tmp_path: Path) -> None:
    assert RegistryJournal(tmp_path / "fresh").read() == []


def test_concurrent_appends_do_not_interleave(tmp_path: Path) -> None:
    journal = RegistryJournal(tmp_path)
    writers = 8
    per_writer = 40

    def write() -> None:
        for _ in range(per_writer):
            journal.append("attack", SampleRecord(id=str(uuid4()), label="concurrent"))

    threads = [threading.Thread(target=write) for _ in range(writers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    lines = journal.path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == writers * per_writer
    # Every line must still parse, which fails if two appends interleaved mid-write.
    assert all(json.loads(line)["kind"] == "attack" for line in lines)
