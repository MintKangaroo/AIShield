"""Typed registry records returned by the service and API."""

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Probability = Annotated[float, Field(ge=0.0, le=1.0)]


class RegistryModel(BaseModel):
    """Strict immutable base for registry records."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetName(StrEnum):
    """Built-in generated and approved-public dataset adapters."""

    SYNTHETIC = "synthetic"
    MNIST = "mnist"
    CIFAR10 = "cifar10"


class DatasetSplit(StrEnum):
    """Dataset partitions supported by built-in torchvision adapters."""

    TRAIN = "train"
    TEST = "test"


class ModelSource(StrEnum):
    """Implemented model adapter families."""

    SMALL_CNN = "small_cnn"
    TORCHVISION = "torchvision"
    TRAINED = "trained"


class DatasetRecord(RegistryModel):
    """Immutable identity and integrity metadata for a loaded dataset split."""

    id: UUID
    name: DatasetName
    version: str = Field(min_length=1, max_length=128)
    split: DatasetSplit
    source: Literal["approved_public", "generated"] = "approved_public"
    source_uri: str = Field(min_length=1)
    manifest_sha256: Sha256
    sample_count: int = Field(gt=0)
    num_classes: int = Field(gt=1)
    input_shape: tuple[int, int, int]
    transform: str = Field(min_length=1)
    torchvision_version: str = Field(min_length=1)


class ModelArtifactRecord(RegistryModel):
    """A safely loadable, content-addressed PyTorch state dictionary."""

    uri: str = Field(min_length=1)
    sha256: Sha256
    size_bytes: int = Field(gt=0)
    format: Literal["pytorch_state_dict"] = "pytorch_state_dict"


class ModelVersionRecord(RegistryModel):
    """Versioned model metadata bound to a state fingerprint and artifact."""

    id: UUID
    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    source: ModelSource
    framework: Literal["pytorch"] = "pytorch"
    framework_version: str = Field(min_length=1)
    torchvision_version: str | None = None
    architecture: str = Field(min_length=1, max_length=256)
    weights: str | None = None
    seed: int = Field(ge=0, le=4_294_967_295)
    num_classes: int = Field(gt=1)
    input_channels: int = Field(gt=0)
    parameter_count: int = Field(gt=0)
    state_dict_sha256: Sha256
    preprocessing: str = Field(min_length=1)
    device: Literal["cpu", "cuda"]
    artifact: ModelArtifactRecord


class EvaluationResult(RegistryModel):
    """Legacy lightweight compatibility result without detailed baseline evidence."""

    model_version_id: UUID
    dataset_id: UUID
    seed: int = Field(ge=0, le=4_294_967_295)
    evaluated_samples: int = Field(gt=0)
    clean_accuracy: Probability
    robust_accuracy: None = None
    robust_accuracy_status: Literal["not_evaluated"] = "not_evaluated"
    mean_loss: float = Field(ge=0.0)
