import random
from pathlib import Path

import numpy as np
import pytest
import torch

from aishield.registry.errors import RegistryError
from aishield.registry.reproducibility import (
    resolve_file_below,
    set_global_seed,
    sha256_directory_manifest,
    sha256_file,
    state_dict_sha256,
    validate_seed,
)


def test_global_seed_repeats_python_and_torch_sequences() -> None:
    set_global_seed(1729)
    first = (random.random(), np.random.random(3), torch.rand(3))
    set_global_seed(1729)
    second = (random.random(), np.random.random(3), torch.rand(3))

    assert first[0] == second[0]
    assert np.array_equal(first[1], second[1])
    assert torch.equal(first[2], second[2])
    assert torch.are_deterministic_algorithms_enabled()
    assert torch.backends.cudnn.deterministic
    assert not torch.backends.cudnn.benchmark


@pytest.mark.parametrize("seed", [-1, 4_294_967_296])
def test_seed_range_is_validated(seed: int) -> None:
    with pytest.raises(RegistryError, match="seed must be between"):
        validate_seed(seed)


def test_file_and_directory_hashes_detect_content_changes(tmp_path: Path) -> None:
    first = tmp_path / "a.bin"
    nested = tmp_path / "nested"
    nested.mkdir()
    second = nested / "b.bin"
    first.write_bytes(b"alpha")
    second.write_bytes(b"beta")

    file_digest = sha256_file(first)
    manifest_before = sha256_directory_manifest(tmp_path)
    second.write_bytes(b"changed")
    manifest_after = sha256_directory_manifest(tmp_path)

    assert len(file_digest) == 64
    assert manifest_before != manifest_after


def test_hashing_rejects_missing_empty_and_symbolic_link_inputs(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="not a regular file"):
        sha256_file(tmp_path / "missing")
    with pytest.raises(RegistryError, match="no files"):
        sha256_directory_manifest(tmp_path)

    target = tmp_path / "target.bin"
    target.write_bytes(b"content")
    link = tmp_path / "link.bin"
    link.symlink_to(target)
    with pytest.raises(RegistryError, match="symbolic links"):
        sha256_directory_manifest(tmp_path)


def test_directory_hash_rejects_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(RegistryError, match="does not exist"):
        sha256_directory_manifest(tmp_path / "missing")


def test_state_dict_fingerprint_is_order_independent_and_value_sensitive() -> None:
    first = {"weight": torch.tensor([[1.0, 2.0]]), "bias": torch.tensor([3.0])}
    reordered = {"bias": torch.tensor([3.0]), "weight": torch.tensor([[1.0, 2.0]])}
    changed = {"weight": torch.tensor([[1.0, 2.1]]), "bias": torch.tensor([3.0])}

    assert state_dict_sha256(first) == state_dict_sha256(reordered)
    assert state_dict_sha256(first) != state_dict_sha256(changed)


def test_checkpoint_resolution_stays_below_configured_root(tmp_path: Path) -> None:
    root = tmp_path / "models"
    root.mkdir()
    checkpoint = root / "model.pt"
    checkpoint.write_bytes(b"weights")

    assert resolve_file_below(root, "model.pt") == checkpoint
    with pytest.raises(RegistryError, match="non-empty relative"):
        resolve_file_below(root, str(checkpoint))
    with pytest.raises(RegistryError, match="remain below"):
        resolve_file_below(root, "../outside.pt")
    with pytest.raises(RegistryError, match="does not exist"):
        resolve_file_below(root, "missing.pt")
