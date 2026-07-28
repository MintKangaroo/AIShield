"""FastAPI application factory and development entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from aishield import __version__
from aishield.api.routes.health import router as health_router
from aishield.api.routes.registry import router as registry_router
from aishield.core.config import Settings, get_settings
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
    application = FastAPI(
        title="AIShield API",
        summary="Reproducible adversarial-robustness research platform",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    application.state.settings = runtime_settings
    application.state.registry = registry or RegistryService(runtime_settings)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "Authorization"],
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(registry_router, prefix="/api/v1")

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
