"""In-process registry orchestration used until persistence is introduced."""

import logging
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import BoundedSemaphore, RLock
from typing import Any, Protocol, TypeVar
from urllib.parse import unquote, urlparse
from uuid import UUID

from pydantic import ValidationError

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
from aishield.evaluation.score import calculate_score
from aishield.jobs.contracts import JobQueueFullError, JobRecord
from aishield.jobs.queue import JobQueue
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    EvaluationResult,
    ModelSource,
    ModelVersionRecord,
)
from aishield.registry.datasets import (
    CIFAR10Adapter,
    DatasetBundle,
    MNISTAdapter,
    SyntheticDatasetAdapter,
    TorchvisionDatasetAdapter,
)
from aishield.registry.errors import (
    RegistryBusyError,
    RegistryError,
    RegistryNotFoundError,
)
from aishield.registry.evaluation import evaluate_registered_model
from aishield.registry.experiment import build_experiment_result
from aishield.registry.models import ModelBundle, SmallCNNAdapter, TorchvisionPretrainedAdapter
from aishield.registry.replay import JournalReplaySummary, group_entries
from aishield.registry.store import MetadataStore, build_metadata_store
from aishield.schemas.experiment import ExperimentResult
from aishield.training.contracts import TrainingConfig, TrainingRunRecord
from aishield.training.runner import train_model

logger = logging.getLogger("aishield.registry")

#: True inside a background worker thread, where waiting for a slot is preferable
#: to failing fast the way a synchronous API request should.
_in_worker: ContextVar[bool] = ContextVar("aishield_in_worker", default=False)


class _JournalRecord(Protocol):
    """Any immutable run record the journal can restore by identity."""

    id: UUID

    @classmethod
    def model_validate(cls, obj: Any) -> Any: ...


_RecordT = TypeVar("_RecordT", bound=_JournalRecord)


