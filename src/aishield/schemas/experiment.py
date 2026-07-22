"""Canonical, versioned experiment result contract for image-model evaluation."""

from enum import StrEnum
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
GitCommit = Annotated[str, StringConstraints(pattern=r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]


class ContractModel(BaseModel):
    """Base for strict result contracts that reject unknown fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RunStatus(StrEnum):
    """Lifecycle state shared by experiments and evaluation runs."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ArtifactKind(StrEnum):
    """Artifact categories expected across the first release."""

    MODEL = "model"
    DATASET_MANIFEST = "dataset_manifest"
    ORIGINAL_IMAGE = "original_image"
    PERTURBATION = "perturbation"
    ADVERSARIAL_IMAGE = "adversarial_image"
    CONFUSION_MATRIX = "confusion_matrix"
    REPORT = "report"
    LOG = "log"
    OTHER = "other"


class Dataset(ContractModel):
    """Immutable dataset identity and authorization record."""

    id: UUID
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    split: str = Field(min_length=1, max_length=64)
    source: Literal["local", "approved_public"]
    approved_for_research: Literal[True]
    manifest_sha256: Sha256
    sample_count: int = Field(gt=0)


class ModelArtifact(ContractModel):
    """Content-addressed model file."""

    id: UUID
    uri: str = Field(min_length=1)
    sha256: Sha256
    size_bytes: int = Field(gt=0)
    format: str = Field(min_length=1, max_length=64)


class ModelVersion(ContractModel):
    """Versioned model metadata bound to an immutable artifact."""

    id: UUID
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    framework: Literal["pytorch"]
    architecture: str = Field(min_length=1, max_length=256)
    artifact: ModelArtifact


class EnvironmentSnapshot(ContractModel):
    """Execution environment needed to reproduce an experiment."""

    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    package_versions: dict[str, str] = Field(min_length=1)
    git_commit: GitCommit | None = None
    container_image_digest: str | None = None
    device: Literal["cpu", "cuda"]
    cuda_version: str | None = None
    cudnn_version: str | None = None


class Experiment(ContractModel):
    """Top-level reproducible experiment identity."""

    id: UUID
    name: str = Field(min_length=1, max_length=200)
    status: RunStatus
    seed: int = Field(ge=0, le=4_294_967_295)
    dataset_id: UUID
    model_version_id: UUID
    created_at: AwareDatetime
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None


class AttackDefinition(ContractModel):
    """Named attack and its complete algorithm parameters."""

    id: UUID
    name: str = Field(min_length=1, max_length=128)
    implementation: str = Field(min_length=1, max_length=256)
    norm: Literal["linf", "l2", "l1"] | None = None
    targeted: bool
    parameters: dict[str, Any]


class AccuracyMetrics(ContractModel):
    """Required paired reporting for every attack evaluation."""

    clean_accuracy: Probability
    robust_accuracy: Probability
    attack_success_rate: Probability
    evaluated_samples: int = Field(gt=0)


class CleanBaseline(ContractModel):
    """Metrics produced by an unperturbed evaluation."""

    clean_accuracy: Probability
    mean_loss: NonNegativeFloat
    evaluated_samples: int = Field(gt=0)
    mean_inference_latency_ms: NonNegativeFloat
    precision_by_class: dict[int, Probability]
    recall_by_class: dict[int, Probability]
    confusion_matrix_artifact_id: UUID | None = None


class AttackRun(ContractModel):
    """One attack execution against the experiment model and dataset."""

    id: UUID
    experiment_id: UUID
    definition: AttackDefinition
    status: RunStatus
    seed: int = Field(ge=0, le=4_294_967_295)
    accuracy: AccuracyMetrics | None = None
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def require_metrics_after_success(self) -> Self:
        """A completed attack is invalid without clean and robust metrics."""

        if self.status is RunStatus.SUCCEEDED and self.accuracy is None:
            raise ValueError("a succeeded attack run requires paired accuracy metrics")
        return self


class DefenseDefinition(ContractModel):
    """Named defense with configuration required for adaptive reevaluation."""

    id: UUID
    name: str = Field(min_length=1, max_length=128)
    implementation: str = Field(min_length=1, max_length=256)
    parameters: dict[str, Any]


class DefenseRun(ContractModel):
    """Defense execution and paired before/after attack measurements."""

    id: UUID
    experiment_id: UUID
    definition: DefenseDefinition
    status: RunStatus
    attack_run_id: UUID | None = None
    before: AccuracyMetrics | None = None
    after: AccuracyMetrics | None = None
    adaptive_attack_evaluated: bool = False


class SampleResult(ContractModel):
    """Per-sample prediction outcome with links to comparison artifacts."""

    id: UUID
    experiment_id: UUID
    attack_run_id: UUID | None = None
    sample_index: int = Field(ge=0)
    true_label: int = Field(ge=0)
    clean_prediction: int = Field(ge=0)
    adversarial_prediction: int | None = Field(default=None, ge=0)
    attack_succeeded: bool | None = None
    artifact_ids: list[UUID] = Field(default_factory=list)


class Metric(ContractModel):
    """Raw scalar metric retained alongside any aggregate score."""

    id: UUID
    experiment_id: UUID
    name: str = Field(min_length=1, max_length=128)
    value: float
    unit: str = Field(min_length=1, max_length=64)
    attack_run_id: UUID | None = None
    defense_run_id: UUID | None = None
    class_label: int | None = Field(default=None, ge=0)


class Artifact(ContractModel):
    """Content-addressed experiment output."""

    id: UUID
    experiment_id: UUID
    kind: ArtifactKind
    uri: str = Field(min_length=1)
    sha256: Sha256
    media_type: str = Field(min_length=1, max_length=128)
    size_bytes: int = Field(ge=0)


class ScoreComponent(ContractModel):
    """Transparent contribution to a robustness score."""

    name: str = Field(min_length=1, max_length=128)
    raw_value: float
    normalized_value: Probability
    weight: Probability


class RobustnessScore(ContractModel):
    """Versioned aggregate whose formula and raw inputs remain inspectable."""

    version: str = Field(min_length=1, max_length=64)
    value: Probability
    formula: str = Field(min_length=1)
    components: list[ScoreComponent] = Field(min_length=1)
    raw_metric_ids: list[UUID] = Field(min_length=1)


class ExperimentResult(ContractModel):
    """Self-contained exchange envelope for one image-model experiment."""

    schema_version: Literal["1.0"] = "1.0"
    experiment: Experiment
    dataset: Dataset
    model: ModelVersion
    environment: EnvironmentSnapshot
    baseline: CleanBaseline | None = None
    attack_runs: list[AttackRun] = Field(default_factory=list)
    defense_runs: list[DefenseRun] = Field(default_factory=list)
    sample_results: list[SampleResult] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    robustness_score: RobustnessScore | None = None

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        """Reject envelopes that mix records from different experiments."""

        experiment_id = self.experiment.id
        if self.experiment.status is RunStatus.SUCCEEDED and self.baseline is None:
            raise ValueError("a succeeded experiment result requires a clean baseline")
        if self.dataset.id != self.experiment.dataset_id:
            raise ValueError("dataset does not match experiment.dataset_id")
        if self.model.id != self.experiment.model_version_id:
            raise ValueError("model does not match experiment.model_version_id")

        has_foreign_record = (
            any(record.experiment_id != experiment_id for record in self.attack_runs)
            or any(record.experiment_id != experiment_id for record in self.defense_runs)
            or any(record.experiment_id != experiment_id for record in self.sample_results)
            or any(record.experiment_id != experiment_id for record in self.metrics)
            or any(record.experiment_id != experiment_id for record in self.artifacts)
        )
        if has_foreign_record:
            raise ValueError("all result records must belong to the envelope experiment")

        artifact_ids = {artifact.id for artifact in self.artifacts}
        sample_artifact_ids = {
            artifact_id for sample in self.sample_results for artifact_id in sample.artifact_ids
        }
        baseline_artifact_ids = (
            {self.baseline.confusion_matrix_artifact_id}
            if self.baseline is not None and self.baseline.confusion_matrix_artifact_id is not None
            else set()
        )
        referenced_artifact_ids = sample_artifact_ids | baseline_artifact_ids
        if not referenced_artifact_ids <= artifact_ids:
            raise ValueError("sample result references an artifact missing from the envelope")
        return self
