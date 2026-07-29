"""Deterministic preprocessing-defense evaluation."""

from datetime import UTC, datetime
from typing import cast
from uuid import uuid4

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

from aishield.attacks.contracts import AttackConfig
from aishield.attacks.runner import _attack_batch, run_adversarial_evaluation
from aishield.defenses.contracts import (
    DefenseConfig,
    DefenseKind,
    DefenseMetrics,
    DefenseRunRecord,
    TransferDefenseMetrics,
    TransferDefenseRunRecord,
)
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


def run_transfer_evaluation(
    surrogate: ModelBundle,
    target: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    attack: AttackConfig,
) -> TransferDefenseRunRecord:
    """Generate perturbations on a surrogate and measure transfer on target."""

    if surrogate.record.input_channels != target.record.input_channels:
        raise RegistryError("surrogate and target input channels must match")
    if surrogate.record.num_classes != target.record.num_classes:
        raise RegistryError("surrogate and target class counts must match")
    loader = DataLoader(dataset_bundle.dataset, batch_size=attack.batch_size, shuffle=False)
    source = surrogate.model.eval()
    destination = target.model.eval()
    device = torch.device(target.record.device)
    loss = nn.CrossEntropyLoss()
    total = clean_correct = robust_correct = successful = 0
    max_linf = 0.0
    for raw_inputs, raw_targets in loader:
        remaining = attack.max_samples - total if attack.max_samples is not None else None
        if remaining is not None and remaining <= 0:
            break
        inputs = raw_inputs[:remaining] if remaining is not None else raw_inputs
        targets = raw_targets[:remaining] if remaining is not None else raw_targets
        inputs = inputs.to(device=device, dtype=torch.float32)
        targets = targets.to(device=device, dtype=torch.long)
        with torch.inference_mode():
            clean_logits = cast(Tensor, destination(target.preprocess(inputs)))
        source_bundle = ModelBundle(
            model=source, record=surrogate.record, preprocess=surrogate.preprocess
        )
        adversarial, _ = _attack_batch(inputs, targets, source_bundle, attack, loss)
        with torch.inference_mode():
            adversarial_logits = cast(Tensor, destination(target.preprocess(adversarial)))
        clean_predictions = clean_logits.argmax(dim=1)
        adversarial_predictions = adversarial_logits.argmax(dim=1)
        clean_mask = clean_predictions == targets
        clean_correct += int(clean_mask.sum().item())
        robust_correct += int((adversarial_predictions == targets).sum().item())
        successful += int((clean_mask & (adversarial_predictions != targets)).sum().item())
        max_linf = max(max_linf, float((adversarial - inputs).abs().amax().item()))
        total += int(targets.shape[0])
    if total == 0:
        raise RegistryError("transfer evaluation produced no samples")
    return TransferDefenseRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        surrogate_model_version_id=surrogate.record.id,
        target_model_version_id=target.record.id,
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        attack=attack,
        environment=capture_environment(device),
        metrics=TransferDefenseMetrics(
            clean_accuracy=clean_correct / total,
            transferred_robust_accuracy=robust_correct / total,
            transfer_attack_success_rate=successful / clean_correct if clean_correct else 0.0,
            evaluated_samples=total,
            clean_correct_samples=clean_correct,
            successful_transfers=successful,
            maximum_observed_linf=max_linf,
        ),
        warnings=("Transfer strength depends on surrogate-target similarity.",),
    )
