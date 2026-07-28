from pathlib import Path
from uuid import UUID

import pytest
import torch
from torch.utils.data import TensorDataset

from aishield.registry.contracts import DatasetName, DatasetRecord, DatasetSplit
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.evaluation import evaluate_registered_model
from aishield.registry.models import ModelBundle, SmallCNNAdapter


def dataset_bundle(*, channels: int = 1, samples: int = 5) -> DatasetBundle:
    record = DatasetRecord(
        id=UUID("00000000-0000-4000-8000-000000000101"),
        name=DatasetName.MNIST,
        version="fixture-v1",
        split=DatasetSplit.TEST,
        source_uri="https://example.invalid/approved-fixture",
        manifest_sha256="a" * 64,
        sample_count=samples,
        num_classes=10,
        input_shape=(channels, 28, 28),
        transform="ToTensor",
        torchvision_version="fixture",
    )
    dataset = TensorDataset(
        torch.zeros(samples, channels, 28, 28),
        torch.arange(samples, dtype=torch.long) % 10,
    )
    return DatasetBundle(dataset=dataset, record=record)


def model_bundle(tmp_path: Path) -> ModelBundle:
    return SmallCNNAdapter(tmp_path, tmp_path / "models", "cpu").load(
        input_channels=1,
        num_classes=10,
        seed=1729,
    )


def test_evaluation_is_bounded_and_reports_robustness_as_not_evaluated(tmp_path: Path) -> None:
    result = evaluate_registered_model(
        model_bundle(tmp_path),
        dataset_bundle(samples=5),
        seed=1729,
        batch_size=2,
        max_samples=3,
    )

    assert result.evaluated_samples == 3
    assert 0.0 <= result.clean_accuracy <= 1.0
    assert result.mean_loss >= 0.0
    assert result.robust_accuracy is None
    assert result.robust_accuracy_status == "not_evaluated"


@pytest.mark.parametrize(
    ("batch_size", "max_samples", "message"),
    [(0, None, "batch_size"), (1, 0, "max_samples")],
)
def test_evaluation_validates_bounds(
    tmp_path: Path, batch_size: int, max_samples: int | None, message: str
) -> None:
    with pytest.raises(RegistryError, match=message):
        evaluate_registered_model(
            model_bundle(tmp_path),
            dataset_bundle(),
            seed=1,
            batch_size=batch_size,
            max_samples=max_samples,
        )


def test_evaluation_validates_dataset_compatibility(tmp_path: Path) -> None:
    model = model_bundle(tmp_path)

    with pytest.raises(RegistryError, match="input channels"):
        evaluate_registered_model(
            model,
            dataset_bundle(channels=3),
            seed=1,
            batch_size=1,
            max_samples=None,
        )

    incompatible_record = dataset_bundle().record.model_copy(update={"num_classes": 2})
    incompatible = DatasetBundle(dataset=dataset_bundle().dataset, record=incompatible_record)
    with pytest.raises(RegistryError, match="class count"):
        evaluate_registered_model(
            model,
            incompatible,
            seed=1,
            batch_size=1,
            max_samples=None,
        )


def test_evaluation_rejects_empty_dataset(tmp_path: Path) -> None:
    empty = dataset_bundle(samples=1)
    empty = DatasetBundle(
        dataset=TensorDataset(torch.empty(0, 1, 28, 28), torch.empty(0, dtype=torch.long)),
        record=empty.record.model_copy(update={"sample_count": 1}),
    )

    with pytest.raises(RegistryError, match="no samples"):
        evaluate_registered_model(
            model_bundle(tmp_path),
            empty,
            seed=1,
            batch_size=1,
            max_samples=None,
        )
