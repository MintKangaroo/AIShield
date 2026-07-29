"""Deterministic preprocessing-defense evaluation."""

from datetime import UTC, datetime
from uuid import uuid4

import torch
from torch import Tensor

from aishield.attacks.contracts import AttackConfig
from aishield.attacks.runner import run_adversarial_evaluation
from aishield.defenses.contracts import DefenseConfig, DefenseKind, DefenseMetrics, DefenseRunRecord
from aishield.evaluation.environment import capture_environment
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle


def _bit_depth(inputs: Tensor, bit_depth: int) -> Tensor:
    levels = float((1 << bit_depth) - 1)
    return (inputs.clamp(0.0, 1.0) * levels).round() / levels


def _defended_bundle(model_bundle: ModelBundle, config: DefenseConfig) -> ModelBundle:
    original_preprocess = model_bundle.preprocess

    def preprocess(inputs: Tensor) -> Tensor:
        if config.kind is not DefenseKind.BIT_DEPTH:
            raise RegistryError(f"unsupported defense kind: {config.kind}")
        return original_preprocess(_bit_depth(inputs, config.bit_depth))

    return ModelBundle(model=model_bundle.model, record=model_bundle.record, preprocess=preprocess)


def run_defense_evaluation(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    defense: DefenseConfig,
    attack: AttackConfig,
) -> DefenseRunRecord:
    """Compare a preprocessing defense before/after an adaptive attack."""

    before = run_adversarial_evaluation(model_bundle, dataset_bundle, config=attack)
    after = run_adversarial_evaluation(
        _defended_bundle(model_bundle, defense),
        dataset_bundle,
        config=attack,
    )
    warnings = list(after.warnings)
    if defense.kind is DefenseKind.BIT_DEPTH:
        warnings.append(
            "Bit-depth reduction is non-differentiable; interpret flat adaptive gradients "
            "as a gradient-masking diagnostic, not as robustness evidence."
        )
    return DefenseRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        model_version_id=model_bundle.record.id,
        model_state_sha256=model_bundle.record.state_dict_sha256,
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        defense=defense,
        attack_algorithm=attack.algorithm,
        environment=capture_environment(torch.device(model_bundle.record.device)),
        metrics=DefenseMetrics(
            clean_accuracy_before=before.metrics.clean_accuracy,
            clean_accuracy_after=after.metrics.clean_accuracy,
            robust_accuracy_before=before.metrics.robust_accuracy,
            robust_accuracy_after=after.metrics.robust_accuracy,
            attack_success_rate_before=before.metrics.attack_success_rate,
            attack_success_rate_after=after.metrics.attack_success_rate,
            evaluated_samples=before.metrics.evaluated_samples,
            adaptive_gradient_status=after.metrics.gradient_status,
        ),
        warnings=tuple(warnings),
    )
