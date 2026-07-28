from pathlib import Path
from typing import Any

import torch
from torch.utils.data import Dataset, TensorDataset

from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.datasets import CIFAR10Adapter, MNISTAdapter


class FixtureMNISTAdapter(MNISTAdapter):
    def __init__(self) -> None:
        self.calls: list[tuple[Path, DatasetSplit, bool]] = []

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        self.calls.append((root, split, download))
        (root / "mnist.fixture").write_bytes(b"canonical-mnist-fixture")
        sample_count = 4 if split is DatasetSplit.TRAIN else 2
        return TensorDataset(
            torch.zeros(sample_count, 1, 28, 28),
            torch.arange(sample_count, dtype=torch.long) % 10,
        )


class FixtureCIFAR10Adapter(CIFAR10Adapter):
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        (root / "cifar.fixture").write_bytes(b"canonical-cifar-fixture")
        return TensorDataset(torch.zeros(3, 3, 32, 32), torch.tensor([0, 1, 2]))


def test_mnist_adapter_records_version_split_checksum_and_source(tmp_path: Path) -> None:
    adapter = FixtureMNISTAdapter()

    first = adapter.load(tmp_path, DatasetSplit.TEST, download=False)
    second = adapter.load(tmp_path, DatasetSplit.TEST, download=False)

    assert first.record == second.record
    assert first.record.name is DatasetName.MNIST
    assert first.record.version == "mnist-original-v1"
    assert first.record.split is DatasetSplit.TEST
    assert first.record.sample_count == 2
    assert first.record.input_shape == (1, 28, 28)
    assert first.record.source == "approved_public"
    assert len(first.record.manifest_sha256) == 64
    assert adapter.calls[-1] == (tmp_path / "mnist", DatasetSplit.TEST, False)


def test_split_is_part_of_dataset_identity(tmp_path: Path) -> None:
    adapter = FixtureMNISTAdapter()

    train = adapter.load(tmp_path, DatasetSplit.TRAIN, download=True)
    test = adapter.load(tmp_path, DatasetSplit.TEST, download=True)

    assert train.record.id != test.record.id
    assert train.record.sample_count == 4
    assert adapter.calls[0][2] is True


def test_cifar10_adapter_records_rgb_shape(tmp_path: Path) -> None:
    bundle = FixtureCIFAR10Adapter().load(tmp_path, DatasetSplit.TRAIN, download=False)

    assert bundle.record.name is DatasetName.CIFAR10
    assert bundle.record.version == "cifar-10-python-v1"
    assert bundle.record.input_shape == (3, 32, 32)
    assert bundle.record.num_classes == 10
