"""Deterministic clean baseline execution and same-seed verification."""

import hashlib
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

import numpy as np
import torch
from torch import Tensor, nn
from torch.utils.data import DataLoader

from aishield.evaluation.artifacts import write_baseline_artifacts
from aishield.evaluation.contracts import (
    BaselineConfig,
    BaselineEvidence,
    BaselineRunRecord,
    BaselineVerification,
    CleanBaselineMetrics,
    LatencyMetrics,
    PerClassMetric,
    ReproducibilityCheck,
)
from aishield.evaluation.environment import capture_environment
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle
from aishield.registry.reproducibility import set_global_seed

Clock = Callable[[], int]
LOSS_ABSOLUTE_TOLERANCE = 1e-12


def _validate_compatibility(model: ModelBundle, dataset: DatasetBundle) -> None:
    if model.record.input_channels != dataset.record.input_shape[0]:
        raise RegistryError("model input channels do not match the dataset")
    if model.record.num_classes != dataset.record.num_classes:
        raise RegistryError("model class count does not match the dataset")


def _synchronize(device: torch.device) -> None:
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def _prediction_fingerprint(targets: list[int], predictions: list[int]) -> str:
    digest = hashlib.sha256(b"aishield-clean-predictions-v1\0")
    for target, prediction in zip(targets, predictions, strict=True):
        digest.update(target.to_bytes(8, "big", signed=True))
        digest.update(prediction.to_bytes(8, "big", signed=True))
    return digest.hexdigest()


def _class_metrics(
    confusion_matrix: list[list[int]],
) -> tuple[PerClassMetric, ...]:
    records: list[PerClassMetric] = []
    class_count = len(confusion_matrix)
    for class_index in range(class_count):
        true_positive = confusion_matrix[class_index][class_index]
        predicted_positive = sum(row[class_index] for row in confusion_matrix)
        support = sum(confusion_matrix[class_index])
        records.append(
            PerClassMetric(
                class_index=class_index,
                precision=true_positive / predicted_positive if predicted_positive else 0.0,
                recall=true_positive / support if support else 0.0,
                support=support,
            )
        )
    return tuple(records)


def _percentile(values: list[float], percentile: float) -> float:
    return float(np.percentile(np.asarray(values, dtype=np.float64), percentile))


def _prepare_batch(
    raw_inputs: object,
    raw_targets: object,
    model_bundle: ModelBundle,
    device: torch.device,
    remaining: int | None,
) -> tuple[Tensor, Tensor]:
    if not isinstance(raw_inputs, Tensor) or not isinstance(raw_targets, Tensor):
        raise RegistryError("dataset batches must contain input and target tensors")
    inputs = raw_inputs[:remaining] if remaining is not None else raw_inputs
    targets = raw_targets[:remaining] if remaining is not None else raw_targets
    inputs = model_bundle.preprocess(inputs.to(device))
    targets = targets.to(device=device, dtype=torch.long)
    return inputs, targets


def _warm_up(
    loader: DataLoader[tuple[Tensor, Tensor]],
    model_bundle: ModelBundle,
    device: torch.device,
    warmup_batches: int,
) -> None:
    if warmup_batches == 0:
        return
    try:
        raw_inputs, raw_targets = next(iter(loader))
    except StopIteration as error:
        raise RegistryError("dataset evaluation produced no samples") from error
    inputs, _ = _prepare_batch(raw_inputs, raw_targets, model_bundle, device, None)
    with torch.inference_mode():
        for _ in range(warmup_batches):
            model_bundle.model(inputs)
    _synchronize(device)


