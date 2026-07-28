from pathlib import Path

import pytest
import torch

from aishield.registry.contracts import ModelSource
from aishield.registry.errors import RegistryError
from aishield.registry.models import (
    SmallCNN,
    SmallCNNAdapter,
    TorchvisionPretrainedAdapter,
    resolve_device,
)


@pytest.mark.parametrize("channels,size", [(1, 28), (3, 32)])
def test_small_cnn_returns_ten_class_logits(channels: int, size: int) -> None:
    model = SmallCNN(input_channels=channels, num_classes=10)

    output = model(torch.zeros(2, channels, size, size))

    assert output.shape == (2, 10)


def test_seeded_small_cnn_has_repeatable_hash_and_artifact(tmp_path: Path) -> None:
    adapter = SmallCNNAdapter(tmp_path / "artifacts", tmp_path / "models", "cpu")

    first = adapter.load(input_channels=1, num_classes=10, seed=1729)
    second = adapter.load(input_channels=1, num_classes=10, seed=1729)
    changed = adapter.load(input_channels=1, num_classes=10, seed=1730)

    assert first.record == second.record
    assert first.record.id != changed.record.id
    assert first.record.source is ModelSource.SMALL_CNN
    assert first.record.device == "cpu"
    assert first.record.parameter_count > 0
    artifact_path = Path(first.record.artifact.uri.removeprefix("file://"))
    assert artifact_path.is_file()
    assert artifact_path.stat().st_size == first.record.artifact.size_bytes


def test_small_cnn_restores_weights_only_checkpoint(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    source = SmallCNN(input_channels=1, num_classes=10)
    torch.save(source.state_dict(), model_root / "checkpoint.pt")
    adapter = SmallCNNAdapter(tmp_path / "artifacts", model_root, "cpu")

    loaded = adapter.load(
        input_channels=1,
        num_classes=10,
        seed=1729,
        checkpoint="checkpoint.pt",
    )

    assert loaded.record.artifact.uri.endswith("checkpoint.pt")
    assert all(
        torch.equal(source.state_dict()[name], loaded.model.state_dict()[name])
        for name in source.state_dict()
    )


def test_small_cnn_rejects_non_tensor_and_incompatible_checkpoints(tmp_path: Path) -> None:
    model_root = tmp_path / "models"
    model_root.mkdir()
    adapter = SmallCNNAdapter(tmp_path / "artifacts", model_root, "cpu")
    torch.save({"metadata": "unsafe"}, model_root / "not-state.pt")
    torch.save(SmallCNN(3, 10).state_dict(), model_root / "wrong-shape.pt")

    with pytest.raises(RegistryError, match="only a PyTorch tensor"):
        adapter.load(input_channels=1, num_classes=10, seed=1, checkpoint="not-state.pt")
    with pytest.raises(RegistryError, match="incompatible"):
        adapter.load(input_channels=1, num_classes=10, seed=1, checkpoint="wrong-shape.pt")


def test_torchvision_adapter_loads_allowlisted_untrained_model(tmp_path: Path) -> None:
    adapter = TorchvisionPretrainedAdapter(tmp_path, "cpu", allow_downloads=False)

    bundle = adapter.load(
        architecture="mobilenet_v3_small",
        weights=None,
        num_classes=10,
        seed=1729,
    )

    assert bundle.record.source is ModelSource.TORCHVISION
    assert bundle.record.architecture == "mobilenet_v3_small"
    assert bundle.record.num_classes == 10
    assert bundle.model(torch.zeros(1, 3, 32, 32)).shape == (1, 10)


def test_torchvision_adapter_enforces_allowlist_and_download_policy(tmp_path: Path) -> None:
    adapter = TorchvisionPretrainedAdapter(tmp_path, "cpu", allow_downloads=False)

    with pytest.raises(RegistryError, match="unsupported torchvision architecture"):
        adapter.load(architecture="alexnet", weights=None, num_classes=10, seed=1)
    with pytest.raises(RegistryError, match="not approved"):
        adapter.load(architecture="resnet18", weights="DEFAULT", num_classes=1000, seed=1)

    approved_adapter = TorchvisionPretrainedAdapter(tmp_path, "cpu", allow_downloads=True)
    with pytest.raises(RegistryError, match="unknown weights"):
        approved_adapter.load(
            architecture="resnet18",
            weights="NOT_A_WEIGHT",
            num_classes=1000,
            seed=1,
        )


def test_device_resolution_does_not_silently_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    assert resolve_device("cpu") == torch.device("cpu")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RegistryError, match="CUDA was requested"):
        resolve_device("cuda")
    with pytest.raises(RegistryError, match="unsupported"):
        resolve_device("mps")
