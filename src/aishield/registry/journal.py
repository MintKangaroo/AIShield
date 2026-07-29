"""Append-only metadata journal used as a lightweight persistence boundary."""

import json
from pathlib import Path
from threading import Lock
from typing import Any

from pydantic import BaseModel


class RegistryJournal:
    """Durably append registry metadata without persisting live torch objects."""

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
