"""Append-only metadata journal: the default, dependency-free metadata store."""

import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel

from aishield.registry.errors import RegistryError


class RegistryJournal:
    """Durably append registry metadata without persisting live torch objects.

    This is one implementation of :class:`~aishield.registry.store.MetadataStore`.
    It needs no server, which keeps the default demo stack a single process.
    """

    def __init__(self, root: Path) -> None:
        self.path = root / "registry" / "journal.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def append(self, kind: str, record: BaseModel) -> None:
        payload: dict[str, Any] = {"kind": kind, "record": record.model_dump(mode="json")}
        line = json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()

    def read(self) -> list[dict[str, Any]]:
        """Read valid journal entries in append order."""

        if not self.path.exists():
            return []
        entries: list[dict[str, Any]] = []
        with self._lock, self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict) and isinstance(payload.get("record"), dict):
                    entries.append(payload)
        return entries

    def close(self) -> None:
        """Nothing to release: every append is flushed as it is written."""

    def check_ready(self) -> None:
        """Confirm the journal directory is writable; there is no server to reach."""

        if not os.access(self.path.parent, os.W_OK):
            raise RegistryError(f"journal directory is not writable: {self.path.parent}")