def _evaluate(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    config: BaselineConfig,
    clock: Clock,
) -> CleanBaselineMetrics:
    generator = torch.Generator().manual_seed(config.seed)
    loader: DataLoader[tuple[Tensor, Tensor]] = DataLoader(
        dataset_bundle.dataset,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
        generator=generator,
    )
    model = model_bundle.model
    model.eval()
    device = torch.device(model_bundle.record.device)
    loss_function = nn.CrossEntropyLoss(reduction="sum")
    _warm_up(loader, model_bundle, device, config.warmup_batches)

    class_count = model_bundle.record.num_classes
    confusion_matrix = [[0 for _ in range(class_count)] for _ in range(class_count)]
    all_targets: list[int] = []
    all_predictions: list[int] = []
    per_sample_latency_ms: list[float] = []
    total_forward_ms = 0.0
    total_loss = 0.0
    total = 0

    with torch.inference_mode():
        for raw_inputs, raw_targets in loader:
            remaining = config.max_samples - total if config.max_samples is not None else None
            if remaining is not None and remaining <= 0:
                break
            inputs, targets = _prepare_batch(
                raw_inputs,
                raw_targets,
                model_bundle,
                device,
                remaining,
            )
            if targets.shape[0] == 0:
                continue
            _synchronize(device)
            started = clock()
            logits = cast(Tensor, model(inputs))
            _synchronize(device)
            elapsed_ms = (clock() - started) / 1_000_000

            if (
                logits.ndim != 2
                or logits.shape[0] != targets.shape[0]
                or logits.shape[1] != class_count
            ):
                raise RegistryError("model output is not a compatible class-logit tensor")
            predictions = logits.argmax(dim=1)
            batch_targets = [int(value) for value in targets.detach().cpu().tolist()]
            batch_predictions = [int(value) for value in predictions.detach().cpu().tolist()]
            if any(target < 0 or target >= class_count for target in batch_targets):
                raise RegistryError("dataset target is outside the registered class range")

            total_loss += float(loss_function(logits, targets).item())
            total_forward_ms += elapsed_ms
            per_sample_latency_ms.append(elapsed_ms / targets.shape[0])
            all_targets.extend(batch_targets)
            all_predictions.extend(batch_predictions)
            for target, prediction in zip(batch_targets, batch_predictions, strict=True):
                confusion_matrix[target][prediction] += 1
            total += int(targets.shape[0])

    if total == 0:
        raise RegistryError("dataset evaluation produced no samples")
    correct = sum(
        target == prediction
        for target, prediction in zip(all_targets, all_predictions, strict=True)
    )
    return CleanBaselineMetrics(
        clean_accuracy=correct / total,
        mean_loss=total_loss / total,
        evaluated_samples=total,
        confusion_matrix=tuple(tuple(row) for row in confusion_matrix),
        per_class=_class_metrics(confusion_matrix),
        latency=LatencyMetrics(
            warmup_batches=config.warmup_batches,
            measured_batches=len(per_sample_latency_ms),
            total_forward_ms=total_forward_ms,
            mean_ms_per_sample=total_forward_ms / total,
            p50_ms_per_sample=_percentile(per_sample_latency_ms, 50),
            p95_ms_per_sample=_percentile(per_sample_latency_ms, 95),
        ),
        prediction_sha256=_prediction_fingerprint(all_targets, all_predictions),
    )


def run_clean_baseline(
    model_bundle: ModelBundle,
    dataset_bundle: DatasetBundle,
    *,
    artifact_root: Path,
    config: BaselineConfig,
    clock: Clock = time.perf_counter_ns,
) -> BaselineRunRecord:
    """Evaluate clean data, snapshot the environment, and persist artifacts."""

    _validate_compatibility(model_bundle, dataset_bundle)
    set_global_seed(config.seed)
    metrics = _evaluate(model_bundle, dataset_bundle, config, clock)
    evidence = BaselineEvidence(
        id=uuid4(),
        created_at=datetime.now(UTC),
        model_version_id=model_bundle.record.id,
        model_state_sha256=model_bundle.record.state_dict_sha256,
        model_artifact_sha256=model_bundle.record.artifact.sha256,
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        config=config,
        environment=capture_environment(torch.device(model_bundle.record.device)),
        metrics=metrics,
    )
    artifacts = write_baseline_artifacts(evidence, artifact_root)
    return BaselineRunRecord(**evidence.model_dump(), artifacts=artifacts)


def _check(name: str, passed: bool, detail: str) -> ReproducibilityCheck:
    return ReproducibilityCheck(name=name, passed=passed, detail=detail)


def verify_baseline_rerun(
    reference: BaselineRunRecord,
    rerun: BaselineRunRecord,
    *,
    loss_absolute_tolerance: float = LOSS_ABSOLUTE_TOLERANCE,
) -> BaselineVerification:
    """Compare deterministic evidence while excluding wall-clock latency."""

    loss_difference = abs(reference.metrics.mean_loss - rerun.metrics.mean_loss)
    checks = (
        _check(
            "configuration",
            reference.config == rerun.config,
            "seed, batch size, sample bound, warm-up, and worker count must match",
        ),
        _check(
            "model_state",
            reference.model_state_sha256 == rerun.model_state_sha256,
            "canonical model state SHA-256 must match",
        ),
        _check(
            "dataset_manifest",
            reference.dataset_manifest_sha256 == rerun.dataset_manifest_sha256,
            "dataset manifest SHA-256 must match",
        ),
        _check(
            "environment",
            reference.environment == rerun.environment,
            "runtime versions, device, and deterministic settings must match",
        ),
        _check(
            "prediction_fingerprint",
            reference.metrics.prediction_sha256 == rerun.metrics.prediction_sha256,
            "ordered clean targets and predictions must match",
        ),
        _check(
            "confusion_matrix",
            reference.metrics.confusion_matrix == rerun.metrics.confusion_matrix,
            "all per-class prediction counts must match",
        ),
        _check(
            "clean_accuracy",
            reference.metrics.clean_accuracy == rerun.metrics.clean_accuracy,
            "clean accuracy must match exactly",
        ),
        _check(
            "mean_loss",
            loss_difference <= loss_absolute_tolerance,
            f"absolute loss difference {loss_difference:.3e} must be <= "
            f"{loss_absolute_tolerance:.3e}",
        ),
    )
    return BaselineVerification(
        reference_run_id=reference.id,
        rerun=rerun,
        reproducible=all(check.passed for check in checks),
        loss_absolute_tolerance=loss_absolute_tolerance,
        checks=checks,
    )
