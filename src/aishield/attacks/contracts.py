"""Strict contracts for bounded adversarial evaluation runs."""

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from aishield.evaluation.contracts import BaselineEnvironment
from aishield.registry.contracts import Probability, RegistryModel, Sha256


class AttackAlgorithm(StrEnum):
    """Implemented bounded first-order attack algorithms."""

    FGSM = "fgsm"
    BIM = "bim"
    PGD = "pgd"
    DEEPFOOL = "deepfool"
    CARLINI_WAGNER = "cw"
    AUTOATTACK = "autoattack"
    APGD = "apgd"
    FAB = "fab"
    SQUARE = "square"


class AttackConfig(RegistryModel):
    """Complete and validated L-infinity attack configuration."""

    algorithm: AttackAlgorithm
    norm: Literal["linf", "l2"] = "linf"
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
        if self.algorithm is AttackAlgorithm.BIM and self.random_start:
            raise ValueError("BIM requires random_start=false; use PGD for randomized starts")
        if self.algorithm in (AttackAlgorithm.DEEPFOOL, AttackAlgorithm.CARLINI_WAGNER):
            if self.norm != "l2":
                raise ValueError("DeepFool and Carlini-Wagner require norm=l2")
        elif self.norm != "linf":
            raise ValueError("FGSM, BIM, PGD, AutoAttack, APGD, FAB, and Square require norm=linf")
        if self.algorithm is AttackAlgorithm.CARLINI_WAGNER and self.random_start:
            raise ValueError("Carlini-Wagner requires random_start=false")
        if self.algorithm is AttackAlgorithm.AUTOATTACK and self.random_start:
            raise ValueError("AutoAttack ensemble controls its own deterministic starts")
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
    maximum_observed_l2: float = Field(default=0.0, ge=0.0)
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


class RemoteAttackConfig(RegistryModel):
    """Bounded query-based black-box attack against a remote endpoint."""

    # "square" is score-based (needs a scores endpoint); "boundary" is
    # decision-based and needs only predicted labels (the harder, more realistic
    # case for a deployed classifier).
    algorithm: Literal["square", "boundary"] = "square"
    norm: Literal["linf"] = "linf"
    epsilon: float = Field(gt=0.0, le=1.0)
    max_queries: int = Field(gt=0, le=100_000)
    seed: int = Field(ge=0, le=4_294_967_295)
    batch_size: int = Field(gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)


class RemoteAttackMetrics(RegistryModel):
    """Paired clean/adversarial metrics plus the real query cost of the attack."""

    clean_accuracy: Probability
    robust_accuracy: Probability
    attack_success_rate: Probability
    evaluated_samples: int = Field(gt=0)
    clean_correct_samples: int = Field(ge=0)
    successful_attacks: int = Field(ge=0)
    maximum_observed_linf: float = Field(ge=0.0, le=1.0)
    total_queries: int = Field(ge=0)
    clean_prediction_sha256: Sha256
    adversarial_prediction_sha256: Sha256

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.clean_correct_samples > self.evaluated_samples:
            raise ValueError("clean-correct samples cannot exceed evaluated samples")
        if self.successful_attacks > self.clean_correct_samples:
            raise ValueError("successful attacks cannot exceed clean-correct samples")
        return self


class RemoteAttackRunRecord(RegistryModel):
    """Evidence for one authorized black-box attack on a remote model.

    The target is identified by host and a configuration fingerprint rather than a
    weight hash — a remote model exposes no state to hash. Secrets (auth headers,
    query strings) are never part of the record.
    """

    id: UUID
    created_at: AwareDatetime
    target_host: str = Field(min_length=1)
    target_fingerprint: Sha256
    dataset_id: UUID
    dataset_manifest_sha256: Sha256
    config: RemoteAttackConfig
    environment: BaselineEnvironment
    metrics: RemoteAttackMetrics
    authorized: Literal[True]
    warnings: tuple[str, ...] = ()
