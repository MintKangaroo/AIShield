"""In-process registry orchestration used until persistence is introduced."""

from collections.abc import Mapping
from threading import RLock
from uuid import UUID

from aishield.core.config import Settings
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    EvaluationResult,
    ModelVersionRecord,
)
from aishield.registry.datasets import (
    CIFAR10Adapter,
    DatasetBundle,
    MNISTAdapter,
    TorchvisionDatasetAdapter,
)
from aishield.registry.errors import RegistryError, RegistryNotFoundError
from aishield.registry.evaluation import evaluate_registered_model
from aishield.registry.models import ModelBundle, SmallCNNAdapter, TorchvisionPretrainedAdapter


class RegistryService:
    """Load and retain reproducible dataset and model handles for this process."""

    def __init__(
        self,
        settings: Settings,
        dataset_adapters: Mapping[DatasetName, TorchvisionDatasetAdapter] | None = None,
    ) -> None:
        self.settings = settings
        self._dataset_adapters = dict(
            dataset_adapters
            or {
                DatasetName.MNIST: MNISTAdapter(),
                DatasetName.CIFAR10: CIFAR10Adapter(),
            }
        )
        self._datasets: dict[UUID, DatasetBundle] = {}
        self._models: dict[UUID, ModelBundle] = {}
        self._lock = RLock()

    def load_dataset(
        self, name: DatasetName, split: DatasetSplit, *, download: bool
    ) -> DatasetRecord:
        """Load an approved dataset adapter and retain the runtime object."""

        if download and not self.settings.allow_public_downloads:
            raise RegistryError("public dataset downloads are not approved by configuration")
        adapter = self._dataset_adapters[name]
        bundle = adapter.load(self.settings.dataset_root, split, download=download)
        with self._lock:
            self._datasets[bundle.record.id] = bundle
        return bundle.record

    def load_small_cnn(
        self, dataset_id: UUID, *, seed: int, checkpoint: str | None
    ) -> ModelVersionRecord:
        """Create a dataset-compatible seeded SmallCNN."""

        dataset = self.get_dataset_bundle(dataset_id)
        adapter = SmallCNNAdapter(
            artifact_root=self.settings.artifact_root,
            model_root=self.settings.model_root,
            device_name=self.settings.compute_device,
        )
        bundle = adapter.load(
            input_channels=dataset.record.input_shape[0],
            num_classes=dataset.record.num_classes,
            seed=seed,
            checkpoint=checkpoint,
        )
        with self._lock:
            self._models[bundle.record.id] = bundle
        return bundle.record

    def load_torchvision_model(
        self,
        *,
        architecture: str,
        weights: str | None,
        num_classes: int,
        seed: int,
    ) -> ModelVersionRecord:
        """Load a torchvision classifier under the public-download policy."""

        adapter = TorchvisionPretrainedAdapter(
            artifact_root=self.settings.artifact_root,
            device_name=self.settings.compute_device,
            allow_downloads=self.settings.allow_public_downloads,
        )
        bundle = adapter.load(
            architecture=architecture,
            weights=weights,
            num_classes=num_classes,
            seed=seed,
        )
        with self._lock:
            self._models[bundle.record.id] = bundle
        return bundle.record

    def evaluate(
        self,
        model_id: UUID,
        dataset_id: UUID,
        *,
        seed: int,
        batch_size: int,
        max_samples: int | None,
    ) -> EvaluationResult:
        """Evaluate one retained model and dataset pair."""

        return evaluate_registered_model(
            self.get_model_bundle(model_id),
            self.get_dataset_bundle(dataset_id),
            seed=seed,
            batch_size=batch_size,
            max_samples=max_samples,
        )

    def list_datasets(self) -> list[DatasetRecord]:
        """List loaded dataset records in deterministic ID order."""

        with self._lock:
            return [self._datasets[key].record for key in sorted(self._datasets, key=str)]

    def list_models(self) -> list[ModelVersionRecord]:
        """List loaded model records in deterministic ID order."""

        with self._lock:
            return [self._models[key].record for key in sorted(self._models, key=str)]

    def get_dataset_bundle(self, dataset_id: UUID) -> DatasetBundle:
        """Return a runtime dataset or raise a domain-level not-found error."""

        with self._lock:
            try:
                return self._datasets[dataset_id]
            except KeyError as error:
                raise RegistryNotFoundError(f"dataset is not loaded: {dataset_id}") from error

    def get_model_bundle(self, model_id: UUID) -> ModelBundle:
        """Return a runtime model or raise a domain-level not-found error."""

        with self._lock:
            try:
                return self._models[model_id]
            except KeyError as error:
                raise RegistryNotFoundError(f"model is not loaded: {model_id}") from error
