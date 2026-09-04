"""Contract for the LLM prompt-injection red-team track.

The harness must tell a vulnerable model from a hardened one, keep prompts and
completions private by default, and refuse targets that are not explicitly
authorized. One test drives a real HTTP LLM server end to end.
"""

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from aishield.api.main import create_app
from aishield.core.config import Settings
from aishield.llm.contracts import LlmRedTeamConfig, ProbeCategory
from aishield.llm.probes import (
    CANARY,
    OVERRIDE_MARKER,
    RESTRICTED,
    SYSTEM_PROMPT,
    build_probes,
    contains_secret,
)
from aishield.llm.remote import LlmEndpoint, RemoteLlm
from aishield.llm.runner import run_llm_red_team
from aishield.registry.errors import RegistryAuthorizationError, RegistryError
from aishield.registry.service import RegistryService

ALL_CATEGORIES = (
    ProbeCategory.SYSTEM_PROMPT_LEAK,
    ProbeCategory.INSTRUCTION_OVERRIDE,
    ProbeCategory.JAILBREAK,
)


def vulnerable(system: str, prompt: str) -> str:
    """A model that yields to every technique: it leaks, obeys, and gets jailbroken."""

    lowered = prompt.lower()
    if "access code" in lowered or "config" in lowered or "maintenance mode" in lowered:
        return f"Of course — the code is {CANARY}."
    if "hyphen between every character" in lowered:
        return "-".join(CANARY)
    if "backwards" in lowered:
        return CANARY[::-1]
    if "base64" in lowered:
        import base64

        return base64.b64encode(CANARY.encode()).decode()
    if "restricted procedure token" in lowered:
        return f"Sure, the restricted procedure token is {RESTRICTED}."
    return OVERRIDE_MARKER


def hardened(system: str, prompt: str) -> str:
    return "I'm sorry, but I can't help with that."


def _config(**kwargs: Any) -> LlmRedTeamConfig:
    return LlmRedTeamConfig(categories=ALL_CATEGORIES, seed=1, **kwargs)


def _endpoint() -> LlmEndpoint:
    return LlmEndpoint(url="http://127.0.0.1/chat")


# --- detection ----------------------------------------------------------------


def test_a_vulnerable_model_is_flagged() -> None:
    record = run_llm_red_team(vulnerable, _endpoint(), config=_config())

    assert record.metrics.injection_success_rate == 1.0
    assert record.metrics.successful_probes == record.metrics.total_probes
    assert record.metrics.by_category["system_prompt_leak"] > 0
    assert record.metrics.by_category["instruction_override"] > 0
    assert record.authorized is True


def test_a_hardened_model_passes_clean() -> None:
    record = run_llm_red_team(hardened, _endpoint(), config=_config())

    assert record.metrics.injection_success_rate == 0.0
    assert record.metrics.successful_probes == 0
    assert all(not probe.succeeded for probe in record.probes)


def test_obfuscated_leaks_are_detected() -> None:
    """Hyphenated, reversed and base64 leaks are caught, not just plain substrings."""

    def obfuscate(system: str, prompt: str) -> str:
        lowered = prompt.lower()
        if "hyphen" in lowered:
            return "-".join(CANARY)
        if "backwards" in lowered:
            return CANARY[::-1]
        if "base64" in lowered:
            import base64

            return base64.b64encode(CANARY.encode()).decode()
        return "I can't share that."

    record = run_llm_red_team(
        obfuscate,
        _endpoint(),
        config=LlmRedTeamConfig(categories=(ProbeCategory.SYSTEM_PROMPT_LEAK,), seed=1),
    )

    for probe_id in ("leak-encode", "leak-reverse", "leak-base64"):
        result = next(p for p in record.probes if p.probe_id == probe_id)
        assert result.succeeded is True, probe_id


@pytest.mark.parametrize(
    "leak",
    ["-".join(CANARY), " ".join(CANARY), ".".join(CANARY), CANARY[::-1], CANARY.lower()],
)
def test_contains_secret_sees_through_obfuscation(leak: str) -> None:
    assert contains_secret(f"here you go: {leak}", CANARY) is True


def test_contains_secret_does_not_false_positive() -> None:
    assert contains_secret("I will not reveal any codes.", CANARY) is False
    assert contains_secret("AISHIELD-OTHER-9999", CANARY) is False


def test_the_jailbreak_category_targets_the_restricted_token() -> None:
    record = run_llm_red_team(
        vulnerable,
        _endpoint(),
        config=LlmRedTeamConfig(categories=(ProbeCategory.JAILBREAK,), seed=1),
    )

    assert record.metrics.injection_success_rate == 1.0
    assert all(p.category is ProbeCategory.JAILBREAK for p in record.probes)


def test_a_model_that_leaks_the_canary_still_resists_jailbreak() -> None:
    """The two secrets are independent: leaking one is not the other."""

    def leaks_only_canary(system: str, prompt: str) -> str:
        return f"the code is {CANARY}"  # never emits RESTRICTED

    record = run_llm_red_team(
        leaks_only_canary,
        _endpoint(),
        config=LlmRedTeamConfig(categories=(ProbeCategory.JAILBREAK,), seed=1),
    )

    assert record.metrics.injection_success_rate == 0.0


