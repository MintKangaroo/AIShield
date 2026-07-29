"""Dataset, model, and basic evaluation registry endpoints."""

from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from aishield.attacks.contracts import AttackAlgorithm, AttackConfig, AttackRunRecord
from aishield.evaluation.contracts import (
    BaselineConfig,
    BaselineRunRecord,
    BaselineVerification,
)
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    EvaluationResult,
    ModelVersionRecord,
)
from aishield.registry.errors import RegistryError, RegistryNotFoundError
from aishield.registry.service import RegistryService

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


def get_registry(request: Request) -> RegistryService:
    """Resolve the process-local registry from application state."""

    return cast(RegistryService, request.app.state.registry)


RegistryDependency = Annotated[RegistryService, Depends(get_registry)]


def _translate_registry_error(error: Exception) -> HTTPException:
    if isinstance(error, RegistryNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))
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
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error


@router.post(
    "/baselines/{baseline_id}/verify",
    response_model=BaselineVerification,
    summary="Verify an exact-configuration baseline rerun",
)
def verify_baseline(baseline_id: UUID, registry: RegistryDependency) -> BaselineVerification:
    try:
        return registry.verify_clean_baseline(baseline_id)
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError, ValueError) as error:
        raise _translate_registry_error(error) from error


@router.get(
    "/attacks",
    response_model=list[AttackRunRecord],
    summary="List completed adversarial evaluations",
)
def list_attacks(registry: RegistryDependency) -> list[AttackRunRecord]:
    return registry.list_attacks()


@router.get(
    "/attacks/{attack_id}",
    response_model=AttackRunRecord,
    summary="Get one adversarial evaluation",
)
def get_attack(attack_id: UUID, registry: RegistryDependency) -> AttackRunRecord:
    try:
        return registry.get_attack(attack_id)
    except (RegistryError, RegistryNotFoundError) as error:
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
    except (RegistryError, RegistryNotFoundError) as error:
        raise _translate_registry_error(error) from error
    return FileResponse(
        path,
        media_type=artifact.media_type,
        filename=path.name,
        headers={"ETag": f'"{artifact.sha256}"'},
    )
