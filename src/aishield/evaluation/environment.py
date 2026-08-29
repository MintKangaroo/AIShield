"""Capture environment versions without invoking external commands."""

import os
import platform
import re
from pathlib import Path
from typing import Final, Literal, cast

import matplotlib
import numpy as np
import torch
import torchvision

from aishield import __version__
from aishield.evaluation.contracts import BaselineEnvironment

GIT_HASH_PATTERN: Final = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
GIT_REF_PATTERN: Final = re.compile(r"^refs/[A-Za-z0-9._/-]+$")


def _validated_git_hash(candidate: str | None) -> str | None:
    normalized = candidate.strip().lower() if candidate is not None else ""
    return normalized if GIT_HASH_PATTERN.fullmatch(normalized) else None


def _read_ref(git_directory: Path, reference: str) -> str | None:
    if not GIT_REF_PATTERN.fullmatch(reference) or ".." in reference:
        return None
    loose_ref = git_directory / reference
    if loose_ref.is_file() and not loose_ref.is_symlink():
        return _validated_git_hash(loose_ref.read_text(encoding="utf-8"))

    packed_refs = git_directory / "packed-refs"
    if not packed_refs.is_file() or packed_refs.is_symlink():
        return None
    for line in packed_refs.read_text(encoding="utf-8").splitlines():
        if line.startswith(("#", "^")):
            continue
        fields = line.split(" ", maxsplit=1)
        if len(fields) == 2 and fields[1] == reference:
            return _validated_git_hash(fields[0])
    return None


def discover_git_commit() -> str | None:
    """Read an injected or local repository commit without spawning Git."""

    injected = _validated_git_hash(os.getenv("AISHIELD_GIT_COMMIT"))
    if injected is not None:
        return injected

    for parent in Path(__file__).resolve().parents:
        git_directory = parent / ".git"
        head = git_directory / "HEAD"
        if not head.is_file() or head.is_symlink():
            continue
        content = head.read_text(encoding="utf-8").strip()
        direct = _validated_git_hash(content)
        if direct is not None:
            return direct
        prefix = "ref: "
        if content.startswith(prefix):
            return _read_ref(git_directory, content.removeprefix(prefix))
    return None


def capture_environment(device: torch.device) -> BaselineEnvironment:
    """Capture runtime and ML package versions for one evaluation."""

    cudnn_version = torch.backends.cudnn.version()  # type: ignore[no-untyped-call]
    return BaselineEnvironment(
        python_version=platform.python_version(),
        platform=platform.platform(),
        package_versions={
            "aishield": __version__,
            "matplotlib": matplotlib.__version__,
            "numpy": np.__version__,
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
        },
        git_commit=discover_git_commit(),
        container_image_digest=os.getenv("AISHIELD_CONTAINER_IMAGE_DIGEST") or None,
        device=cast(Literal["cpu", "cuda"], device.type),
        cuda_version=torch.version.cuda,
        cudnn_version=str(cudnn_version) if cudnn_version is not None else None,
        deterministic_algorithms=True,
    )
