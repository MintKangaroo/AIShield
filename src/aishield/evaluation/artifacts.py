"""Atomic JSON and matplotlib artifact generation for clean baselines."""

import json
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import matplotlib

matplotlib.use("Agg")

from matplotlib import pyplot as plt  # noqa: E402

from aishield.evaluation.contracts import (
    BaselineArtifact,
    BaselineArtifactKind,
    BaselineEvidence,
)
from aishield.registry.reproducibility import sha256_file


def _artifact_record(
    run_id: UUID,
    path: Path,
    kind: BaselineArtifactKind,
    media_type: Literal["application/json", "image/png"],
) -> BaselineArtifact:
    digest = sha256_file(path)
    return BaselineArtifact(
        id=uuid5(NAMESPACE_URL, f"aishield:baseline-artifact:{run_id}:{kind.value}:{digest}"),
        kind=kind,
        uri=path.resolve().as_uri(),
        sha256=digest,
        media_type=media_type,
        size_bytes=path.stat().st_size,
    )


def write_baseline_report(evidence: BaselineEvidence, run_directory: Path) -> BaselineArtifact:
    """Write stable, sorted JSON evidence using an atomic rename."""

    destination = run_directory / "baseline.json"
    temporary = run_directory / f".baseline.{uuid4().hex}.tmp"
    payload = json.dumps(
        evidence.model_dump(mode="json"),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    try:
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return _artifact_record(
        evidence.id,
        destination,
        BaselineArtifactKind.REPORT,
        "application/json",
    )


def write_confusion_matrix(
    evidence: BaselineEvidence,
    run_directory: Path,
) -> BaselineArtifact:
    """Render the raw confusion matrix as a publication-friendly PNG."""

    matrix = evidence.metrics.confusion_matrix
    class_count = len(matrix)
    figure_size = max(6.0, min(12.0, class_count * 0.72))
    figure, axis = plt.subplots(figsize=(figure_size, figure_size))
    image = axis.imshow(matrix, interpolation="nearest", cmap="viridis")
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04, label="samples")
    axis.set(
        title="AIShield clean baseline confusion matrix",
        xlabel="Predicted class",
        ylabel="True class",
        xticks=range(class_count),
        yticks=range(class_count),
    )
    threshold = max(max(row) for row in matrix) / 2 if matrix else 0
    if class_count <= 20:
        for row_index, row in enumerate(matrix):
            for column_index, count in enumerate(row):
                axis.text(
                    column_index,
                    row_index,
                    str(count),
                    ha="center",
                    va="center",
                    color="white" if count <= threshold else "black",
                    fontsize=8,
                )
    figure.tight_layout()

    destination = run_directory / "confusion-matrix.png"
    temporary = run_directory / f".confusion-matrix.{uuid4().hex}.tmp"
    try:
        figure.savefig(
            temporary,
            format="png",
            dpi=160,
            metadata={"Software": "AIShield"},
        )
        temporary.replace(destination)
    finally:
        plt.close(figure)
        temporary.unlink(missing_ok=True)
    return _artifact_record(
        evidence.id,
        destination,
        BaselineArtifactKind.CONFUSION_MATRIX,
        "image/png",
    )


def write_baseline_artifacts(
    evidence: BaselineEvidence,
    artifact_root: Path,
) -> tuple[BaselineArtifact, BaselineArtifact]:
    """Create the machine-readable report and confusion matrix image."""

    run_directory = artifact_root / "baselines" / str(evidence.id)
    run_directory.mkdir(parents=True, exist_ok=False)
    report = write_baseline_report(evidence, run_directory)
    confusion_matrix = write_confusion_matrix(evidence, run_directory)
    return report, confusion_matrix
