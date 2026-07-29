"""Strict contracts for before/after defense evaluations."""

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from aishield.attacks.contracts import AttackAlgorithm
from aishield.evaluation.contracts import BaselineEnvironment
from aishield.registry.contracts import Probability, RegistryModel, Sha256


class DefenseKind(StrEnum):
    """Preprocessing defenses implemented by the research baseline."""

    BIT_DEPTH = "bit_depth"


class DefenseConfig(RegistryModel):
    """Complete deterministic preprocessing-defense configuration."""

    kind: DefenseKind
    bit_depth: int = Field(default=4, ge=1, le=8)

    @model_validator(mode="after")
    def validate_kind_parameters(self) -> Self:
        if self.kind is not DefenseKind.BIT_DEPTH:
            raise ValueError(f"unsupported defense kind: {self.kind}")
        return self


class DefenseMetrics(RegistryModel):
    """Paired before/after metrics over one identical sample population."""

    clean_accuracy_before: Probability
    clean_accuracy_after: Probability
    robust_accuracy_before: Probability
    robust_accuracy_after: Probability
    attack_success_rate_before: Probability
    attack_success_rate_after: Probability
    evaluated_samples: int = Field(gt=0)
    adaptive_gradient_status: Literal["healthy", "flat"]


class DefenseRunRecord(RegistryModel):
    """Evidence for one preprocessing-defense evaluation."""

    id: UUID
    created_at: AwareDatetime
    model_version_id: UUID
    model_state_sha256: Sha256
    dataset_id: UUID
    dataset_manifest_sha256: Sha256
    defense: DefenseConfig
    attack_algorithm: AttackAlgorithm
    environment: BaselineEnvironment
    metrics: DefenseMetrics
    warnings: tuple[str, ...] = ()
