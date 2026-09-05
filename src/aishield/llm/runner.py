"""Run injection and jailbreak probes against an authorized LLM and record results.

Authorization is checked by the service before this runs. Prompts and completions
are hashed for evidence; raw text is kept only when the config opts in. Both
single-turn and conversation-level probes drive one chat oracle, so a multi-turn
probe sees the model's own replies as it steers.
"""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from aishield.llm.contracts import (
    LlmRedTeamConfig,
    LlmRedTeamMetrics,
    LlmRedTeamRunRecord,
    ProbeCategory,
    ProbeResult,
)
from aishield.llm.probes import (
    SYSTEM_PROMPT,
    build_multi_turn_probes,
    build_probes,
    looks_like_refusal,
)
from aishield.llm.remote import ChatMessage, LlmEndpoint

#: A chat oracle: (system, conversation) -> the model's next completion.
ChatOracle = Callable[[str, list[ChatMessage]], str]


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


def _result(
    probe_id: str,
    category: ProbeCategory,
    prompt: str,
    completion: str,
    *,
    turns: int,
    detect: Callable[[str], tuple[bool, str]],
    retain_text: bool,
) -> tuple[ProbeResult, bool]:
    succeeded, detail = detect(completion)
    result = ProbeResult(
        probe_id=probe_id,
        category=category,
        succeeded=succeeded,
        detail=detail,
        turns=turns,
        refused=looks_like_refusal(completion),
        prompt_sha256=_sha256(prompt),
        response_sha256=_sha256(completion),
        prompt_text=prompt if retain_text else None,
        response_text=completion if retain_text else None,
    )
    return result, succeeded


def run_llm_red_team(
    oracle: ChatOracle,
    endpoint: LlmEndpoint,
    *,
    config: LlmRedTeamConfig,
) -> LlmRedTeamRunRecord:
    """Send each selected probe once, detect success, and aggregate the outcomes."""

    single = build_probes(config.categories)
    multi = build_multi_turn_probes() if ProbeCategory.MULTI_TURN in config.categories else []
    if not single and not multi:
        raise ValueError("no probes were selected for the requested categories")

    results: list[ProbeResult] = []
    by_category: dict[str, int] = {}
    successful = 0

    def record(result: ProbeResult, ok: bool) -> None:
        nonlocal successful
        successful += int(ok)
        by_category[result.category.value] = by_category.get(result.category.value, 0) + int(ok)
        results.append(result)

    for probe in single[: config.max_probes]:
        completion = oracle(SYSTEM_PROMPT, [ChatMessage("user", probe.prompt)])
        result, ok = _result(
            probe.probe_id,
            probe.category,
            probe.prompt,
            completion,
            turns=1,
            detect=probe.detect,
            retain_text=config.retain_text,
        )
        record(result, ok)

    remaining = config.max_probes - len(results)
    for mt_probe in multi[: max(0, remaining)]:
        conversation: list[ChatMessage] = []
        completion = ""
        for turn in mt_probe.turns:
            conversation.append(ChatMessage("user", turn))
            completion = oracle(SYSTEM_PROMPT, conversation)
            conversation.append(ChatMessage("assistant", completion))
        # The transcript of user turns is what we fingerprint/retain for the probe.
        transcript = "\n".join(mt_probe.turns)
        result, ok = _result(
            mt_probe.probe_id,
            mt_probe.category,
            transcript,
            completion,
            turns=len(mt_probe.turns),
            detect=mt_probe.detect,
            retain_text=config.retain_text,
        )
        record(result, ok)

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
            "Diagnostic prompt-injection and jailbreak probes against a remote LLM; success "
            "means the model leaked a planted canary or followed an injected instruction. "
            "Prompts and completions are hashed; raw text is retained only when opted in.",
        ),
    )
