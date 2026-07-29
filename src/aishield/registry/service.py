"""In-process registry orchestration used until persistence is introduced."""

from collections.abc import Mapping
from pathlib import Path
from threading import RLock
from urllib.parse import unquote, urlparse
from uuid import UUID

from aishield.attacks.contracts import AttackConfig, AttackRunRecord
from aishield.attacks.runner import run_adversarial_evaluation
from aishield.core.config import Settings
from aishield.defenses.contracts import DefenseConfig, DefenseRunRecord, TransferDefenseRunRecord
from aishield.defenses.runner import run_defense_evaluation, run_transfer_evaluation
from aishield.evaluation.contracts import (
    BaselineArtifact,
    BaselineConfig,
    BaselineRunRecord,
    BaselineVerification,
)
from aishield.evaluation.runner import run_clean_baseline, verify_baseline_rerun
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
    SyntheticDatasetAdapter,
    TorchvisionDatasetAdapter,
)
from aishield.registry.errors import RegistryError, RegistryNotFoundError
from aishield.registry.evaluation import evaluate_registered_model
from aishield.registry.models import ModelBundle, SmallCNNAdapter, TorchvisionPretrainedAdapter
from aishield.training.contracts import TrainingConfig, TrainingRunRecord
from aishield.training.runner import train_model


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
                DatasetName.SYNTHETIC: SyntheticDatasetAdapter(),
                DatasetName.MNIST: MNISTAdapter(),
                DatasetName.CIFAR10: CIFAR10Adapter(),
            }
        )
        self._datasets: dict[UUID, DatasetBundle] = {}
        self._models: dict[UUID, ModelBundle] = {}
        self._baselines: dict[UUID, BaselineRunRecord] = {}
        self._attacks: dict[UUID, AttackRunRecord] = {}
        self._defenses: dict[UUID, DefenseRunRecord] = {}
        self._transfers: dict[UUID, TransferDefenseRunRecord] = {}
        self._training: dict[UUID, TrainingRunRecord] = {}
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

    def run_clean_baseline(
        self,
        model_id: UUID,
        dataset_id: UUID,
        *,
        config: BaselineConfig,
    ) -> BaselineRunRecord:
        """Run and retain a full clean baseline with generated artifacts."""

        record = run_clean_baseline(
            self.get_model_bundle(model_id),
            self.get_dataset_bundle(dataset_id),
            artifact_root=self.settings.artifact_root,
            config=config,
        )
        with self._lock:
            self._baselines[record.id] = record
        return record

    def verify_clean_baseline(self, baseline_id: UUID) -> BaselineVerification:
        """Rerun one baseline with its exact configuration and compare evidence."""

        reference = self.get_baseline(baseline_id)
        rerun = self.run_clean_baseline(
            reference.model_version_id,
            reference.dataset_id,
            config=reference.config,
        )
        return verify_baseline_rerun(reference, rerun)

    def run_attack(
        self,
        model_id: UUID,
        dataset_id: UUID,
        *,
        config: AttackConfig,
    ) -> AttackRunRecord:
        """Run and retain a bounded adversarial evaluation."""

        record = run_adversarial_evaluation(
            self.get_model_bundle(model_id),
            self.get_dataset_bundle(dataset_id),
            config=config,
        )
        with self._lock:
            self._attacks[record.id] = record
        return record

    def run_defense(
        self,
        model_id: UUID,
        dataset_id: UUID,
        *,
        defense: DefenseConfig,
        attack: AttackConfig,
    ) -> DefenseRunRecord:
        """Run and retain a before/after adaptive-defense evaluation."""

        record = run_defense_evaluation(
            self.get_model_bundle(model_id),
            self.get_dataset_bundle(dataset_id),
            defense=defense,
            attack=attack,
        )
        with self._lock:
            self._defenses[record.id] = record
        return record

    def list_datasets(self) -> list[DatasetRecord]:
        """List loaded dataset records in deterministic ID order."""

        with self._lock:
            return [self._datasets[key].record for key in sorted(self._datasets, key=str)]

    def list_models(self) -> list[ModelVersionRecord]:
        """List loaded model records in deterministic ID order."""

        with self._lock:
            return [self._models[key].record for key in sorted(self._models, key=str)]

    def list_baselines(self) -> list[BaselineRunRecord]:
        """List completed clean baselines in deterministic ID order."""

        with self._lock:
            return [self._baselines[key] for key in sorted(self._baselines, key=str)]

    def list_attacks(self) -> list[AttackRunRecord]:
        """List completed attack runs in deterministic ID order."""

        with self._lock:
            return [self._attacks[key] for key in sorted(self._attacks, key=str)]

    def list_defenses(self) -> list[DefenseRunRecord]:
        """List completed defense evaluations in deterministic ID order."""

        with self._lock:
            return [self._defenses[key] for key in sorted(self._defenses, key=str)]

    def run_transfer(
        self,
        surrogate_model_id: UUID,
        target_model_id: UUID,
        dataset_id: UUID,
        *,
        attack: AttackConfig,
    ) -> TransferDefenseRunRecord:
        """Generate a surrogate attack and measure black-box transfer."""

        record = run_transfer_evaluation(
            self.get_model_bundle(surrogate_model_id),
            self.get_model_bundle(target_model_id),
            self.get_dataset_bundle(dataset_id),
            attack=attack,
        )
        with self._lock:
            self._transfers[record.id] = record
        return record

    def list_transfers(self) -> list[TransferDefenseRunRecord]:
        """List transfer evaluations in deterministic ID order."""

        with self._lock:
            return [self._transfers[key] for key in sorted(self._transfers, key=str)]

    def train_model(
        self,
        model_id: UUID,
        dataset_id: UUID,
        *,
        config: TrainingConfig,
    ) -> tuple[ModelVersionRecord, TrainingRunRecord, ModelBundle]:
        """Train a copied model and retain its runtime bundle and evidence."""

        bundle, record = train_model(
            self.get_model_bundle(model_id),
            self.get_dataset_bundle(dataset_id),
            artifact_root=self.settings.artifact_root,
            config=config,
        )
        with self._lock:
            self._models[bundle.record.id] = bundle
            self._training[record.id] = record
        return bundle.record, record, bundle

    def list_training(self) -> list[TrainingRunRecord]:
        """List completed training runs in deterministic ID order."""

        with self._lock:
            return [self._training[key] for key in sorted(self._training, key=str)]

    def get_baseline(self, baseline_id: UUID) -> BaselineRunRecord:
        """Return a completed baseline or raise a domain-level not-found error."""

        with self._lock:
            try:
                return self._baselines[baseline_id]
            except KeyError as error:
                raise RegistryNotFoundError(f"baseline is not loaded: {baseline_id}") from error

    def get_attack(self, attack_id: UUID) -> AttackRunRecord:
        """Return a completed adversarial evaluation or a domain-level not-found error."""

        with self._lock:
            try:
                return self._attacks[attack_id]
            except KeyError as error:
                raise RegistryNotFoundError(f"attack run is not loaded: {attack_id}") from error

    def get_baseline_artifact(
        self,
        baseline_id: UUID,
        artifact_id: UUID,
    ) -> tuple[BaselineArtifact, Path]:
        """Resolve one registered baseline artifact below the configured artifact root."""

        baseline = self.get_baseline(baseline_id)
        try:
            artifact = next(item for item in baseline.artifacts if item.id == artifact_id)
        except StopIteration as error:
            raise RegistryNotFoundError(
                f"baseline artifact is not loaded: {artifact_id}"
            ) from error

        parsed = urlparse(artifact.uri)
        if parsed.scheme != "file":
            raise RegistryError("baseline artifact does not use local file storage")
        path = Path(unquote(parsed.path)).resolve()
        artifact_root = self.settings.artifact_root.resolve()
        if not path.is_relative_to(artifact_root) or not path.is_file() or path.is_symlink():
            raise RegistryNotFoundError(f"baseline artifact file is unavailable: {artifact_id}")
        return artifact, path

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