class RegistryService:
    """Load and retain reproducible dataset and model handles for this process."""

    def __init__(
        self,
        settings: Settings,
        dataset_adapters: Mapping[DatasetName, TorchvisionDatasetAdapter] | None = None,
        store: MetadataStore | None = None,
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
        self._experiments: dict[UUID, ExperimentResult] = {}
        self._store: MetadataStore = store or build_metadata_store(settings)
        self._jobs = JobQueue(
            max_workers=settings.job_max_workers,
            max_pending=settings.job_max_pending,
            retained_jobs=settings.job_retained_records,
            observer=lambda record: self._store.append("job", record),
        )
        self._run_slots = BoundedSemaphore(settings.max_concurrent_runs)
        self._lock = RLock()

    @contextmanager
    def _worker_mode(self) -> Iterator[None]:
        """Mark the current thread as a background worker, which waits for a slot."""

        token = _in_worker.set(True)
        try:
            yield
        finally:
            _in_worker.reset(token)

    @contextmanager
    def _run_slot(self, kind: str) -> Iterator[None]:
        """Hold one of the bounded evaluation slots for the duration of a run.

        A synchronous API request fails immediately rather than piling several
        full torch evaluations onto one machine; a queued worker waits instead,
        because refusing there would discard already-accepted work.
        """

        timeout = self.settings.job_slot_timeout_seconds if _in_worker.get() else 0.0
        if not self._run_slots.acquire(blocking=timeout > 0.0, timeout=timeout or None):
            logger.warning("run rejected: no free evaluation slot", extra={"run_kind": kind})
            raise RegistryBusyError(
                f"all {self.settings.max_concurrent_runs} evaluation slots are busy; "
                f"retry or queue the run as a background job"
            )
        try:
            yield
        finally:
            self._run_slots.release()

    @contextmanager
    def _timed_run(self, kind: str, **fields: object) -> Iterator[dict[str, object]]:
        """Log the start, duration, and outcome of one evaluation or training run.

        The yielded dict is merged into the completion record, so a caller can
        attach the identifier that only exists once the run has finished.
        """

        with self._run_slot(kind):
            started = time.perf_counter()
            logger.info("%s run started", kind, extra={"run_kind": kind, **fields})
            outcome: dict[str, object] = {}
            try:
                yield outcome
            except Exception:
                logger.exception(
                    "%s run failed",
                    kind,
                    extra={
                        "run_kind": kind,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        **fields,
                    },
                )
                raise
            logger.info(
                "%s run completed",
                kind,
                extra={
                    "run_kind": kind,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    **fields,
                    **outcome,
                },
            )

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
        self._store.append("dataset", bundle.record)
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
        self._store.append("model", bundle.record)
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
        self._store.append("model", bundle.record)
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

        with self._timed_run(
            "baseline", model_version_id=str(model_id), dataset_id=str(dataset_id)
        ) as outcome:
            record = run_clean_baseline(
                self.get_model_bundle(model_id),
                self.get_dataset_bundle(dataset_id),
                artifact_root=self.settings.artifact_root,
                config=config,
            )
            outcome["run_id"] = str(record.id)
            outcome["clean_accuracy"] = record.metrics.clean_accuracy
        with self._lock:
            self._baselines[record.id] = record
        self._store.append("baseline", record)
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

        with self._timed_run(
            "attack",
            model_version_id=str(model_id),
            dataset_id=str(dataset_id),
            algorithm=config.algorithm.value,
            epsilon=config.epsilon,
        ) as outcome:
            record = run_adversarial_evaluation(
                self.get_model_bundle(model_id),
                self.get_dataset_bundle(dataset_id),
                config=config,
            )
            outcome["run_id"] = str(record.id)
            outcome["robust_accuracy"] = record.metrics.robust_accuracy
            outcome["gradient_status"] = record.metrics.gradient_status
        with self._lock:
            self._attacks[record.id] = record
        self._store.append("attack", record)
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

        with self._timed_run(
            "defense",
            model_version_id=str(model_id),
            dataset_id=str(dataset_id),
            defense_kind=defense.kind.value,
            algorithm=attack.algorithm.value,
        ) as outcome:
            record = run_defense_evaluation(
                self.get_model_bundle(model_id),
                self.get_dataset_bundle(dataset_id),
                defense=defense,
                attack=attack,
            )
            outcome["run_id"] = str(record.id)
            outcome["robust_accuracy_after"] = record.metrics.robust_accuracy_after
        with self._lock:
            self._defenses[record.id] = record
        self._store.append("defense", record)
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

        with self._timed_run(
            "transfer",
            surrogate_model_version_id=str(surrogate_model_id),
            target_model_version_id=str(target_model_id),
            dataset_id=str(dataset_id),
            algorithm=attack.algorithm.value,
        ) as outcome:
            record = run_transfer_evaluation(
                self.get_model_bundle(surrogate_model_id),
                self.get_model_bundle(target_model_id),
                self.get_dataset_bundle(dataset_id),
                attack=attack,
            )
            outcome["run_id"] = str(record.id)
            outcome["transferred_robust_accuracy"] = record.metrics.transferred_robust_accuracy
        with self._lock:
            self._transfers[record.id] = record
        self._store.append("transfer", record)
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

        with self._timed_run(
            "training",
            model_version_id=str(model_id),
            dataset_id=str(dataset_id),
            strategy=config.strategy.value,
            epochs=config.epochs,
        ) as outcome:
            bundle, record = train_model(
                self.get_model_bundle(model_id),
                self.get_dataset_bundle(dataset_id),
                artifact_root=self.settings.artifact_root,
                config=config,
            )
            outcome["run_id"] = str(record.id)
            outcome["trained_model_version_id"] = str(bundle.record.id)
            outcome["final_robust_accuracy"] = record.metrics.final_robust_accuracy
        with self._lock:
            self._models[bundle.record.id] = bundle
            self._training[record.id] = record
        self._store.append("model", bundle.record)
        self._store.append("training", record)
        return bundle.record, record, bundle

    def list_training(self) -> list[TrainingRunRecord]:
        """List completed training runs in deterministic ID order."""

        with self._lock:
            return [self._training[key] for key in sorted(self._training, key=str)]

    def export_experiment(self, baseline_id: UUID) -> ExperimentResult:
        """Build a portable, self-contained envelope for one baseline run.

        Every attack and defense recorded against the same model and dataset is
        included, so the envelope carries the full evidence for that target
        rather than a hand-picked subset.
        """

        baseline = self.get_baseline(baseline_id)
        dataset = self.get_dataset_bundle(baseline.dataset_id).record
        model = self.get_model_bundle(baseline.model_version_id).record
        with self._lock:
            attacks = [
                record
                for record in self._attacks.values()
                if record.model_version_id == model.id and record.dataset_id == dataset.id
            ]
            defenses = [
                record
                for record in self._defenses.values()
                if record.model_version_id == model.id and record.dataset_id == dataset.id
            ]
        attacks.sort(key=lambda record: record.created_at)
        defenses.sort(key=lambda record: record.created_at)
        score = calculate_score(attacks) if attacks else None
        return build_experiment_result(
            baseline,
            dataset,
            model,
            attacks=attacks,
            defenses=defenses,
            score=score,
        )

    def import_experiment(self, envelope: ExperimentResult) -> ExperimentResult:
        """Retain a peer's validated envelope for audit and comparison.

        An imported envelope is evidence, not a runnable handle: the datasets and
        weights it names are not fetched, so it never becomes a source of new runs.
        """

        with self._lock:
            self._experiments[envelope.experiment.id] = envelope
        self._store.append("experiment", envelope)
        logger.info(
            "experiment imported",
            extra={
                "experiment_id": str(envelope.experiment.id),
                "attack_runs": len(envelope.attack_runs),
                "defense_runs": len(envelope.defense_runs),
            },
        )
        return envelope

    def get_experiment(self, experiment_id: UUID) -> ExperimentResult:
        with self._lock:
            try:
                return self._experiments[experiment_id]
            except KeyError as error:
                raise RegistryNotFoundError(
                    f"experiment is not imported: {experiment_id}"
                ) from error

    def list_experiments(self) -> list[ExperimentResult]:
        with self._lock:
            return [self._experiments[key] for key in sorted(self._experiments, key=str)]

    def _replay_dataset(self, record: dict[str, Any], skipped: list[str]) -> bool:
        """Reload a dataset split and accept it only if its manifest still matches."""

        try:
            stored = DatasetRecord.model_validate(record)
        except ValidationError as error:
            skipped.append(f"dataset {record.get('id', '?')}: unreadable record ({error.title})")
            return False
        # Replay never downloads: it only re-reads a split that is already present,
        # so a missing one is skipped rather than fetched without approval.
        try:
            bundle = self._dataset_adapters[stored.name].load(
                self.settings.dataset_root, stored.split, download=False
            )
        except (RegistryError, OSError, KeyError) as error:
            skipped.append(f"dataset {stored.id}: files unavailable ({error})")
            return False
        if bundle.record.manifest_sha256 != stored.manifest_sha256:
            skipped.append(f"dataset {stored.id}: manifest hash changed on disk")
            return False
        with self._lock:
            self._datasets[bundle.record.id] = bundle
        return True

    def _replay_model(self, record: dict[str, Any], skipped: list[str]) -> bool:
        """Restore a model from its content-addressed checkpoint, verifying the hash."""

        try:
            stored = ModelVersionRecord.model_validate(record)
        except ValidationError as error:
            skipped.append(f"model {record.get('id', '?')}: unreadable record ({error.title})")
            return False
        if stored.source is ModelSource.TORCHVISION:
            skipped.append(f"model {stored.id}: torchvision weights are not replayed")
            return False
        adapter = SmallCNNAdapter(
            artifact_root=self.settings.artifact_root,
            model_root=self.settings.model_root,
            device_name=self.settings.compute_device,
        )
        # Trained checkpoints are not named after the state hash, so take the file
        # name the record itself points at rather than reconstructing one.
        checkpoint = Path(unquote(urlparse(stored.artifact.uri).path)).name
        try:
            loaded = adapter.load(
                input_channels=stored.input_channels,
                num_classes=stored.num_classes,
                seed=stored.seed,
                checkpoint=checkpoint,
            )
        except (RegistryError, OSError) as error:
            skipped.append(f"model {stored.id}: checkpoint unavailable ({error})")
            return False
        if loaded.record.state_dict_sha256 != stored.state_dict_sha256:
            skipped.append(f"model {stored.id}: restored weights do not match the record")
            return False
        # Keep the recorded identity: a trained model has its own version, source and
        # UUID namespace, and rebuilding it as a fresh SmallCNN would rewrite history.
        bundle = ModelBundle(model=loaded.model, record=stored, preprocess=loaded.preprocess)
        with self._lock:
            self._models[stored.id] = bundle
        return True

    def _replay_records(
        self,
        records: list[dict[str, Any]],
        model: type[_RecordT],
        index: dict[UUID, Any],
        label: str,
        skipped: list[str],
    ) -> int:
        """Restore immutable run evidence, which needs no runtime handle."""

        restored = 0
        for record in records:
            try:
                parsed = model.model_validate(record)
            except ValidationError as error:
                skipped.append(
                    f"{label} {record.get('id', '?')}: unreadable record ({error.title})"
                )
                continue
            with self._lock:
                index[parsed.id] = parsed
            restored += 1
        return restored

    def replay_journal(self) -> JournalReplaySummary:
        """Rebuild the in-memory index from the journal after a process restart.

        Run evidence is always restored. Dataset and model handles are rebuilt
        only when the files on disk still hash to the recorded identity, so a
        replay can never resurrect a run against changed inputs. Background jobs
        are never replayed: a queued job from a dead process was never executed.
        """

        entries = self._store.read()
        grouped = group_entries(entries)
        skipped: list[str] = []

        datasets = sum(1 for record in grouped["dataset"] if self._replay_dataset(record, skipped))
        models = sum(1 for record in grouped["model"] if self._replay_model(record, skipped))
        summary = JournalReplaySummary(
            entries_read=len(entries),
            datasets_restored=datasets,
            models_restored=models,
            baselines_restored=self._replay_records(
                grouped["baseline"], BaselineRunRecord, self._baselines, "baseline", skipped
            ),
            attacks_restored=self._replay_records(
                grouped["attack"], AttackRunRecord, self._attacks, "attack", skipped
            ),
            defenses_restored=self._replay_records(
                grouped["defense"], DefenseRunRecord, self._defenses, "defense", skipped
            ),
            transfers_restored=self._replay_records(
                grouped["transfer"], TransferDefenseRunRecord, self._transfers, "transfer", skipped
            ),
            training_restored=self._replay_records(
                grouped["training"], TrainingRunRecord, self._training, "training", skipped
            ),
            experiments_restored=self._replay_experiments(grouped["experiment"], skipped),
            jobs_skipped=sum(1 for entry in entries if entry.get("kind") == "job"),
            skipped=tuple(skipped),
        )
        logger.info(
            "metadata replay completed",
            extra={
                "metadata_backend": self.settings.metadata_backend,
                "entries_read": summary.entries_read,
                "datasets_restored": summary.datasets_restored,
                "models_restored": summary.models_restored,
                "runs_restored": summary.runs_restored,
                "skipped": len(summary.skipped),
            },
        )
        return summary

    def _replay_experiments(self, records: list[dict[str, Any]], skipped: list[str]) -> int:
        restored = 0
        for record in records:
            try:
                envelope = ExperimentResult.model_validate(record)
            except ValidationError as error:
                skipped.append(f"experiment: unreadable envelope ({error.title})")
                continue
            with self._lock:
                self._experiments[envelope.experiment.id] = envelope
            restored += 1
        return restored

    def check_ready(self) -> None:
        """Raise when the configured metadata store cannot currently be used."""

        self._store.check_ready()

    def shutdown(self) -> None:
        """Stop background workers and release the metadata store's resources."""

        self._jobs.shutdown(wait=False)
        self._store.close()

    def read_journal(self) -> list[dict[str, object]]:
        """Return append-only metadata entries for audit/export consumers."""

        return self._store.read()

    def submit_training_job(
        self, model_id: UUID, dataset_id: UUID, *, config: TrainingConfig
    ) -> JobRecord:
        """Queue training without blocking the API worker."""

        # Fail before accepting the job if the inputs are already unusable, so a
        # caller sees a 404 now instead of a failed job record later.
        self.get_model_bundle(model_id)
        self.get_dataset_bundle(dataset_id)

        def task() -> UUID:
            with self._worker_mode():
                return self.train_model(model_id, dataset_id, config=config)[1].id

        try:
            return self._jobs.submit("training", task)
        except JobQueueFullError as error:
            raise RegistryBusyError(str(error)) from error

    def get_job(self, job_id: UUID) -> JobRecord:
        try:
            return self._jobs.get(job_id)
        except KeyError as error:
            raise RegistryNotFoundError(f"job is not loaded: {job_id}") from error

    def cancel_job(self, job_id: UUID) -> JobRecord:
        """Cancel a job that has not started; a running job keeps its slot."""

        try:
            return self._jobs.cancel(job_id)
        except KeyError as error:
            raise RegistryNotFoundError(f"job is not loaded: {job_id}") from error

    def list_jobs(self) -> list[JobRecord]:
        return self._jobs.list()

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
