"""Deterministic execution and content hashing primitives."""

import hashlib
import os
import random
from collections.abc import Mapping
from pathlib import Path
from typing import Final

import numpy as np
import torch
from torch import Tensor

from aishield.registry.errors import RegistryError

HASH_CHUNK_SIZE: Final = 1024 * 1024
MIN_SEED: Final = 0
MAX_SEED: Final = 4_294_967_295


def validate_seed(seed: int) -> None:
    """Validate the portable unsigned 32-bit seed range."""

    if not MIN_SEED <= seed <= MAX_SEED:
        raise RegistryError(f"seed must be between {MIN_SEED} and {MAX_SEED}")


def set_global_seed(seed: int) -> None:
    """Seed Python and PyTorch and request deterministic kernels."""

    validate_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")


def sha256_file(path: Path) -> str:
    """Hash one regular file without loading it all into memory."""

    if not path.is_file() or path.is_symlink():
        raise RegistryError(f"not a regular file: {path}")

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_directory_manifest(root: Path) -> str:
    """Hash sorted relative paths, sizes, and content hashes below ``root``."""

    if not root.is_dir():
        raise RegistryError(f"dataset directory does not exist: {root}")

    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        raise RegistryError(f"dataset directory has no files to fingerprint: {root}")

    digest = hashlib.sha256(b"aishield-dataset-manifest-v1\0")
    for path in files:
        if path.is_symlink():
            raise RegistryError(f"dataset manifest rejects symbolic links: {path}")
        relative_path = path.relative_to(root).as_posix().encode()
        content_digest = bytes.fromhex(sha256_file(path))
        digest.update(len(relative_path).to_bytes(4, "big"))
        digest.update(relative_path)
        digest.update(path.stat().st_size.to_bytes(8, "big"))
        digest.update(content_digest)
    return digest.hexdigest()


def state_dict_sha256(state_dict: Mapping[str, Tensor]) -> str:
    """Build a serialization-independent fingerprint for tensor state."""

    digest = hashlib.sha256(b"aishield-pytorch-state-v1\0")
    for name in sorted(state_dict):
        tensor = state_dict[name].detach().cpu().contiguous()
        name_bytes = name.encode()
        dtype_bytes = str(tensor.dtype).encode()
        shape_bytes = ",".join(str(dimension) for dimension in tensor.shape).encode()
        raw_bytes = tensor.reshape(-1).view(torch.uint8).numpy().tobytes()
        for payload in (name_bytes, dtype_bytes, shape_bytes, raw_bytes):
            digest.update(len(payload).to_bytes(8, "big"))
            digest.update(payload)
    return digest.hexdigest()


def resolve_file_below(root: Path, relative_name: str) -> Path:
    """Resolve a user-selected artifact while preventing path traversal."""

    if not relative_name or Path(relative_name).is_absolute():
        raise RegistryError("checkpoint must be a non-empty relative path")
    resolved_root = root.resolve()
    candidate = (resolved_root / relative_name).resolve()
    if not candidate.is_relative_to(resolved_root):
        raise RegistryError("checkpoint must remain below the configured model root")
    if not candidate.is_file() or candidate.is_symlink():
        raise RegistryError(f"checkpoint does not exist or is not a regular file: {relative_name}")
    return candidate
