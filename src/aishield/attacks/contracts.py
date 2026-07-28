"""Strict contracts for bounded adversarial evaluation runs."""

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from aishield.evaluation.contracts import BaselineEnvironment
from aishield.registry.contracts import Probability, RegistryModel, Sha256


class AttackAlgorithm(StrEnum):
    """Implemented first-order attack algorithms."""

    FGSM = "fgsm"
    PGD = "pgd"


class AttackConfig(RegistryModel):
    """Complete and validated L-infinity attack configuration."""

    algorithm: AttackAlgorithm
    norm: Literal["linf"] = "linf"
    epsilon: float = Field(gt=0.0, le=1.0)
    step_size: float = Field(gt=0.0, le=1.0)
    iterations: int = Field(ge=1, le=100)
    random_start: bool
    targeted: Literal[False] = False
    seed: int = Field(ge=0, le=4_294_967_295)
    batch_size: int = Field(gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)

    @model_validator(mode="after")
    def validate_algorithm_parameters(self) -> Self:
        """Reject ambiguous or misleading algorithm configurations."""

        if self.step_size > self.epsilon:
            raise ValueError("attack step_size must not exceed epsilon")
        if self.algorithm is AttackAlgorithm.FGSM and (
            self.iterations != 1 or self.random_start or abs(self.step_size - self.epsilon) > 1e-12
        ):
            raise ValueError(
                "FGSM requires one iteration, no random start, and step_size equal to epsilon"
            )
        return self


class AttackMetrics(RegistryModel):
    """Paired clean/adversarial metrics over the same eligible population."""

    clean_accuracy: Probability
    robust_accuracy: Probability
    attack_success_rate: Probability
    evaluated_samples: int = Field(gt=0)
    clean_correct_samples: int = Field(ge=0)
    successful_attacks: int = Field(ge=0)
    maximum_observed_linf: float = Field(ge=0.0, le=1.0)
    clean_prediction_sha256: Sha256
    adversarial_prediction_sha256: Sha256
    gradient_status: Literal["healthy", "flat"]

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        """Keep raw attack counts aligned with the reported population."""

        if self.clean_correct_samples > self.evaluated_samples:
            raise ValueError("clean-correct samples cannot exceed evaluated samples")
        if self.successful_attacks > self.clean_correct_samples:
            raise ValueError("successful attacks cannot exceed clean-correct samples")
        return self


class AttackRunRecord(RegistryModel):
    """Self-contained evidence for one bounded adversarial evaluation."""

    id: UUID
    created_at: AwareDatetime
    model_version_id: UUID
    model_state_sha256: Sha256
    dataset_id: UUID
    dataset_manifest_sha256: Sha256
    config: AttackConfig
    environment: BaselineEnvironment
    metrics: AttackMetrics
    warnings: tuple[str, ...] = ()