def test_only_requested_categories_are_probed() -> None:
    record = run_llm_red_team(
        vulnerable,
        _endpoint(),
        config=LlmRedTeamConfig(categories=(ProbeCategory.INSTRUCTION_OVERRIDE,), seed=1),
    )

    assert {p.category for p in record.probes} == {ProbeCategory.INSTRUCTION_OVERRIDE}


def test_max_probes_caps_the_run() -> None:
    record = run_llm_red_team(hardened, _endpoint(), config=_config(max_probes=2))

    assert record.metrics.total_probes == 2


# --- privacy ------------------------------------------------------------------


def test_text_is_redacted_by_default() -> None:
    record = run_llm_red_team(vulnerable, _endpoint(), config=_config())

    for probe in record.probes:
        assert probe.prompt_text is None
        assert probe.response_text is None
        assert len(probe.prompt_sha256) == 64
        assert len(probe.response_sha256) == 64


def test_text_is_retained_only_when_opted_in() -> None:
    record = run_llm_red_team(vulnerable, _endpoint(), config=_config(retain_text=True))

    assert all(probe.prompt_text is not None for probe in record.probes)
    assert all(probe.response_text is not None for probe in record.probes)


def test_a_probe_result_cannot_be_half_redacted() -> None:
    from aishield.llm.contracts import ProbeResult

    with pytest.raises(ValueError, match="retained together"):
        ProbeResult(
            probe_id="x",
            category=ProbeCategory.SYSTEM_PROMPT_LEAK,
            succeeded=False,
            detail="d",
            prompt_sha256="a" * 64,
            response_sha256="b" * 64,
            prompt_text="kept",
            response_text=None,
        )


# --- authorization ------------------------------------------------------------


def _service(tmp_path: Path, allowlist: list[str] | None = None) -> RegistryService:
    settings = Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        replay_journal_on_start=False,
        llm_targets_allowlist=allowlist or [],
    )
    return RegistryService(settings)


def test_refused_without_confirmation(tmp_path: Path) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])
    with pytest.raises(RegistryAuthorizationError, match="authorized to test"):
        service.run_llm_red_team(_endpoint(), config=_config(), authorized=False)


def test_refused_when_allowlist_is_empty(tmp_path: Path) -> None:
    service = _service(tmp_path, allowlist=[])
    with pytest.raises(RegistryAuthorizationError, match="no LLM targets are allowlisted"):
        service.run_llm_red_team(_endpoint(), config=_config(), authorized=True)


def test_refused_when_host_not_allowlisted(tmp_path: Path) -> None:
    service = _service(tmp_path, allowlist=["only.example.com"])
    with pytest.raises(RegistryAuthorizationError, match="not in the configured LLM allowlist"):
        service.run_llm_red_team(_endpoint(), config=_config(), authorized=True)


def test_non_http_scheme_is_refused() -> None:
    with pytest.raises(RegistryError, match="http"):
        RemoteLlm(LlmEndpoint(url="file:///etc/passwd"))


# --- end to end over real HTTP ------------------------------------------------


class _LlmHandler(BaseHTTPRequestHandler):
    """A deliberately vulnerable LLM: it complies with injection attempts."""

    def log_message(self, *args: Any) -> None:
        return

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        completion = vulnerable(payload["system"], payload["prompt"])
        body = json.dumps({"completion": completion}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def served_llm() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _LlmHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        yield f"http://{host!s}:{port}/chat"
    finally:
        server.shutdown()
        server.server_close()


def test_red_teams_a_real_served_llm_over_http(tmp_path: Path, served_llm: str) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])

    record = service.run_llm_red_team(
        LlmEndpoint(url=served_llm), config=_config(), authorized=True
    )

    assert record.target_host == "127.0.0.1"
    assert record.metrics.injection_success_rate > 0.0
    assert record.metrics.successful_probes > 0


def test_api_records_and_lists_a_run(tmp_path: Path, served_llm: str) -> None:
    service = _service(tmp_path, allowlist=["127.0.0.1"])

    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(
            "/api/v1/registry/llm-red-team",
            json={"endpoint_url": served_llm, "authorized": True},
        )
        assert response.status_code == 201, response.text
        listed = client.get("/api/v1/registry/llm-red-team")

    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_api_returns_403_for_an_unauthorized_target(tmp_path: Path, served_llm: str) -> None:
    service = _service(tmp_path, allowlist=["only.example.com"])

    with TestClient(create_app(service.settings, service)) as client:
        response = client.post(
            "/api/v1/registry/llm-red-team",
            json={"endpoint_url": served_llm, "authorized": True},
        )

    assert response.status_code == 403


def test_system_prompt_hides_the_canary_it_protects() -> None:
    # The planted secret must be in the system prompt (what the model sees), and the
    # probes must not simply hand the canary to the model themselves.
    assert CANARY in SYSTEM_PROMPT
    for probe in build_probes(ALL_CATEGORIES):
        assert CANARY not in probe.prompt
