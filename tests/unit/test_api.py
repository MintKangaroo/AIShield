from pathlib import Path
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient

from aishield.api.main import create_app
from aishield.core.config import Settings, get_settings
from aishield.registry.errors import RegistryError
from aishield.registry.service import RegistryService


def test_liveness_reports_cpu_runtime() -> None:
    settings = Settings(environment="test", compute_device="cpu")

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "aishield-api",
        "version": "0.1.0",
        "environment": "test",
        "compute_device": "cpu",
    }


def test_service_metadata_and_openapi_are_exposed() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        metadata = client.get("/api/v1")
        openapi = client.get("/api/openapi.json")

    assert metadata.status_code == 200
    assert metadata.json()["release_scope"] == "image-classification-robustness"
    assert "/api/v1/health/live" in openapi.json()["paths"]
    assert "/api/v1/registry/baselines" in openapi.json()["paths"]
    assert "/api/v1/registry/attacks" in openapi.json()["paths"]
    assert "/api/v1/registry/defenses" in openapi.json()["paths"]


def test_settings_are_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()


def test_readiness_reports_the_journal_backend(tmp_path: Path) -> None:
    settings = Settings(environment="test", artifact_root=tmp_path, replay_journal_on_start=False)

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "metadata_backend": "journal"}


def test_readiness_reports_503_when_the_store_is_unusable(tmp_path: Path) -> None:
    settings = Settings(environment="test", artifact_root=tmp_path, replay_journal_on_start=False)
    app = create_app(settings)

    class BrokenStore:
        def append(self, kind: str, record: object) -> None: ...

        def read(self) -> list[dict[str, object]]:
            return []

        def close(self) -> None: ...

        def check_ready(self) -> None:
            raise RegistryError("metadata database is unreachable")

    app.state.registry = RegistryService(settings, store=cast(Any, BrokenStore()))

    with TestClient(app) as client:
        response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert "unreachable" in response.json()["detail"]
    # Liveness must stay green: the process itself is fine.
    assert TestClient(app).get("/api/v1/health/live").status_code == 200


def test_startup_fails_loudly_when_the_configured_database_is_unreachable() -> None:
    """Starting unable to record any evidence would be worse than not starting."""

    settings = Settings(
        environment="test",
        metadata_backend="postgresql",
        database_url="postgresql://aishield:aishield@127.0.0.1:1/aishield",
    )

    with pytest.raises(RegistryError, match="could not prepare the metadata schema"):
        create_app(settings)
