"""Guard against dashboard/API path drift.

The dashboard is a first-class client of this API. A renamed or mistyped route
is invisible to both the Python tests and the TypeScript compiler, so this test
reads the paths the client actually builds and asserts the server serves them.
"""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aishield.api.main import create_app
from aishield.core.config import Settings

CLIENT_SOURCE = Path(__file__).resolve().parents[2] / "web" / "src" / "api.ts"
REGISTRY_PREFIX = "/api/v1/registry"


def _client_paths() -> set[str]:
    """Extract the request paths from the dashboard's API client."""

    source = CLIENT_SOURCE.read_text(encoding="utf-8")
    template_paths = {
        REGISTRY_PREFIX + match
        for match in re.findall(r"`\$\{registryPath\}([^`]*)`", source)
        if match
    }
    literal_paths = {
        match
        for match in re.findall(r'"(/api/v1/[^"]*)"', source)
        # Skip the `registryPath` constant itself; it is a prefix, not a request.
        if match != REGISTRY_PREFIX
    }
    return template_paths | literal_paths


def _served_paths() -> set[str]:
    with TestClient(
        create_app(Settings(environment="test", replay_journal_on_start=False))
    ) as client:
        return set(client.get("/api/openapi.json").json()["paths"])


def _normalise(path: str) -> str:
    """Reduce both a TS interpolation and an OpenAPI parameter to one placeholder.

    A query string is not part of the OpenAPI path, so it is dropped first.
    """

    path = path.split("?", 1)[0]
    return re.sub(r"\$\{[^}]+\}", "{X}", re.sub(r"\{[^}]+\}", "{X}", path))


@pytest.mark.skipif(not CLIENT_SOURCE.exists(), reason="dashboard sources are not checked out")
def test_every_dashboard_path_is_served() -> None:
    served = {_normalise(path) for path in _served_paths()}

    unknown = {path for path in _client_paths() if _normalise(path) not in served}

    assert unknown == set(), f"dashboard calls paths the API does not serve: {sorted(unknown)}"


@pytest.mark.skipif(not CLIENT_SOURCE.exists(), reason="dashboard sources are not checked out")
def test_dashboard_reaches_every_registry_collection() -> None:
    """Every list endpoint should be reachable, or the evidence is invisible."""

    client_paths = {_normalise(path) for path in _client_paths()}
    collections = {
        f"{REGISTRY_PREFIX}/{name}"
        for name in ("datasets", "models", "baselines", "attacks", "defenses", "training", "jobs")
    }

    assert collections <= client_paths
