"""Contract for optional API key authentication.

Two properties matter most. Without a configured key the API behaves exactly as
before, so the demo and CI need no secret. With one, the whole registry surface
is closed — including reads, because the artifacts served there are the evidence
this platform exists to protect.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from aishield.api.main import create_app
from aishield.api.security import API_KEY_HEADER
from aishield.core.config import Settings

KEY = "an-api-key-long-enough"
OTHER = "a-different-key-entirely"


def _settings(tmp_path: Path, api_key: str | None = None) -> Settings:
    return Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
        api_key=SecretStr(api_key) if api_key is not None else None,
    )


def test_a_short_key_is_refused_at_startup(tmp_path: Path) -> None:
    """A key weak enough to guess should stop the process, not protect it."""

    with pytest.raises(ValueError):
        _settings(tmp_path, "tooshort")


def test_registry_is_open_when_no_key_is_configured(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path))) as client:
        assert client.get("/api/v1/registry/datasets").status_code == 200
        # An unexpected key is simply ignored rather than rejected.
        assert (
            client.get(
                "/api/v1/registry/datasets", headers={API_KEY_HEADER: "anything"}
            ).status_code
            == 200
        )


def test_registry_requires_the_key_when_configured(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        response = client.get("/api/v1/registry/datasets")

    assert response.status_code == 401
    assert API_KEY_HEADER in response.headers["WWW-Authenticate"]
    assert "API key is required" in response.json()["detail"]


@pytest.mark.parametrize(
    "headers",
    [
        {API_KEY_HEADER: KEY},
        {"Authorization": f"Bearer {KEY}"},
    ],
    ids=["api-key-header", "bearer-token"],
)
def test_either_accepted_header_authenticates(headers: dict[str, str], tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        assert client.get("/api/v1/registry/datasets", headers=headers).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {API_KEY_HEADER: OTHER},
        {"Authorization": f"Bearer {OTHER}"},
        {"Authorization": KEY},  # missing the Bearer prefix
        {"Authorization": "Bearer "},  # empty credential
        {API_KEY_HEADER: ""},
    ],
)
def test_a_wrong_or_malformed_credential_is_rejected(
    headers: dict[str, str], tmp_path: Path
) -> None:
    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        assert client.get("/api/v1/registry/datasets", headers=headers).status_code == 401


def test_writes_are_protected_too(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        response = client.post(
            "/api/v1/registry/datasets",
            json={"name": "synthetic", "split": "test", "download": False},
        )

    assert response.status_code == 401


def test_artifact_downloads_are_protected(tmp_path: Path) -> None:
    """Artifacts are the recorded evidence; leaving reads open would defeat the point."""

    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        response = client.get(
            "/api/v1/registry/baselines/"
            "00000000-0000-0000-0000-000000000000/artifacts/"
            "00000000-0000-0000-0000-000000000000"
        )

    # 401 rather than 404: an unauthenticated caller learns nothing about what exists.
    assert response.status_code == 401


def test_health_probes_stay_open(tmp_path: Path) -> None:
    """A probe must work without a credential, and it reveals nothing sensitive."""

    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        assert client.get("/api/v1/health/live").status_code == 200
        assert client.get("/api/v1/health/ready").status_code == 200


def test_discovery_and_schema_stay_open(tmp_path: Path) -> None:
    with TestClient(create_app(_settings(tmp_path, KEY))) as client:
        assert client.get("/api/v1").status_code == 200
        assert client.get("/api/openapi.json").status_code == 200


def test_every_registry_route_is_covered(tmp_path: Path) -> None:
    """Protection is applied to the router, so a new route cannot be forgotten."""

    application = create_app(_settings(tmp_path, KEY))
    with TestClient(application) as client:
        paths = [
            path
            for path in client.get("/api/openapi.json").json()["paths"]
            if path.startswith("/api/v1/registry")
        ]

        assert paths, "expected registry routes to exist"
        for path in paths:
            probe = path.replace("{baseline_id}", "00000000-0000-0000-0000-000000000000")
            probe = probe.replace("{artifact_id}", "00000000-0000-0000-0000-000000000000")
            probe = probe.replace("{attack_id}", "00000000-0000-0000-0000-000000000000")
            probe = probe.replace("{job_id}", "00000000-0000-0000-0000-000000000000")
            probe = probe.replace("{experiment_id}", "00000000-0000-0000-0000-000000000000")
            assert client.get(probe).status_code in {401, 405}, probe


def test_the_key_never_reaches_the_logs(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with (
        caplog.at_level("DEBUG"),
        TestClient(create_app(_settings(tmp_path, KEY))) as client,
    ):
        client.get("/api/v1/registry/datasets", headers={API_KEY_HEADER: OTHER})

    assert KEY not in caplog.text
    assert OTHER not in caplog.text


def test_the_key_is_not_exposed_through_settings_repr(tmp_path: Path) -> None:
    settings = _settings(tmp_path, KEY)

    assert KEY not in repr(settings)
    assert settings.api_key is not None
    assert settings.api_key.get_secret_value() == KEY
