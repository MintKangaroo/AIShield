"""Artifact garbage collection: reclaim files no retained record points to.

Artifacts accumulate — a checkpoint per model, a directory per baseline, plus the
occasional interrupted ``.tmp`` write. This sweep deletes only what nothing in the
registry references any more, so it can never remove a file a live record still
needs. It deliberately does not rewrite the append-only journal or delete records;
bounding the record set itself is a separate, backend-level concern.
"""

import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote, urlparse

logger = logging.getLogger("aishield.registry.gc")

#: Subdirectories under the artifact root the sweep is allowed to touch.
_SWEEPABLE = ("models", "baselines")


@dataclass
class GcReport:
    """What a sweep removed (or would remove, for a dry run)."""

    dry_run: bool
    removed_files: list[str] = field(default_factory=list)
    removed_dirs: list[str] = field(default_factory=list)
    reclaimed_bytes: int = 0
    skipped: list[str] = field(default_factory=list)

    @property
    def removed_count(self) -> int:
        return len(self.removed_files) + len(self.removed_dirs)


def uri_to_path(uri: str) -> Path | None:
    """Resolve a ``file://`` artifact URI to a local path, or None if not local."""

    parsed = urlparse(uri)
    if parsed.scheme not in ("file", ""):
        return None
    raw = unquote(parsed.path) if parsed.scheme == "file" else uri
    try:
        return Path(raw).resolve()
    except (OSError, ValueError):
        return None


def _dir_size(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file() and not child.is_symlink():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total


def collect_orphan_artifacts(
    artifact_root: Path,
    referenced: set[Path],
    *,
    dry_run: bool = False,
) -> GcReport:
    """Remove artifact files and baseline dirs not present in ``referenced``.

    A model checkpoint (``models/*.pt``) is a file; a baseline's outputs live in a
    directory (``baselines/<id>/``). A file whose resolved path is referenced is
    kept; a baseline directory is kept when any file inside it is referenced. An
    interrupted ``.tmp`` write is always an orphan. The journal is never touched.
    """

    report = GcReport(dry_run=dry_run)
    root = artifact_root.resolve()
    referenced_resolved = {p.resolve() for p in referenced}

    # Model checkpoints: one file each.
    models_dir = root / "models"
    if models_dir.is_dir():
        for entry in sorted(models_dir.iterdir()):
            if entry.is_symlink() or not entry.is_file():
                report.skipped.append(str(entry))
                continue
            if entry.resolve() in referenced_resolved:
                continue
            size = entry.stat().st_size if entry.is_file() else 0
            if not dry_run:
                entry.unlink(missing_ok=True)
            report.removed_files.append(str(entry))
            report.reclaimed_bytes += size

    # Baseline outputs: one directory each; keep it if anything inside is referenced.
    baselines_dir = root / "baselines"
    if baselines_dir.is_dir():
        for entry in sorted(baselines_dir.iterdir()):
            if entry.is_symlink() or not entry.is_dir():
                report.skipped.append(str(entry))
                continue
            files = {child.resolve() for child in entry.rglob("*") if child.is_file()}
            if files & referenced_resolved:
                continue
            size = _dir_size(entry)
            if not dry_run:
                _remove_tree(entry)
            report.removed_dirs.append(str(entry))
            report.reclaimed_bytes += size

    logger.info(
        "artifact gc completed",
        extra={
            "dry_run": dry_run,
            "removed": report.removed_count,
            "reclaimed_bytes": report.reclaimed_bytes,
        },
    )
    return report


def _remove_tree(path: Path) -> None:
    for child in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        try:
            if child.is_file() or child.is_symlink():
                child.unlink(missing_ok=True)
            elif child.is_dir():
                child.rmdir()
        except OSError:
            continue
    with contextlib.suppress(OSError):
        path.rmdir()
