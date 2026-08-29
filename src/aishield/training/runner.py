"""Deterministic adversarial-training and TRADES execution."""

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid4, uuid5

import torch
from torch import Tensor, nn
from torch.nn import functional as F
from torch.utils.data import DataLoader

from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.attacks.runner import run_adversarial_evaluation
from aishield.evaluation.environment import capture_environment
from aishield.registry.contracts import ModelArtifactRecord, ModelSource, ModelVersionRecord
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle
from aishield.registry.reproducibility import set_global_seed, sha256_file, state_dict_sha256
from aishield.training.contracts import TrainingConfig, TrainingMetrics, TrainingRunRecord


def _inner_pgd(
    model_bundle: ModelBundle,
    inputs: Tensor,
    targets: Tensor,
    config: TrainingConfig,
) -> Tensor:
    adversarial = inputs.detach().clone()
    for _ in range(config.attack_iterations):
        candidate = adversarial.detach().requires_grad_(True)
        logits = cast(Tensor, model_bundle.model(model_bundle.preprocess(candidate)))
        loss = F.cross_entropy(logits, targets)
        gradient = torch.autograd.grad(loss, candidate, only_inputs=True)[0]
        if not torch.isfinite(gradient).all():
            raise RegistryError("training attack gradient contains a non-finite value")
        adversarial = candidate.detach() + config.step_size * gradient.sign()
        delta = (adversarial - inputs).clamp(-config.epsilon, config.epsilon)
        adversarial = (inputs + delta).clamp(0.0, 1.0)
    return adversarial.detach()


def _store_checkpoint(model: nn.Module, artifact_root: Path, state_sha: str) -> ModelArtifactRecord:
    model_root = artifact_root / "models"
    model_root.mkdir(parents=True, exist_ok=True)
    destination = model_root / f"trained-{state_sha}.pt"
    torch.save(model.state_dict(), destination)
    return ModelArtifactRecord(
        uri=destination.resolve().as_uri(),
        sha256=sha256_file(destination),
        size_bytes=destination.stat().st_size,
    )


def train_model(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    artifact_root: Path,
    config: TrainingConfig,
) -> tuple[ModelBundle, TrainingRunRecord]:
    """Train a copied model with adversarial training or TRADES."""

    set_global_seed(config.seed)
    model = copy.deepcopy(model_bundle.model).train()
    device = torch.device(model_bundle.record.device)
    model.to(device)
    loader = DataLoader(
        dataset_bundle.dataset,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=config.num_workers,
        generator=torch.Generator().manual_seed(config.seed),
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
    total_samples = 0
    final_loss = 0.0
    epochs_completed = 0
    training_bundle = ModelBundle(
        model=model, record=model_bundle.record, preprocess=model_bundle.preprocess
    )

    for _ in range(config.epochs):
        for raw_inputs, raw_targets in loader:
            remaining = (
                config.max_samples - total_samples if config.max_samples is not None else None
            )
            if remaining is not None and remaining <= 0:
                break
            inputs = raw_inputs[:remaining] if remaining is not None else raw_inputs
            targets = raw_targets[:remaining] if remaining is not None else raw_targets
            inputs = inputs.to(device=device, dtype=torch.float32)
            targets = targets.to(device=device, dtype=torch.long)
            if inputs.shape[0] == 0:
                continue
            adversarial = _inner_pgd(training_bundle, inputs, targets, config)
            clean_logits = cast(Tensor, model(model_bundle.preprocess(inputs)))
            adversarial_logits = cast(Tensor, model(model_bundle.preprocess(adversarial)))
            if config.strategy.value == "trades":
                loss = F.cross_entropy(clean_logits, targets) + config.trades_beta * F.kl_div(
                    F.log_softmax(adversarial_logits, dim=1),
                    F.softmax(clean_logits.detach(), dim=1),
                    reduction="batchmean",
                )
            else:
                loss = F.cross_entropy(adversarial_logits, targets)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()  # type: ignore[no-untyped-call]
            optimizer.step()
            final_loss = float(loss.detach().item())
            total_samples += int(inputs.shape[0])
        epochs_completed += 1
        if config.max_samples is not None and total_samples >= config.max_samples:
            break

    model.eval()
    state_sha = state_dict_sha256(model.state_dict())
    artifact = _store_checkpoint(model, artifact_root, state_sha)
    trained_record = ModelVersionRecord(
        id=uuid5(NAMESPACE_URL, f"aishield:trained:{state_sha}"),
        name=f"{model_bundle.record.name} ({config.strategy.value})",
        version=f"trained-{config.strategy.value}-v1",
        source=ModelSource.TRAINED,
        framework_version=model_bundle.record.framework_version,
        torchvision_version=model_bundle.record.torchvision_version,
        architecture=model_bundle.record.architecture,
        seed=config.seed,
        num_classes=model_bundle.record.num_classes,
        input_channels=model_bundle.record.input_channels,
        parameter_count=model_bundle.record.parameter_count,
        state_dict_sha256=state_sha,
        preprocessing=model_bundle.record.preprocessing,
        device=model_bundle.record.device,
        artifact=artifact,
    )
    trained_bundle = ModelBundle(
        model=model, record=trained_record, preprocess=model_bundle.preprocess
    )
    final_attack = run_adversarial_evaluation(
        trained_bundle,
        dataset_bundle,
        config=AttackConfig(
            algorithm=AttackAlgorithm.PGD,
            epsilon=config.epsilon,
            step_size=config.step_size,
            iterations=config.attack_iterations,
            random_start=False,
            seed=config.seed,
            batch_size=config.batch_size,
            max_samples=config.max_samples,
        ),
    )
    metrics = TrainingMetrics(
        epochs_completed=epochs_completed,
        training_samples=total_samples,
        final_training_loss=final_loss,
        final_clean_accuracy=final_attack.metrics.clean_accuracy,
        final_robust_accuracy=final_attack.metrics.robust_accuracy,
        final_attack_success_rate=final_attack.metrics.attack_success_rate,
    )
    run = TrainingRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        source_model_version_id=model_bundle.record.id,
        trained_model_version_id=trained_record.id,
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        config=config,
        model_state_sha256=state_sha,
        artifact=artifact,
        environment=capture_environment(device),
        metrics=metrics,
    )
    return trained_bundle, run
