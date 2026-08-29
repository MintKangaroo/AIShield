"""Contracts for adversarial training and TRADES runs."""

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from aishield.evaluation.contracts import BaselineEnvironment
from aishield.registry.contracts import ModelArtifactRecord, Probability, RegistryModel, Sha256


class TrainingStrategy(StrEnum):
    """Supported robust-training objectives."""

    ADVERSARIAL = "adversarial_training"
    TRADES = "trades"


class TrainingConfig(RegistryModel):
    """Deterministic CPU-friendly training configuration."""

    strategy: TrainingStrategy
    seed: int = Field(ge=0, le=4_294_967_295)
    epochs: int = Field(ge=1, le=100)
    batch_size: int = Field(gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)
    epsilon: float = Field(gt=0.0, le=1.0)
    step_size: float = Field(gt=0.0, le=1.0)
    attack_iterations: int = Field(ge=1, le=20)
    learning_rate: float = Field(gt=0.0, le=1.0)
    trades_beta: float = Field(default=6.0, ge=0.0, le=100.0)
    num_workers: Literal[0] = 0

    @model_validator(mode="after")
    def validate_attack_bounds(self) -> "TrainingConfig":
        if self.step_size > self.epsilon:
            raise ValueError("step_size must be less than or equal to epsilon")
        return self


class TrainingMetrics(RegistryModel):
    """Final training and paired robustness metrics."""

    epochs_completed: int = Field(gt=0)
    training_samples: int = Field(gt=0)
    final_training_loss: float = Field(ge=0.0)
    final_clean_accuracy: Probability
    final_robust_accuracy: Probability
    final_attack_success_rate: Probability


class TrainingRunRecord(RegistryModel):
    """Evidence and checkpoint identity for one robust-training run."""

    id: UUID
    created_at: AwareDatetime
    source_model_version_id: UUID
    trained_model_version_id: UUID
    dataset_id: UUID
    dataset_manifest_sha256: Sha256
    config: TrainingConfig
    model_state_sha256: Sha256
    artifact: ModelArtifactRecord
    environment: BaselineEnvironment
    metrics: TrainingMetrics
