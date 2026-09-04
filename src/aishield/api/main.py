"""FastAPI application factory and development entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from aishield import __version__
from aishield.api.middleware import RequestContextMiddleware
from aishield.api.routes.health import router as health_router
from aishield.api.routes.registry import router as registry_router
from aishield.api.security import API_KEY_HEADER, ApiKeyDependency
from aishield.core.config import Settings, get_settings
from aishield.core.logging import configure_logging
from aishield.registry.service import RegistryService


class ServiceMetadata(BaseModel):
    """Public metadata for API discovery."""

    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    release_scope: str
    documentation: str


def create_app(
    settings: Settings | None = None, registry: RegistryService | None = None
) -> FastAPI:
    """Build an application with explicit, testable settings."""

    runtime_settings = settings or get_settings()
    configure_logging(runtime_settings.log_level)

    @asynccontextmanager
    async def lifespan(running: FastAPI) -> AsyncIterator[None]:
        yield
        # Release the worker threads and any database pool the store holds, so a
        # reload or a test client teardown does not leak connections.
        service: RegistryService = running.state.registry
        service.shutdown()

    application = FastAPI(
        title="AIShield API",
        summary="Reproducible adversarial-robustness research platform",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    service = registry or RegistryService(runtime_settings)
    application.state.registry = service
    if runtime_settings.replay_journal_on_start:
        # Recovery must never keep the API from starting: a damaged or partially
        # written journal is reported and skipped, not raised.
        try:
            service.replay_journal()
        except Exception:  # noqa: BLE001 - startup must survive a bad journal
            logging.getLogger("aishield.registry").exception("journal replay failed at startup")
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", API_KEY_HEADER],
        expose_headers=["X-Request-ID"],
    )
    application.include_router(health_router, prefix="/api/v1")
    # Applied to the router, so a new route is protected by default rather than
    # by remembering to decorate it.
    application.include_router(registry_router, prefix="/api/v1", dependencies=[ApiKeyDependency])

    @application.get("/api/v1", response_model=ServiceMetadata, tags=["system"])
    def metadata() -> ServiceMetadata:
        return ServiceMetadata(
            name="AIShield",
            version=__version__,
            release_scope="image-classification-robustness",
            documentation="/api/docs",
        )

    return application


app = create_app()


def run() -> None:
    """Run the local development server."""

    import uvicorn

    uvicorn.run(
        "aishield.api.main:app",
        host="0.0.0.0",  # noqa: S104 - container entry point must accept external traffic
        port=8000,
        reload=False,
    )
