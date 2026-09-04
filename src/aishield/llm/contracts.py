"""Strict contracts for LLM prompt-injection red-team runs.

Deliberately distinct from ``aishield.attacks``: the unit of evidence is a probe
outcome, not a perturbed image, and the aggregate is an injection success rate,
not robust accuracy. Raw prompts and completions are sensitive, so by default only
their SHA-256 fingerprints and the detector verdict are retained; keeping the text
is an explicit opt-in.
"""

from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from aishield.registry.contracts import Probability, RegistryModel, Sha256


class ProbeCategory(StrEnum):
    """What a probe is testing for. Diagnostic categories, not an exploit library."""

    #: Try to make the model reveal a secret planted in its system prompt.
    SYSTEM_PROMPT_LEAK = "system_prompt_leak"
    #: Try to make the model follow an injected instruction that overrides its rules.
    INSTRUCTION_OVERRIDE = "instruction_override"


class LlmRedTeamConfig(RegistryModel):
    """Bounded, query-only red-team of a remote LLM endpoint."""

    categories: tuple[ProbeCategory, ...] = Field(min_length=1)
    max_probes: int = Field(default=50, gt=0, le=1000)
    seed: int = Field(ge=0, le=4_294_967_295)
    # Prompts and completions may contain sensitive content; off by default.
    retain_text: bool = False


class ProbeResult(RegistryModel):
    """Outcome of one probe against the target."""

    probe_id: str = Field(min_length=1, max_length=128)
    category: ProbeCategory
    succeeded: bool
    detail: str = Field(min_length=1, max_length=512)
    prompt_sha256: Sha256
    response_sha256: Sha256
    # Populated only when the run explicitly opted to retain text.
    prompt_text: str | None = None
    response_text: str | None = None

    @model_validator(mode="after")
    def validate_text_retention(self) -> Self:
        # A result may omit text (privacy default) or carry both, never one alone,
        # so evidence is never half-redacted in a way that misleads a reader.
        if (self.prompt_text is None) != (self.response_text is None):
            raise ValueError("prompt and response text must be retained together or not at all")
        return self


class LlmRedTeamMetrics(RegistryModel):
    """Aggregate over probe outcomes. No image-model metric appears here."""

    total_probes: int = Field(gt=0)
    successful_probes: int = Field(ge=0)
    injection_success_rate: Probability
    by_category: dict[str, int] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.successful_probes > self.total_probes:
            raise ValueError("successful probes cannot exceed total probes")
        return self


class LlmRedTeamRunRecord(RegistryModel):
    """Evidence for one authorized LLM red-team run against a remote endpoint."""

    id: UUID
    created_at: AwareDatetime
    target_host: str = Field(min_length=1)
    target_fingerprint: Sha256
    config: LlmRedTeamConfig
    metrics: LlmRedTeamMetrics
    probes: tuple[ProbeResult, ...] = Field(min_length=1)
    authorized: Literal[True]
    warnings: tuple[str, ...] = ()
