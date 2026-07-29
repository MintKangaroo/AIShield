"""Numerically bounded FGSM and PGD evaluation over registered tensors."""

import hashlib
from datetime import UTC, datetime
from typing import Literal, cast
from uuid import uuid4

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

from aishield.attacks.contracts import (
    AttackConfig,
    AttackMetrics,
    AttackRunRecord,
)
from aishield.evaluation.environment import capture_environment
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle
from aishield.registry.reproducibility import set_global_seed

BOUND_TOLERANCE = 1e-6


def _fingerprint(targets: list[int], predictions: list[int]) -> str:
    digest = hashlib.sha256(b"aishield-attack-predictions-v1\0")
    for target, prediction in zip(targets, predictions, strict=True):
        digest.update(target.to_bytes(8, "big", signed=True))
        digest.update(prediction.to_bytes(8, "big", signed=True))
    return digest.hexdigest()


def _validate_compatibility(model: ModelBundle, dataset: DatasetBundle) -> None:
    if model.record.input_channels != dataset.record.input_shape[0]:
        raise RegistryError("model input channels do not match the dataset")
    if model.record.num_classes != dataset.record.num_classes:
        raise RegistryError("model class count does not match the dataset")


def _validate_batch(inputs: Tensor, targets: Tensor, class_count: int) -> None:
    if not torch.isfinite(inputs).all():
        raise RegistryError("dataset inputs must be finite")
    minimum = float(inputs.min().item())
    maximum = float(inputs.max().item())
    if minimum < 0.0 or maximum > 1.0:
        raise RegistryError("adversarial evaluation requires raw inputs in the [0, 1] range")
    if targets.ndim != 1 or any(
        target < 0 or target >= class_count for target in targets.detach().cpu().tolist()
    ):
        raise RegistryError("dataset target is outside the registered class range")


def _gradient(
    adversarial: Tensor,
    targets: Tensor,
    model_bundle: ModelBundle,
    loss_function: nn.CrossEntropyLoss,
) -> Tensor:
    candidate = adversarial.detach().requires_grad_(True)
    logits = cast(Tensor, model_bundle.model(model_bundle.preprocess(candidate)))
    if logits.ndim != 2 or logits.shape != (targets.shape[0], model_bundle.record.num_classes):
        raise RegistryError("model output is not a compatible class-logit tensor")
    loss = loss_function(logits, targets)
    gradient_result = torch.autograd.grad(
        loss,
        candidate,
        only_inputs=True,
        allow_unused=True,
    )[0]
    gradient = gradient_result if gradient_result is not None else torch.zeros_like(candidate)
    if not torch.isfinite(gradient).all():
        raise RegistryError("attack gradient contains a non-finite value")
    return gradient


def _attack_batch(
    clean_inputs: Tensor,
    targets: Tensor,
    model_bundle: ModelBundle,
    config: AttackConfig,
    loss_function: nn.CrossEntropyLoss,
) -> tuple[Tensor, bool]:
    if config.random_start:
        noise = torch.empty_like(clean_inputs).uniform_(-config.epsilon, config.epsilon)
        adversarial = (clean_inputs + noise).clamp(0.0, 1.0)
    else:
        adversarial = clean_inputs.clone()

    saw_nonzero_gradient = False
    for _ in range(config.iterations):
        gradient = _gradient(adversarial, targets, model_bundle, loss_function)
        saw_nonzero_gradient = saw_nonzero_gradient or bool(torch.count_nonzero(gradient).item())
        adversarial = adversarial.detach() + config.step_size * gradient.sign()
        delta = (adversarial - clean_inputs).clamp(-config.epsilon, config.epsilon)
        adversarial = (clean_inputs + delta).clamp(0.0, 1.0).detach()

    observed_linf = float((adversarial - clean_inputs).abs().amax().item())
    if observed_linf > config.epsilon + BOUND_TOLERANCE:
        raise RegistryError("generated adversarial input exceeded the configured L-infinity bound")
    return adversarial, saw_nonzero_gradient


