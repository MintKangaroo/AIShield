"""Rebuild process state from the append-only metadata journal.

The registry index lives in process memory, so a restart loses it. The journal
already holds every record that was ever returned to a client, which makes it
the recovery source: run evidence is restored verbatim, and dataset/model
handles are rebuilt only when their recorded content hash still matches.
"""

from typing import Any

from aishield.registry.contracts import RegistryModel

#: Journal kinds this replay understands, in the order they must be restored.
REPLAYABLE_KINDS = (
    "dataset",
    "model",
    "baseline",
    "attack",
    "defense",
    "transfer",
    "training",
    "experiment",
)


class JournalReplaySummary(RegistryModel):
    """What one replay pass restored, and what it deliberately did not."""

    entries_read: int = 0
    datasets_restored: int = 0
    models_restored: int = 0
    baselines_restored: int = 0
    attacks_restored: int = 0
    defenses_restored: int = 0
    transfers_restored: int = 0
    training_restored: int = 0
    experiments_restored: int = 0
    jobs_skipped: int = 0
    skipped: tuple[str, ...] = ()

    @property
    def runs_restored(self) -> int:
        return (
            self.baselines_restored
            + self.attacks_restored
            + self.defenses_restored
            + self.transfers_restored
            + self.training_restored
        )


def group_entries(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group journal entries by kind, preserving append order within each kind.

    Later entries for the same record win because the journal is append-only and
    a repeated identity means the record was rewritten by a newer run.
    """

    grouped: dict[str, list[dict[str, Any]]] = {kind: [] for kind in REPLAYABLE_KINDS}
    for entry in entries:
        kind = entry.get("kind")
        record = entry.get("record")
        if isinstance(kind, str) and kind in grouped and isinstance(record, dict):
            grouped[kind].append(record)
    return grouped
