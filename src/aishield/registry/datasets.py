"""Approved torchvision dataset adapters."""

from abc import ABC, abstractmethod
from collections.abc import Sized
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast
from uuid import NAMESPACE_URL, uuid5

import torch
import torchvision
from torch.utils.data import Dataset, TensorDataset
from torchvision import datasets, transforms

from aishield.registry.contracts import DatasetName, DatasetRecord, DatasetSplit
from aishield.registry.errors import RegistryError
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
    source: Literal["approved_public", "generated"] = "approved_public"
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
            source=self.source,
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


class SyntheticDatasetAdapter(TorchvisionDatasetAdapter):
    """Generate a deterministic, zero-download dataset for product evaluation."""

    name = DatasetName.SYNTHETIC
    version = "signal-10-v1"
    source_uri = "aishield://generated/signal-10"
    source = "generated"
    input_shape = (1, 28, 28)

    def _create_dataset(self, root: Path, split: DatasetSplit, *, download: bool) -> Dataset[Any]:
        if download:
            raise RegistryError(
                "the synthetic dataset is generated locally and cannot be downloaded"
            )

        seed = 1729 if split is DatasetSplit.TRAIN else 1730
        sample_count = 1024 if split is DatasetSplit.TRAIN else 256
        generator = torch.Generator().manual_seed(seed)
        labels = torch.arange(sample_count, dtype=torch.long) % self.num_classes
        inputs = (
            torch.rand(
                (sample_count, *self.input_shape),
                generator=generator,
                dtype=torch.float32,
            )
            * 0.08
        )

        # Each class owns a stable bright patch. The signal makes this dataset useful for
        # exercising training/evaluation pipelines without pretending it is a benchmark.
        for class_index in range(self.num_classes):
            row = 3 + (class_index // 5) * 13
            column = 2 + (class_index % 5) * 5
            inputs[labels == class_index, 0, row : row + 7, column : column + 4] += 0.88
        inputs.clamp_(0.0, 1.0)

        manifest = root / f"{split.value}.signal-10.txt"
        manifest.write_text(
            "\n".join(
                (
                    f"version={self.version}",
                    f"split={split.value}",
                    f"seed={seed}",
                    f"samples={sample_count}",
                    "license=generated-for-aishield-demo",
                )
            )
            + "\n",
            encoding="utf-8",
        )
        return cast(Dataset[Any], TensorDataset(inputs, labels))


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