def run_adversarial_evaluation(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    config: AttackConfig,
) -> AttackRunRecord:
    """Run one bounded attack and retain paired clean/robust evidence."""

    _validate_compatibility(model_bundle, dataset_bundle)
    set_global_seed(config.seed)
    generator = torch.Generator().manual_seed(config.seed)
    loader = DataLoader(
        dataset_bundle.dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=0,
        generator=generator,
    )
    model = model_bundle.model
    model.eval()
    device = torch.device(model_bundle.record.device)
    loss_function = nn.CrossEntropyLoss()
    class_count = model_bundle.record.num_classes

    all_targets: list[int] = []
    all_clean_predictions: list[int] = []
    all_adversarial_predictions: list[int] = []
    total = 0
    clean_correct = 0
    robust_correct = 0
    successful_attacks = 0
    maximum_observed_linf = 0.0
    saw_nonzero_gradient = False

    for raw_inputs, raw_targets in loader:
        if not isinstance(raw_inputs, Tensor) or not isinstance(raw_targets, Tensor):
            raise RegistryError("dataset batches must contain input and target tensors")
        remaining = config.max_samples - total if config.max_samples is not None else None
        if remaining is not None and remaining <= 0:
            break
        clean_inputs = raw_inputs[:remaining] if remaining is not None else raw_inputs
        targets = raw_targets[:remaining] if remaining is not None else raw_targets
        clean_inputs = clean_inputs.to(device=device, dtype=torch.float32)
        targets = targets.to(device=device, dtype=torch.long)
        if targets.shape[0] == 0:
            continue
        _validate_batch(clean_inputs, targets, class_count)

        with torch.inference_mode():
            clean_logits = cast(Tensor, model(model_bundle.preprocess(clean_inputs)))
        if clean_logits.ndim != 2 or clean_logits.shape != (targets.shape[0], class_count):
            raise RegistryError("model output is not a compatible class-logit tensor")
        clean_predictions = clean_logits.argmax(dim=1)

        adversarial, batch_has_gradient = _attack_batch(
            clean_inputs,
            targets,
            model_bundle,
            config,
            loss_function,
        )
        saw_nonzero_gradient = saw_nonzero_gradient or batch_has_gradient
        with torch.inference_mode():
            adversarial_logits = cast(Tensor, model(model_bundle.preprocess(adversarial)))
        adversarial_predictions = adversarial_logits.argmax(dim=1)

        clean_correct_mask = clean_predictions == targets
        adversarial_correct_mask = adversarial_predictions == targets
        clean_correct += int(clean_correct_mask.sum().item())
        robust_correct += int(adversarial_correct_mask.sum().item())
        successful_attacks += int((clean_correct_mask & ~adversarial_correct_mask).sum().item())
        maximum_observed_linf = max(
            maximum_observed_linf,
            float((adversarial - clean_inputs).abs().amax().item()),
        )

        batch_targets = [int(value) for value in targets.detach().cpu().tolist()]
        batch_clean = [int(value) for value in clean_predictions.detach().cpu().tolist()]
        batch_adversarial = [
            int(value) for value in adversarial_predictions.detach().cpu().tolist()
        ]
        all_targets.extend(batch_targets)
        all_clean_predictions.extend(batch_clean)
        all_adversarial_predictions.extend(batch_adversarial)
        total += int(targets.shape[0])

    if total == 0:
        raise RegistryError("dataset evaluation produced no samples")

    gradient_status: Literal["healthy", "flat"] = "healthy" if saw_nonzero_gradient else "flat"
    warnings = (
        (
            (
                "All observed input gradients were zero; investigate gradient masking or "
                "non-differentiable preprocessing."
            ),
        )
        if gradient_status == "flat"
        else ()
    )
    metrics = AttackMetrics(
        clean_accuracy=clean_correct / total,
        robust_accuracy=robust_correct / total,
        attack_success_rate=successful_attacks / clean_correct if clean_correct else 0.0,
        evaluated_samples=total,
        clean_correct_samples=clean_correct,
        successful_attacks=successful_attacks,
        maximum_observed_linf=maximum_observed_linf,
        clean_prediction_sha256=_fingerprint(all_targets, all_clean_predictions),
        adversarial_prediction_sha256=_fingerprint(all_targets, all_adversarial_predictions),
        gradient_status=gradient_status,
    )
    return AttackRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        model_version_id=model_bundle.record.id,
        model_state_sha256=model_bundle.record.state_dict_sha256,
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        config=config,
        environment=capture_environment(device),
        metrics=metrics,
        warnings=warnings,
    )
