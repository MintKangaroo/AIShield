"""Contract for the provenance recorded alongside every evaluation.

`container_image_digest` existed in the evidence contract but nothing ever set
it, so every recorded run claimed unknown provenance. These tests pin down what
is accepted and, more importantly, what is refused: a malformed value must not
become evidence.
"""

import pytest
import torch

from aishield.evaluation.environment import (
    capture_environment,
    discover_container_image_digest,
)

BARE = "sha256:" + "a" * 64
REFERENCED = "ghcr.io/mintkangaroo/aishield:0.1.0@sha256:" + "b" * 64


def test_no_digest_is_reported_as_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AISHIELD_CONTAINER_IMAGE_DIGEST", raising=False)

    assert discover_container_image_digest() is None


@pytest.mark.parametrize("value", [BARE, REFERENCED])
def test_a_well_formed_digest_is_recorded(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISHIELD_CONTAINER_IMAGE_DIGEST", value)

    assert discover_container_image_digest() == value


def test_surrounding_whitespace_is_tolerated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISHIELD_CONTAINER_IMAGE_DIGEST", f"  {BARE}\n")

    assert discover_container_image_digest() == BARE


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "latest",
        "sha256:tooshort",
        "sha256:" + "a" * 63,
        "sha256:" + "a" * 65,
        "sha256:" + "A" * 64,  # digests are lowercase hex
        "md5:" + "a" * 64,
        "sha256:" + "g" * 64,  # not hexadecimal
        "; rm -rf /",
    ],
)
def test_a_malformed_digest_is_refused_rather_than_recorded(
    value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bad provenance is worse than absent provenance: it misleads a reproducer."""

    monkeypatch.setenv("AISHIELD_CONTAINER_IMAGE_DIGEST", value)

    assert discover_container_image_digest() is None


def test_captured_environment_carries_the_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AISHIELD_CONTAINER_IMAGE_DIGEST", REFERENCED)

    environment = capture_environment(torch.device("cpu"))

    assert environment.container_image_digest == REFERENCED
    assert environment.deterministic_algorithms is True


def test_captured_environment_omits_a_malformed_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AISHIELD_CONTAINER_IMAGE_DIGEST", "not-a-digest")

    assert capture_environment(torch.device("cpu")).container_image_digest is None
