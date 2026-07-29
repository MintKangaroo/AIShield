"""Transparent robustness score derived only from retained attack evidence."""

from uuid import UUID

from pydantic import Field

from aishield.attacks.contracts import AttackRunRecord
from aishield.registry.contracts import Probability, RegistryModel


class RobustnessScore(RegistryModel):
    """Versioned, explainable aggregate over attack robust accuracy."""

    formula_version: str = "mean-robust-accuracy-v1"
    model_version_id: UUID
    dataset_id: UUID
    attack_run_ids: tuple[UUID, ...] = Field(min_length=1)
    score: Probability
    evidence_coverage: Probability
    attacks_used: tuple[str, ...]
    warnings: tuple[str, ...] = ()


def calculate_score(runs: list[AttackRunRecord]) -> RobustnessScore:
    if not runs:
        raise ValueError("at least one attack run is required")
    model_id = runs[0].model_version_id
    dataset_id = runs[0].dataset_id
    if any(run.model_version_id != model_id or run.dataset_id != dataset_id for run in runs):
        raise ValueError("all attack runs must use the same model and dataset")
    supported = {"fgsm", "bim", "pgd", "deepfool", "cw", "autoattack", "apgd", "fab", "square"}
    coverage = len({run.config.algorithm.value for run in runs} & supported) / len(supported)
    warnings = (
        ("Score is an aggregate research aid, not a universal robustness guarantee.",)
        if coverage < 1.0
        else ()
    )
    return RobustnessScore(
        model_version_id=model_id,
        dataset_id=dataset_id,
        attack_run_ids=tuple(run.id for run in runs),
        score=sum(run.metrics.robust_accuracy for run in runs) / len(runs),
        evidence_coverage=coverage,
        attacks_used=tuple(run.config.algorithm.value for run in runs),
        warnings=warnings,
    )
