"""Dataset, model, and basic evaluation registry endpoints."""

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

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
