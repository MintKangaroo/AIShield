from fastapi.testclient import TestClient

from aishield.api.main import create_app
from aishield.core.config import Settings, get_settings


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


def test_settings_are_cached() -> None:
    get_settings.cache_clear()
    assert get_settings() is get_settings()
