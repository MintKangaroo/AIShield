"""Typed clean-baseline records retained by the evaluation service."""

from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from aishield.registry.contracts import Probability, RegistryModel, Sha256

GitCommit = Annotated[str, StringConstraints(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")]


class BaselineArtifactKind(StrEnum):
    """Artifacts emitted by a clean baseline run."""

    REPORT = "baseline_report"
    CONFUSION_MATRIX = "confusion_matrix"


class BaselineConfig(RegistryModel):
    """Complete execution parameters for a clean baseline."""

    seed: int = Field(ge=0, le=4_294_967_295)
    batch_size: int = Field(gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=10_000_000)
    warmup_batches: int = Field(default=1, ge=0, le=100)
    num_workers: Literal[0] = 0


class PerClassMetric(RegistryModel):
    """Precision and recall for one numeric class."""

    class_index: int = Field(ge=0)
    precision: Probability
    recall: Probability
    support: int = Field(ge=0)


class LatencyMetrics(RegistryModel):
    """Forward-pass latency measured after explicit warm-up."""

    warmup_batches: int = Field(ge=0)
    measured_batches: int = Field(gt=0)
    total_forward_ms: float = Field(ge=0.0)
    mean_ms_per_sample: float = Field(ge=0.0)
    p50_ms_per_sample: float = Field(ge=0.0)
    p95_ms_per_sample: float = Field(ge=0.0)
    includes_preprocessing: Literal[False] = False


class CleanBaselineMetrics(RegistryModel):
    """All raw clean metrics required before attack evaluation."""

    clean_accuracy: Probability
    robust_accuracy: None = None
    robust_accuracy_status: Literal["not_evaluated"] = "not_evaluated"
    mean_loss: float = Field(ge=0.0)
    evaluated_samples: int = Field(gt=0)
    confusion_matrix: tuple[tuple[int, ...], ...]
    per_class: tuple[PerClassMetric, ...]
    latency: LatencyMetrics
    prediction_sha256: Sha256

    @model_validator(mode="after")
    def validate_class_dimensions(self) -> Self:
        """Require a square matrix aligned with the per-class records."""

        class_count = len(self.per_class)
        if class_count < 2:
            raise ValueError("clean baseline requires at least two classes")
        if len(self.confusion_matrix) != class_count or any(
            len(row) != class_count for row in self.confusion_matrix
        ):
            raise ValueError("confusion matrix must be square and match per-class metrics")
        if tuple(metric.class_index for metric in self.per_class) != tuple(range(class_count)):
            raise ValueError("per-class metrics must cover contiguous class indices")
        if sum(sum(row) for row in self.confusion_matrix) != self.evaluated_samples:
            raise ValueError("confusion matrix count must match evaluated samples")
        return self


class BaselineEnvironment(RegistryModel):
    """Runtime versions and device details required to reproduce the run."""

    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    package_versions: dict[str, str] = Field(min_length=1)
    git_commit: GitCommit | None = None
    container_image_digest: str | None = None
    device: Literal["cpu", "cuda"]
    cuda_version: str | None = None
    cudnn_version: str | None = None
    deterministic_algorithms: Literal[True] = True


class BaselineArtifact(RegistryModel):
    """Content-addressed output from a baseline run."""

    id: UUID
    kind: BaselineArtifactKind
    uri: str = Field(min_length=1)
    sha256: Sha256
    media_type: Literal["application/json", "image/png"]
    size_bytes: int = Field(gt=0)


class BaselineEvidence(RegistryModel):
    """Self-contained evidence written to the baseline JSON report."""

    id: UUID
    created_at: AwareDatetime
    model_version_id: UUID
    model_state_sha256: Sha256
    model_artifact_sha256: Sha256
    dataset_id: UUID
    dataset_manifest_sha256: Sha256
    config: BaselineConfig
    environment: BaselineEnvironment
    metrics: CleanBaselineMetrics


class BaselineRunRecord(BaselineEvidence):
    """Baseline evidence plus content-addressed generated artifacts."""

    artifacts: tuple[BaselineArtifact, ...] = Field(min_length=2)


class ReproducibilityCheck(RegistryModel):
    """One transparent same-seed rerun comparison."""

    name: str = Field(min_length=1)
    passed: bool
    detail: str = Field(min_length=1)


class BaselineVerification(RegistryModel):
    """Comparison between a stored baseline and an exact-configuration rerun."""

    reference_run_id: UUID
    rerun: BaselineRunRecord
    reproducible: bool
    loss_absolute_tolerance: float = Field(ge=0.0)
    checks: tuple[ReproducibilityCheck, ...] = Field(min_length=1)
    excluded_from_pass_fail: tuple[Literal["latency"], ...] = ("latency",)
