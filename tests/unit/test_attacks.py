from pathlib import Path
from typing import cast
from uuid import UUID

import pytest
import torch
from torch import Tensor, nn
from torch.utils.data import TensorDataset

from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.attacks.runner import run_adversarial_evaluation
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    ModelArtifactRecord,
    ModelSource,
    ModelVersionRecord,
)
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle, identity_preprocess


class ThresholdClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.linear = nn.Linear(1, 2)
        with torch.no_grad():
            self.linear.weight.copy_(torch.tensor([[-10.0], [10.0]]))
            self.linear.bias.copy_(torch.tensor([5.0, -5.0]))

    def forward(self, inputs: Tensor) -> Tensor:
        return cast(Tensor, self.linear(inputs.flatten(start_dim=1)))


class FlatClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.anchor = nn.Parameter(torch.zeros(1))

    def forward(self, inputs: Tensor) -> Tensor:
        logits = torch.zeros(inputs.shape[0], 2, device=inputs.device)
        return logits + self.anchor * 0


def attack_bundles(
    tmp_path: Path,
    *,
    model: nn.Module | None = None,
    inputs: Tensor | None = None,
) -> tuple[ModelBundle, DatasetBundle]:
    actual_model = model or ThresholdClassifier()
    actual_inputs = (
        inputs
        if inputs is not None
        else torch.tensor([0.1, 0.2, 0.8, 0.9], dtype=torch.float32).reshape(4, 1, 1, 1)
    )
    targets = torch.tensor([0, 0, 1, 1])
    model_record = ModelVersionRecord(
        id=UUID("00000000-0000-4000-8000-000000000301"),
        name="threshold classifier",
        version="fixture-v1",
        source=ModelSource.SMALL_CNN,
        framework_version=torch.__version__,
        architecture=actual_model.__class__.__name__,
        seed=1729,
        num_classes=2,
        input_channels=1,
        parameter_count=sum(parameter.numel() for parameter in actual_model.parameters()),
        state_dict_sha256="a" * 64,
        preprocessing="identity",
        device="cpu",
        artifact=ModelArtifactRecord(
            uri=(tmp_path / "model.pt").resolve().as_uri(),
            sha256="b" * 64,
            size_bytes=1,
        ),
    )
    dataset_record = DatasetRecord(
        id=UUID("00000000-0000-4000-8000-000000000302"),
        name=DatasetName.SYNTHETIC,
        version="fixture-v1",
        split=DatasetSplit.TEST,
        source="generated",
        source_uri="aishield://generated/test",
        manifest_sha256="c" * 64,
        sample_count=4,
        num_classes=2,
        input_shape=(1, 1, 1),
        transform="identity",
        torchvision_version="fixture",
    )
    return (
        ModelBundle(model=actual_model.eval(), record=model_record, preprocess=identity_preprocess),
        DatasetBundle(
            dataset=TensorDataset(actual_inputs, targets),
            record=dataset_record,
        ),
    )


@pytest.mark.parametrize(
    ("algorithm", "step_size", "iterations"),
    (
        (AttackAlgorithm.FGSM, 0.5, 1),
        (AttackAlgorithm.BIM, 0.25, 2),
        (AttackAlgorithm.PGD, 0.25, 2),
    ),
)
def test_bounded_attacks_report_paired_metrics(
    tmp_path: Path,
    algorithm: AttackAlgorithm,
    step_size: float,
    iterations: int,
) -> None:
    model, dataset = attack_bundles(tmp_path)

    result = run_adversarial_evaluation(
        model,
        dataset,
        config=AttackConfig(
            algorithm=algorithm,
            epsilon=0.5,
            step_size=step_size,
            iterations=iterations,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )

    assert result.metrics.clean_accuracy == 1.0
    assert result.metrics.robust_accuracy == 0.0
    assert result.metrics.attack_success_rate == 1.0
    assert result.metrics.clean_correct_samples == 4
    assert result.metrics.successful_attacks == 4
    assert result.metrics.maximum_observed_linf == pytest.approx(0.5)
    assert result.metrics.gradient_status == "healthy"
    assert result.warnings == ()


def test_attack_exposes_flat_gradient_warning(tmp_path: Path) -> None:
    model, dataset = attack_bundles(tmp_path, model=FlatClassifier())

    result = run_adversarial_evaluation(
        model,
        dataset,
        config=AttackConfig(
            algorithm=AttackAlgorithm.FGSM,
            epsilon=0.1,
            step_size=0.1,
            iterations=1,
            random_start=False,
            seed=1,
            batch_size=4,
        ),
    )

    assert result.metrics.gradient_status == "flat"
    assert "gradient masking" in result.warnings[0]


def test_bim_rejects_random_start() -> None:
    with pytest.raises(ValueError, match="BIM requires random_start=false"):
        AttackConfig(
            algorithm=AttackAlgorithm.BIM,
            epsilon=0.1,
            step_size=0.05,
            iterations=2,
            random_start=True,
            seed=1,
            batch_size=4,
        )


def test_deepfool_reports_l2_bound(tmp_path: Path) -> None:
    model, dataset = attack_bundles(tmp_path)

    result = run_adversarial_evaluation(
        model,
        dataset,
        config=AttackConfig(
            algorithm=AttackAlgorithm.DEEPFOOL,
            norm="l2",
            epsilon=0.5,
            step_size=0.5,
            iterations=3,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )

    assert result.config.norm == "l2"
    assert result.metrics.maximum_observed_l2 <= 0.5 + 1e-6
    assert result.metrics.maximum_observed_linf <= 0.5 + 1e-6
    assert result.metrics.gradient_status == "healthy"


def test_carlini_wagner_reports_l2_bound(tmp_path: Path) -> None:
    model, dataset = attack_bundles(tmp_path)

    result = run_adversarial_evaluation(
        model,
        dataset,
        config=AttackConfig(
            algorithm=AttackAlgorithm.CARLINI_WAGNER,
            norm="l2",
            epsilon=0.5,
            step_size=0.05,
            iterations=20,
            random_start=False,
            seed=1729,
            batch_size=2,
            max_samples=4,
        ),
    )

    assert result.config.norm == "l2"
    assert result.metrics.maximum_observed_l2 <= 0.5 + 1e-6
    assert result.metrics.gradient_status == "healthy"


def test_attack_rejects_inputs_outside_unit_interval(tmp_path: Path) -> None:
    inputs = torch.tensor([-0.1, 0.2, 0.8, 1.1]).reshape(4, 1, 1, 1)
    model, dataset = attack_bundles(tmp_path, inputs=inputs)

    with pytest.raises(RegistryError, match=r"\[0, 1\]"):
        run_adversarial_evaluation(
            model,
            dataset,
            config=AttackConfig(
                algorithm=AttackAlgorithm.FGSM,
                epsilon=0.1,
                step_size=0.1,
                iterations=1,
                random_start=False,
                seed=1,
                batch_size=4,
            ),
        )
