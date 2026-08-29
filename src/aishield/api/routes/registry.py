"""Dataset, model, and basic evaluation registry endpoints."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from aishield.attacks.contracts import AttackAlgorithm, AttackConfig, AttackRunRecord
from aishield.defenses.contracts import (
    DefenseConfig,
    DefenseKind,
    DefenseRunRecord,
    TransferDefenseRunRecord,
)
from aishield.evaluation.contracts import (
    BaselineConfig,
    BaselineRunRecord,
    BaselineVerification,
)
from aishield.evaluation.score import RobustnessScore, calculate_score
from aishield.jobs.contracts import JobNotCancellableError, JobRecord
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    EvaluationResult,
    ModelVersionRecord,
)
from aishield.registry.errors import (
    RegistryBusyError,
    RegistryError,
    RegistryNotFoundError,
)
from aishield.registry.replay import JournalReplaySummary
from aishield.registry.service import RegistryService
from aishield.schemas.experiment import ExperimentResult
from aishield.training.contracts import TrainingConfig, TrainingRunRecord, TrainingStrategy

router = APIRouter(prefix="/registry", tags=["registry"])


class RequestModel(BaseModel):
    """Strict request base that catches misspelled experiment parameters."""

    model_config = ConfigDict(extra="forbid")


class DatasetLoadRequest(RequestModel):
    """Request one approved torchvision dataset split."""

    name: DatasetName
    split: DatasetSplit
    download: bool = False


class SmallCNNLoadRequest(RequestModel):
    """Create or restore the built-in model for a loaded dataset."""

    dataset_id: UUID
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    checkpoint: str | None = None


class TorchvisionModelLoadRequest(RequestModel):
    """Load an allowlisted torchvision classifier."""

    architecture: str = Field(min_length=1, max_length=128)
    weights: str | None = None
    num_classes: int = Field(default=1000, gt=1, le=100_000)
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)


class EvaluationRequest(RequestModel):
    """Run a bounded compatibility evaluation."""

    model_version_id: UUID
    dataset_id: UUID
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0)


class CleanBaselineRequest(RequestModel):
    """Run a complete clean baseline for retained registry entries."""

    model_version_id: UUID
    dataset_id: UUID
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=10_000_000)
    warmup_batches: int = Field(default=1, ge=0, le=100)


class AttackEvaluationRequest(RequestModel):
    """Run one bounded first-order attack against registered inputs."""

    model_version_id: UUID
    dataset_id: UUID
    algorithm: AttackAlgorithm
    norm: Literal["linf", "l2"] | None = None
    epsilon: float = Field(default=8 / 255, gt=0.0, le=1.0)
    step_size: float | None = Field(default=None, gt=0.0, le=1.0)
    iterations: int | None = Field(default=None, ge=1, le=100)
    random_start: bool | None = None
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)


class AttackCurveRequest(RequestModel):
    """Run one attack at multiple epsilon strengths for curve visualisation."""

    model_version_id: UUID
    dataset_id: UUID
    algorithm: AttackAlgorithm = AttackAlgorithm.PGD
    epsilons: list[float] = Field(min_length=2, max_length=12)
    step_fraction: float = Field(default=0.25, gt=0.0, le=1.0)
    iterations: int = Field(default=10, ge=1, le=100)
    restarts: int = Field(default=1, ge=1, le=8)
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)

    @field_validator("epsilons")
    @classmethod
    def validate_epsilons(cls, values: list[float]) -> list[float]:
        if any(value <= 0.0 or value > 1.0 for value in values):
            raise ValueError("epsilons must be in the (0, 1] interval")
        if values != sorted(set(values)):
            raise ValueError("epsilons must be strictly increasing")
        return values


class DefenseEvaluationRequest(RequestModel):
    """Run a preprocessing defense before and after adaptive evaluation."""

    model_version_id: UUID
    dataset_id: UUID
    defense: DefenseKind = DefenseKind.BIT_DEPTH
    bit_depth: int = Field(default=4, ge=1, le=8)
    attack_algorithm: AttackAlgorithm = AttackAlgorithm.PGD
    epsilon: float = Field(default=8 / 255, gt=0.0, le=1.0)
    step_size: float | None = Field(default=None, gt=0.0, le=1.0)
    iterations: int | None = Field(default=None, ge=1, le=100)
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)


class TrainingRequest(RequestModel):
    """Train a copied registered model with adversarial training or TRADES."""

    model_version_id: UUID
    dataset_id: UUID
    strategy: TrainingStrategy
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    epochs: int = Field(default=1, ge=1, le=100)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)
    epsilon: float = Field(default=8 / 255, gt=0.0, le=1.0)
    step_size: float = Field(default=2 / 255, gt=0.0, le=1.0)
    attack_iterations: int = Field(default=2, ge=1, le=20)
    learning_rate: float = Field(default=1e-3, gt=0.0, le=1.0)
    trades_beta: float = Field(default=6.0, ge=0.0, le=100.0)


class RobustnessScoreRequest(RequestModel):
    """Aggregate retained attack evidence without hiding raw metrics."""

    attack_run_ids: list[UUID] = Field(min_length=1, max_length=32)


class TransferEvaluationRequest(RequestModel):
    """Generate a black-box transfer attack from a surrogate model."""

    surrogate_model_version_id: UUID
    target_model_version_id: UUID
    dataset_id: UUID
    algorithm: AttackAlgorithm = AttackAlgorithm.PGD
    epsilon: float = Field(default=8 / 255, gt=0.0, le=1.0)
    step_size: float | None = Field(default=None, gt=0.0, le=1.0)
    iterations: int = Field(default=10, ge=1, le=100)
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)


def get_registry(request: Request) -> RegistryService:
    """Resolve the process-local registry from application state."""

    return cast(RegistryService, request.app.state.registry)


RegistryDependency = Annotated[RegistryService, Depends(get_registry)]


def _translate_registry_error(error: Exception) -> HTTPException:
    if isinstance(error, RegistryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
    if isinstance(error, RegistryBusyError):
        # The request is valid; the machine is saturated. Invite a retry.
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(error),
            headers={"Retry-After": "30"},
        )
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))


@router.post(
    "/datasets",
    response_model=DatasetRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Load an approved dataset split",
)
def load_dataset(payload: DatasetLoadRequest, registry: RegistryDependency) -> DatasetRecord:
    try:
        return registry.load_dataset(payload.name, payload.split, download=payload.download)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.get("/datasets", response_model=list[DatasetRecord], summary="List loaded datasets")
def list_datasets(registry: RegistryDependency) -> list[DatasetRecord]:
    return registry.list_datasets()


@router.post(
    "/models/small-cnn",
    response_model=ModelVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Load the built-in CNN",
)
def load_small_cnn(
    payload: SmallCNNLoadRequest, registry: RegistryDependency
) -> ModelVersionRecord:
    try:
        return registry.load_small_cnn(
            payload.dataset_id,
            seed=payload.seed,
            checkpoint=payload.checkpoint,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/models/torchvision",
    response_model=ModelVersionRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Load an allowlisted torchvision model",
)
def load_torchvision_model(
    payload: TorchvisionModelLoadRequest, registry: RegistryDependency
) -> ModelVersionRecord:
    try:
        return registry.load_torchvision_model(
            architecture=payload.architecture,
            weights=payload.weights,
            num_classes=payload.num_classes,
            seed=payload.seed,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.get("/models", response_model=list[ModelVersionRecord], summary="List loaded models")
def list_models(registry: RegistryDependency) -> list[ModelVersionRecord]:
    return registry.list_models()


@router.post(
    "/evaluations",
    response_model=EvaluationResult,
    summary="Run a basic clean compatibility evaluation",
)
def evaluate(payload: EvaluationRequest, registry: RegistryDependency) -> EvaluationResult:
    try:
        return registry.evaluate(
            payload.model_version_id,
            payload.dataset_id,
            seed=payload.seed,
            batch_size=payload.batch_size,
            max_samples=payload.max_samples,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/baselines",
    response_model=BaselineRunRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Run a reproducible clean baseline",
)
def run_baseline(
    payload: CleanBaselineRequest,
    registry: RegistryDependency,
) -> BaselineRunRecord:
    try:
        return registry.run_clean_baseline(
            payload.model_version_id,
            payload.dataset_id,
            config=BaselineConfig(
                seed=payload.seed,
                batch_size=payload.batch_size,
                max_samples=payload.max_samples,
                warmup_batches=payload.warmup_batches,
            ),
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/baselines",
    response_model=list[BaselineRunRecord],
    summary="List completed clean baselines",
)
def list_baselines(registry: RegistryDependency) -> list[BaselineRunRecord]:
    return registry.list_baselines()


@router.get(
    "/baselines/{baseline_id}",
    response_model=BaselineRunRecord,
    summary="Get one clean baseline",
)
def get_baseline(baseline_id: UUID, registry: RegistryDependency) -> BaselineRunRecord:
    try:
        return registry.get_baseline(baseline_id)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/baselines/{baseline_id}/verify",
    response_model=BaselineVerification,
    summary="Verify an exact-configuration baseline rerun",
)
def verify_baseline(baseline_id: UUID, registry: RegistryDependency) -> BaselineVerification:
    try:
        return registry.verify_clean_baseline(baseline_id)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/attacks",
    response_model=AttackRunRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Run a bounded FGSM, BIM, PGD, DeepFool, CW, or AutoAttack evaluation",
)
def run_attack(
    payload: AttackEvaluationRequest,
    registry: RegistryDependency,
) -> AttackRunRecord:
    is_fgsm = payload.algorithm is AttackAlgorithm.FGSM
    is_bim = payload.algorithm is AttackAlgorithm.BIM
    is_deepfool = payload.algorithm is AttackAlgorithm.DEEPFOOL
    is_cw = payload.algorithm is AttackAlgorithm.CARLINI_WAGNER
    is_autoattack = payload.algorithm is AttackAlgorithm.AUTOATTACK
    try:
        config = AttackConfig(
            algorithm=payload.algorithm,
            norm=payload.norm or ("l2" if is_deepfool or is_cw else "linf"),
            epsilon=payload.epsilon,
            step_size=(
                payload.step_size
                if payload.step_size is not None
                else payload.epsilon
                if is_fgsm
                else payload.epsilon
                if is_deepfool or is_cw
                else payload.epsilon / 4
            ),
            iterations=(
                payload.iterations
                if payload.iterations is not None
                else 1
                if is_fgsm
                else 20
                if is_deepfool
                else 50
                if is_cw
                else 10
            ),
            random_start=(
                payload.random_start
                if payload.random_start is not None
                else False
                if is_bim
                else False
                if is_deepfool
                else False
                if is_cw
                else False
                if is_autoattack
                else not is_fgsm
            ),
            seed=payload.seed,
            batch_size=payload.batch_size,
            max_samples=payload.max_samples,
        )
        return registry.run_attack(
            payload.model_version_id,
            payload.dataset_id,
            config=config,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/attacks",
    response_model=list[AttackRunRecord],
    summary="List completed adversarial evaluations",
)
def list_attacks(registry: RegistryDependency) -> list[AttackRunRecord]:
    return registry.list_attacks()


@router.post(
    "/attack-curves",
    response_model=list[AttackRunRecord],
    status_code=status.HTTP_201_CREATED,
    summary="Run a deterministic attack strength curve",
)
def run_attack_curve(
    payload: AttackCurveRequest,
    registry: RegistryDependency,
) -> list[AttackRunRecord]:
    """Evaluate the same population at increasing epsilon values."""

    is_fgsm = payload.algorithm is AttackAlgorithm.FGSM
    is_deepfool = payload.algorithm is AttackAlgorithm.DEEPFOOL
    is_cw = payload.algorithm is AttackAlgorithm.CARLINI_WAGNER
    is_autoattack = payload.algorithm is AttackAlgorithm.AUTOATTACK
    records: list[AttackRunRecord] = []
    try:
        for epsilon in payload.epsilons:
            step_size = (
                epsilon if is_fgsm or is_deepfool or is_cw else epsilon * payload.step_fraction
            )
            for restart in range(payload.restarts):
                records.append(
                    registry.run_attack(
                        payload.model_version_id,
                        payload.dataset_id,
                        config=AttackConfig(
                            algorithm=payload.algorithm,
                            norm="l2" if is_deepfool or is_cw else "linf",
                            epsilon=epsilon,
                            step_size=step_size,
                            iterations=1 if is_fgsm else payload.iterations,
                            random_start=not (is_fgsm or is_deepfool or is_cw or is_autoattack),
                            seed=payload.seed + restart,
                            batch_size=payload.batch_size,
                            max_samples=payload.max_samples,
                        ),
                    )
                )
        return records
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/attacks/{attack_id}",
    response_model=AttackRunRecord,
    summary="Get one adversarial evaluation",
)
def get_attack(attack_id: UUID, registry: RegistryDependency) -> AttackRunRecord:
    try:
        return registry.get_attack(attack_id)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/defenses",
    response_model=DefenseRunRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate a preprocessing defense before and after adaptive attack",
)
def run_defense(
    payload: DefenseEvaluationRequest,
    registry: RegistryDependency,
) -> DefenseRunRecord:
    is_fgsm = payload.attack_algorithm is AttackAlgorithm.FGSM
    is_deepfool = payload.attack_algorithm is AttackAlgorithm.DEEPFOOL
    is_cw = payload.attack_algorithm is AttackAlgorithm.CARLINI_WAGNER
    is_autoattack = payload.attack_algorithm is AttackAlgorithm.AUTOATTACK
    try:
        attack = AttackConfig(
            algorithm=payload.attack_algorithm,
            norm="l2" if is_deepfool or is_cw else "linf",
            epsilon=payload.epsilon,
            step_size=(
                payload.step_size
                if payload.step_size is not None
                else payload.epsilon
                if is_fgsm or is_deepfool or is_cw
                else payload.epsilon / 4
            ),
            iterations=(
                payload.iterations
                if payload.iterations is not None
                else 1
                if is_fgsm
                else 20
                if is_deepfool
                else 50
                if is_cw
                else 10
            ),
            random_start=not (is_fgsm or is_deepfool or is_cw or is_autoattack),
            seed=payload.seed,
            batch_size=payload.batch_size,
            max_samples=payload.max_samples,
        )
        return registry.run_defense(
            payload.model_version_id,
            payload.dataset_id,
            defense=DefenseConfig(kind=payload.defense, bit_depth=payload.bit_depth),
            attack=attack,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/defenses",
    response_model=list[DefenseRunRecord],
    summary="List completed defense evaluations",
)
def list_defenses(registry: RegistryDependency) -> list[DefenseRunRecord]:
    return registry.list_defenses()


@router.post(
    "/defenses/transfer",
    response_model=TransferDefenseRunRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Evaluate surrogate-to-target transfer robustness",
)
def run_transfer(
    payload: TransferEvaluationRequest,
    registry: RegistryDependency,
) -> TransferDefenseRunRecord:
    try:
        is_fgsm = payload.algorithm is AttackAlgorithm.FGSM
        is_deepfool = payload.algorithm is AttackAlgorithm.DEEPFOOL
        is_cw = payload.algorithm is AttackAlgorithm.CARLINI_WAGNER
        if is_deepfool or is_cw or payload.algorithm is AttackAlgorithm.AUTOATTACK:
            raise ValueError("transfer evaluation supports bounded L-infinity attacks only")
        config = AttackConfig(
            algorithm=payload.algorithm,
            norm="l2" if is_deepfool or is_cw else "linf",
            epsilon=payload.epsilon,
            step_size=payload.step_size or (payload.epsilon if is_fgsm else payload.epsilon / 4),
            iterations=1 if is_fgsm else payload.iterations,
            random_start=not (is_fgsm or is_deepfool or is_cw),
            seed=payload.seed,
            batch_size=payload.batch_size,
            max_samples=payload.max_samples,
        )
        return registry.run_transfer(
            payload.surrogate_model_version_id,
            payload.target_model_version_id,
            payload.dataset_id,
            attack=config,
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/defenses/transfer",
    response_model=list[TransferDefenseRunRecord],
    summary="List surrogate-to-target transfer evaluations",
)
def list_transfers(registry: RegistryDependency) -> list[TransferDefenseRunRecord]:
    return registry.list_transfers()


@router.post(
    "/training",
    response_model=TrainingRunRecord,
    status_code=status.HTTP_201_CREATED,
    summary="Train a registered model with adversarial training or TRADES",
)
def train_registered_model(
    payload: TrainingRequest,
    registry: RegistryDependency,
) -> TrainingRunRecord:
    try:
        _, record, _ = registry.train_model(
            payload.model_version_id,
            payload.dataset_id,
            config=TrainingConfig(
                strategy=payload.strategy,
                seed=payload.seed,
                epochs=payload.epochs,
                batch_size=payload.batch_size,
                max_samples=payload.max_samples,
                epsilon=payload.epsilon,
                step_size=payload.step_size,
                attack_iterations=payload.attack_iterations,
                learning_rate=payload.learning_rate,
                trades_beta=payload.trades_beta,
            ),
        )
        return record
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/training",
    response_model=list[TrainingRunRecord],
    summary="List completed robust-training runs",
)
def list_training(registry: RegistryDependency) -> list[TrainingRunRecord]:
    return registry.list_training()


@router.post(
    "/training/jobs",
    response_model=JobRecord,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue adversarial training as a bounded background job",
)
def queue_training(payload: TrainingRequest, registry: RegistryDependency) -> JobRecord:
    try:
        return registry.submit_training_job(
            payload.model_version_id,
            payload.dataset_id,
            config=TrainingConfig(
                strategy=payload.strategy,
                seed=payload.seed,
                epochs=payload.epochs,
                batch_size=payload.batch_size,
                max_samples=payload.max_samples,
                epsilon=payload.epsilon,
                step_size=payload.step_size,
                attack_iterations=payload.attack_iterations,
                learning_rate=payload.learning_rate,
                trades_beta=payload.trades_beta,
            ),
        )
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get("/jobs", response_model=list[JobRecord], summary="List bounded background jobs")
def list_jobs(registry: RegistryDependency) -> list[JobRecord]:
    return registry.list_jobs()


@router.get("/jobs/{job_id}", response_model=JobRecord, summary="Get one background job")
def get_job(job_id: UUID, registry: RegistryDependency) -> JobRecord:
    try:
        return registry.get_job(job_id)
    except RegistryNotFoundError as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/jobs/{job_id}/cancel",
    response_model=JobRecord,
    summary="Cancel a background job that has not started",
)
def cancel_job(job_id: UUID, registry: RegistryDependency) -> JobRecord:
    try:
        return registry.cancel_job(job_id)
    except JobNotCancellableError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except RegistryNotFoundError as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/baselines/{baseline_id}/experiment",
    response_model=ExperimentResult,
    summary="Export one baseline and its evidence as a portable envelope",
)
def export_experiment(baseline_id: UUID, registry: RegistryDependency) -> ExperimentResult:
    try:
        return registry.export_experiment(baseline_id)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/experiments",
    response_model=ExperimentResult,
    status_code=status.HTTP_201_CREATED,
    summary="Import a portable experiment envelope as auditable evidence",
)
def import_experiment(payload: ExperimentResult, registry: RegistryDependency) -> ExperimentResult:
    try:
        return registry.import_experiment(payload)
    except (RegistryError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/experiments",
    response_model=list[ExperimentResult],
    summary="List imported experiment envelopes",
)
def list_experiments(registry: RegistryDependency) -> list[ExperimentResult]:
    return registry.list_experiments()


@router.get(
    "/experiments/{experiment_id}",
    response_model=ExperimentResult,
    summary="Get one imported experiment envelope",
)
def get_experiment(experiment_id: UUID, registry: RegistryDependency) -> ExperimentResult:
    try:
        return registry.get_experiment(experiment_id)
    except RegistryNotFoundError as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/journal/replay",
    response_model=JournalReplaySummary,
    summary="Rebuild the in-memory index from the metadata journal",
)
def replay_journal(registry: RegistryDependency) -> JournalReplaySummary:
    return registry.replay_journal()


@router.get(
    "/journal",
    response_model=list[dict[str, object]],
    summary="Read append-only registry metadata journal",
)
def read_journal(registry: RegistryDependency) -> list[dict[str, object]]:
    return registry.read_journal()


@router.post(
    "/robustness-score",
    response_model=RobustnessScore,
    status_code=status.HTTP_201_CREATED,
    summary="Calculate a transparent robustness score",
)
def calculate_robustness_score(
    payload: RobustnessScoreRequest,
    registry: RegistryDependency,
) -> RobustnessScore:
    try:
        return calculate_score([registry.get_attack(run_id) for run_id in payload.attack_run_ids])
    except (RegistryBusyError, RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/baselines/{baseline_id}/artifacts/{artifact_id}",
    response_class=FileResponse,
    summary="Download a baseline evidence artifact",
)
def download_baseline_artifact(
    baseline_id: UUID,
    artifact_id: UUID,
    registry: RegistryDependency,
) -> FileResponse:
    try:
        artifact, path = registry.get_baseline_artifact(baseline_id, artifact_id)
    except (RegistryBusyError, RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error
    return FileResponse(
        path,
        media_type=artifact.media_type,
        filename=path.name,
        headers={"ETag": f'"{artifact.sha256}"'},
    )
