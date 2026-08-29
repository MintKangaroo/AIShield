"""Service health endpoints."""

import logging
from typing import Literal, cast

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict

from aishield import __version__
from aishield.core.config import Settings
from aishield.registry.errors import RegistryError
from aishield.registry.service import RegistryService

logger = logging.getLogger("aishield.api.health")

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Stable liveness response consumed by Docker and the dashboard."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["aishield-api"] = "aishield-api"
    version: str = __version__
    environment: str
    compute_device: Literal["cpu", "cuda"]


class ReadinessResponse(BaseModel):
    """Readiness of the dependencies this process actually uses."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready"] = "ready"
    metadata_backend: Literal["journal", "postgresql"]


@router.get("/live", response_model=HealthResponse, summary="Check API liveness")
def liveness(request: Request) -> HealthResponse:
    """Report process liveness without claiming dependency readiness."""

    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        environment=settings.environment,
        compute_device=settings.compute_device,
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check that the configured metadata store is usable",
)
def readiness(request: Request) -> ReadinessResponse:
    """Verify the metadata store this process depends on, and report which one it is.

    Liveness and readiness stay separate on purpose: a process can be alive while
    its database is unreachable, and reporting that as healthy would hide the
    failure that actually matters for recording evidence.
    """

    settings = cast(Settings, request.app.state.settings)
    registry = cast(RegistryService, request.app.state.registry)
    try:
        registry.check_ready()
    except RegistryError as error:
        logger.warning(
            "readiness check failed",
            extra={"metadata_backend": settings.metadata_backend, "detail": str(error)},
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error
    return ReadinessResponse(metadata_backend=settings.metadata_backend)
