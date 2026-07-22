"""Service health endpoints."""

from typing import Literal, cast

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from aishield import __version__
from aishield.core.config import Settings

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    """Stable liveness response consumed by Docker and the dashboard."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: Literal["aishield-api"] = "aishield-api"
    version: str = __version__
    environment: str
    compute_device: Literal["cpu", "cuda"]


@router.get("/live", response_model=HealthResponse, summary="Check API liveness")
def liveness(request: Request) -> HealthResponse:
    """Report process liveness without claiming dependency readiness."""

    settings = cast(Settings, request.app.state.settings)
    return HealthResponse(
        environment=settings.environment,
        compute_device=settings.compute_device,
    )
