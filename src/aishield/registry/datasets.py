"""Approved torchvision dataset adapters."""

from abc import ABC, abstractmethod
from collections.abc import Sized
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast
from uuid import NAMESPACE_URL, uuid5

import torchvision
from torch.utils.data import Dataset
from torchvision import datasets, transforms

from aishield.registry.contracts import DatasetName, DatasetRecord, DatasetSplit
from aishield.registry.reproducibility import sha256_directory_manifest


@dataclass(frozen=True, slots=True)
class DatasetBundle:
    """Runtime dataset paired with its immutable registry record."""

    dataset: Dataset[Any]
    record: DatasetRecord


class TorchvisionDatasetAdapter(ABC):
    """Base adapter that fingerprints the exact local dataset materialization."""

    name: DatasetName
    version: str
    source_uri: str
    input_shape: tuple[int, int, int]
    num_classes: Final = 10

    def load(self, root: Path, split: DatasetSplit, *, download: bool) -> DatasetBundle:
        """Load one split and produce its stable metadata record."""

        dataset_root = root / self.name.value
        dataset_root.mkdir(parents=True, exist_ok=True)
        dataset = self._create_dataset(dataset_root, split, download=download)
        manifest_sha256 = sha256_directory_manifest(dataset_root)
        identity = ":".join((self.name.value, self.version, split.value, manifest_sha256))
        record = DatasetRecord(
            id=uuid5(NAMESPACE_URL, f"aishield:dataset:{identity}"),
            name=self.name,
            version=self.version,
            split=split,
            source_uri=self.source_uri,
            manifest_sha256=manifest_sha256,
            sample_count=len(cast(Sized, dataset)),
            num_classes=self.num_classes,
            input_shape=self.input_shape,
            transform="torchvision.transforms.ToTensor",
            torchvision_version=torchvision.__version__,
        )
        return DatasetBundle(dataset=dataset, record=record)

    @abstractmethod
    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        """Instantiate the underlying torchvision dataset."""


class MNISTAdapter(TorchvisionDatasetAdapter):
    """Adapter for the canonical torchvision MNIST distribution."""

    name = DatasetName.MNIST
    version = "mnist-original-v1"
    source_uri = "https://ossci-datasets.s3.amazonaws.com/mnist/"
    input_shape = (1, 28, 28)

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        return cast(
            Dataset[Any],
            datasets.MNIST(
                root=root,
                train=split is DatasetSplit.TRAIN,
                transform=transforms.ToTensor(),
                download=download,
            ),
        )


class CIFAR10Adapter(TorchvisionDatasetAdapter):
    """Adapter for the canonical torchvision CIFAR-10 Python distribution."""

    name = DatasetName.CIFAR10
    version = "cifar-10-python-v1"
    source_uri = "https://www.cs.toronto.edu/~kriz/cifar.html"
    input_shape = (3, 32, 32)

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        return cast(
            Dataset[Any],
            datasets.CIFAR10(
                root=root,
                train=split is DatasetSplit.TRAIN,
                transform=transforms.ToTensor(),
                download=download,
            ),
        )
