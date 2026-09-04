"""Drive a black-box attack against a remote endpoint and record the evidence.

Authorization (allowlist membership and explicit confirmation) is checked by the
service before this runs; this module assumes the target is already approved and
concerns itself with executing the attack and producing an honest record — the
same paired clean/robust/ASR metrics as a white-box run, plus the query cost and
the maximum perturbation actually observed.
"""

import hashlib
from datetime import UTC, datetime
from uuid import uuid4

import torch
from torch import Tensor
from torch.utils.data import DataLoader

from aishield.attacks.blackbox import evaluate_black_box, prediction_fingerprint
from aishield.attacks.contracts import (
    RemoteAttackConfig,
    RemoteAttackMetrics,
    RemoteAttackRunRecord,
)
from aishield.attacks.remote import RemoteEndpoint, RemoteImageClassifier
from aishield.evaluation.environment import capture_environment
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError


def target_fingerprint(endpoint: RemoteEndpoint, config: RemoteAttackConfig) -> str:
    """Stable, secret-free identity for a target so runs against it are groupable."""

    material = "\0".join(
        [
            "aishield-remote-target-v1",
            endpoint.host,
            str(endpoint.num_classes),
            config.algorithm,
            config.norm,
            f"{config.epsilon:.12g}",
            str(config.max_queries),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _batches(dataset: DatasetBundle, config: RemoteAttackConfig) -> list[tuple[Tensor, Tensor]]:
    loader = DataLoader(dataset.dataset, batch_size=config.batch_size, shuffle=False, num_workers=0)
    collected: list[tuple[Tensor, Tensor]] = []
    total = 0
    for raw_inputs, raw_targets in loader:
        if not isinstance(raw_inputs, Tensor) or not isinstance(raw_targets, Tensor):
            raise RegistryError("dataset batches must contain input and target tensors")
        remaining = config.max_samples - total if config.max_samples is not None else None
        if remaining is not None and remaining <= 0:
            break
        inputs = raw_inputs[:remaining] if remaining is not None else raw_inputs
        targets = raw_targets[:remaining] if remaining is not None else raw_targets
        inputs = inputs.to(dtype=torch.float32)
        targets = targets.to(dtype=torch.long)
        if targets.shape[0] == 0:
            continue
        if (
            not torch.isfinite(inputs).all()
            or float(inputs.min()) < 0.0
            or float(inputs.max()) > 1.0
        ):
            raise RegistryError("black-box evaluation requires finite inputs in [0, 1]")
        collected.append((inputs, targets))
        total += int(targets.shape[0])
    if not collected:
        raise RegistryError("dataset evaluation produced no samples")
    return collected


def run_remote_attack(
    dataset_bundle: DatasetBundle,
    endpoint: RemoteEndpoint,
    *,
    config: RemoteAttackConfig,
) -> RemoteAttackRunRecord:
    """Attack a remote classifier using only its scores and record the outcome."""

    if dataset_bundle.record.num_classes != endpoint.num_classes:
        raise RegistryError("dataset class count does not match the remote endpoint")

    classifier = RemoteImageClassifier(endpoint)
    batches = _batches(dataset_bundle, config)

    result = evaluate_black_box(
        classifier.score,
        batches,
        epsilon=config.epsilon,
        max_queries=config.max_queries,
        num_classes=endpoint.num_classes,
        seed=config.seed,
    )

    total = len(result.targets)
    clean_correct = sum(
        p == t for p, t in zip(result.clean_predictions, result.targets, strict=True)
    )
    robust_correct = sum(
        p == t for p, t in zip(result.adversarial_predictions, result.targets, strict=True)
    )
    successful = sum(
        clean == t and adversarial != t
        for clean, adversarial, t in zip(
            result.clean_predictions, result.adversarial_predictions, result.targets, strict=True
        )
    )

    metrics = RemoteAttackMetrics(
        clean_accuracy=clean_correct / total,
        robust_accuracy=robust_correct / total,
        attack_success_rate=successful / clean_correct if clean_correct else 0.0,
        evaluated_samples=total,
        clean_correct_samples=clean_correct,
        successful_attacks=successful,
        maximum_observed_linf=result.maximum_observed_linf,
        total_queries=result.total_queries,
        clean_prediction_sha256=prediction_fingerprint(result.targets, result.clean_predictions),
        adversarial_prediction_sha256=prediction_fingerprint(
            result.targets, result.adversarial_predictions
        ),
    )
    return RemoteAttackRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        target_host=endpoint.host,
        target_fingerprint=target_fingerprint(endpoint, config),
        dataset_id=dataset_bundle.record.id,
        dataset_manifest_sha256=dataset_bundle.record.manifest_sha256,
        config=config,
        environment=capture_environment(torch.device("cpu")),
        metrics=metrics,
        authorized=True,
        warnings=(
            "Black-box query attack against a remote endpoint; results depend on the "
            "query budget and reflect the deployed model as queried, not its weights.",
        ),
    )
