"""Minimal model evaluation used to validate registry compatibility."""

from typing import cast

import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

from aishield.registry.contracts import EvaluationResult
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle
from aishield.registry.reproducibility import set_global_seed


def evaluate_registered_model(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    seed: int,
    batch_size: int,
    max_samples: int | None,
) -> EvaluationResult:
    """Return basic clean accuracy and loss without detailed baseline artifacts."""

    if batch_size <= 0:
        raise RegistryError("batch_size must be positive")
    if max_samples is not None and max_samples <= 0:
        raise RegistryError("max_samples must be positive when provided")
    if model_bundle.record.input_channels != dataset_bundle.record.input_shape[0]:
        raise RegistryError("model input channels do not match the dataset")
    if model_bundle.record.num_classes != dataset_bundle.record.num_classes:
        raise RegistryError("model class count does not match the dataset")

    set_global_seed(seed)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        dataset_bundle.dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        generator=generator,
    )
    loss_function = nn.CrossEntropyLoss(reduction="sum")
    model = model_bundle.model
    model.eval()
    device = torch.device(model_bundle.record.device)
    correct = 0
    total = 0
    total_loss = 0.0

    with torch.inference_mode():
        for raw_inputs, raw_targets in loader:
            inputs = cast(Tensor, raw_inputs)
            targets = cast(Tensor, raw_targets)
            if max_samples is not None:
                remaining = max_samples - total
                if remaining <= 0:
                    break
                inputs = inputs[:remaining]
                targets = targets[:remaining]
            inputs = model_bundle.preprocess(inputs.to(device))
            targets = targets.to(device=device, dtype=torch.long)
            logits = cast(Tensor, model(inputs))
            if logits.ndim != 2 or logits.shape[1] != model_bundle.record.num_classes:
                raise RegistryError("model output is not a compatible class-logit tensor")
            total_loss += float(loss_function(logits, targets).item())
            correct += int((logits.argmax(dim=1) == targets).sum().item())
            total += int(targets.shape[0])

    if total == 0:
        raise RegistryError("dataset evaluation produced no samples")
    return EvaluationResult(
        model_version_id=model_bundle.record.id,
        dataset_id=dataset_bundle.record.id,
        seed=seed,
        evaluated_samples=total,
        clean_accuracy=correct / total,
        mean_loss=total_loss / total,
    )
