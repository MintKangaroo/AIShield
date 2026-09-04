"""Run injection probes against an authorized LLM endpoint and record the outcome.

Authorization is checked by the service before this runs. Prompts and completions
are hashed for evidence; the raw text is kept only when the config opts in, because
it can carry sensitive content.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from aishield.llm.contracts import (
    LlmRedTeamConfig,
    LlmRedTeamMetrics,
    LlmRedTeamRunRecord,
    ProbeResult,
)
from aishield.llm.probes import SYSTEM_PROMPT, build_probes
from aishield.llm.remote import LlmEndpoint

#: A completion oracle: (system, prompt) -> completion text.
CompletionOracle = Callable[[str, str], str]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def target_fingerprint(endpoint: LlmEndpoint, config: LlmRedTeamConfig) -> str:
    material = "\0".join(
        [
            "aishield-llm-target-v1",
            endpoint.host,
            ",".join(sorted(category.value for category in config.categories)),
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def run_llm_red_team(
    oracle: CompletionOracle,
    endpoint: LlmEndpoint,
    *,
    config: LlmRedTeamConfig,
) -> LlmRedTeamRunRecord:
    """Send each probe once, detect success, and aggregate the outcomes."""

    probes = build_probes(config.categories)[: config.max_probes]
    if not probes:
        raise ValueError("no probes were selected for the requested categories")

    results: list[ProbeResult] = []
    by_category: dict[str, int] = {}
    successful = 0
    for probe in probes:
        completion = oracle(SYSTEM_PROMPT, probe.prompt)
        succeeded, detail = probe.detect(completion)
        successful += int(succeeded)
        by_category[probe.category.value] = by_category.get(probe.category.value, 0) + int(
            succeeded
        )
        results.append(
            ProbeResult(
                probe_id=probe.probe_id,
                category=probe.category,
                succeeded=succeeded,
                detail=detail,
                prompt_sha256=_sha256(probe.prompt),
                response_sha256=_sha256(completion),
                prompt_text=probe.prompt if config.retain_text else None,
                response_text=completion if config.retain_text else None,
            )
        )

    metrics = LlmRedTeamMetrics(
        total_probes=len(results),
        successful_probes=successful,
        injection_success_rate=successful / len(results),
        by_category=by_category,
    )
    return LlmRedTeamRunRecord(
        id=uuid4(),
        created_at=datetime.now(UTC),
        target_host=endpoint.host,
        target_fingerprint=target_fingerprint(endpoint, config),
        config=config,
        metrics=metrics,
        probes=tuple(results),
        authorized=True,
        warnings=(
            "Diagnostic prompt-injection probes against a remote LLM; success means the "
            "model leaked a planted canary or followed an injected instruction. Prompts "
            "and completions are hashed; raw text is retained only when opted in.",
        ),
    )
