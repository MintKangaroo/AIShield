"""Small CNN and torchvision model adapters with content-addressed artifacts."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

import torch
import torchvision
from torch import Tensor, nn
from torchvision.models import get_model, get_model_weights, get_weight

from aishield.registry.contracts import ModelArtifactRecord, ModelSource, ModelVersionRecord
from aishield.registry.errors import RegistryError
from aishield.registry.reproducibility import (
    resolve_file_below,
    set_global_seed,
    sha256_file,
    state_dict_sha256,
)


class SmallCNN(nn.Module):
    """Compact convolutional baseline for MNIST and CIFAR-10."""

    def __init__(self, input_channels: int, num_classes: int) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(input_channels, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2),
            nn.AdaptiveAvgPool2d((4, 4)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 4 * 4, 128),
            nn.ReLU(),
            nn.Linear(128, num_classes),
        )

    def forward(self, inputs: Tensor) -> Tensor:
        """Return unnormalized class logits."""

        return cast(Tensor, self.classifier(self.features(inputs)))


@dataclass(frozen=True, slots=True)
class ModelBundle:
    """Runtime model paired with metadata and deterministic preprocessing."""

    model: nn.Module
    record: ModelVersionRecord
    preprocess: Callable[[Tensor], Tensor]


def identity_preprocess(inputs: Tensor) -> Tensor:
    """Leave already tensorized inputs unchanged."""

    return inputs


def resolve_device(device_name: str) -> torch.device:
    """Resolve a configured device without silently falling back to CPU."""

    if device_name == "cuda" and not torch.cuda.is_available():
        raise RegistryError("CUDA was requested but is not available")
    if device_name not in {"cpu", "cuda"}:
        raise RegistryError(f"unsupported compute device: {device_name}")
    return torch.device(device_name)


def _parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())


def _store_model_artifact(
    model: nn.Module, artifact_root: Path, state_sha256: str
) -> ModelArtifactRecord:
    model_root = artifact_root / "models"
    model_root.mkdir(parents=True, exist_ok=True)
    destination = model_root / f"{state_sha256}.pt"
    if not destination.exists():
        temporary = model_root / f".{state_sha256}.{uuid4().hex}.tmp"
        try:
            torch.save(model.state_dict(), temporary)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
    return ModelArtifactRecord(
        uri=destination.resolve().as_uri(),
        sha256=sha256_file(destination),
        size_bytes=destination.stat().st_size,
    )


def _load_state_dict(model: nn.Module, model_root: Path, checkpoint: str) -> Path:
    checkpoint_path = resolve_file_below(model_root, checkpoint)
    loaded = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    if not isinstance(loaded, Mapping) or not all(
        isinstance(name, str) and isinstance(tensor, Tensor) for name, tensor in loaded.items()
    ):
        raise RegistryError("checkpoint must contain only a PyTorch tensor state dictionary")
    state_dict = cast(Mapping[str, Tensor], loaded)
    try:
        model.load_state_dict(state_dict, strict=True)
    except RuntimeError as error:
        raise RegistryError(f"checkpoint is incompatible with the model: {error}") from error
    return checkpoint_path


class SmallCNNAdapter:
    """Create or safely restore the built-in CNN."""

    architecture: Final = "SmallCNN"
    version: Final = "small-cnn-v1"

    def __init__(self, artifact_root: Path, model_root: Path, device_name: str) -> None:
        self.artifact_root = artifact_root
        self.model_root = model_root
        self.device = resolve_device(device_name)

    def load(
        self,
        *,
        input_channels: int,
        num_classes: int,
        seed: int,
        checkpoint: str | None = None,
    ) -> ModelBundle:
        """Build the seeded model and optionally restore a weights-only checkpoint."""

        set_global_seed(seed)
        model = SmallCNN(input_channels=input_channels, num_classes=num_classes)
        source_artifact: Path | None = None
        if checkpoint is not None:
            source_artifact = _load_state_dict(model, self.model_root, checkpoint)
        model.eval().to(self.device)
        state_sha256 = state_dict_sha256(model.state_dict())
        artifact = (
            ModelArtifactRecord(
                uri=source_artifact.resolve().as_uri(),
                sha256=sha256_file(source_artifact),
                size_bytes=source_artifact.stat().st_size,
            )
            if source_artifact is not None
            else _store_model_artifact(model, self.artifact_root, state_sha256)
        )
        identity = f"{self.version}:{input_channels}:{num_classes}:{state_sha256}"
        record = ModelVersionRecord(
            id=uuid5(NAMESPACE_URL, f"aishield:model:{identity}"),
            name="AIShield Small CNN",
            version=self.version,
            source=ModelSource.SMALL_CNN,
            framework_version=torch.__version__,
            architecture=self.architecture,
            seed=seed,
            num_classes=num_classes,
            input_channels=input_channels,
            parameter_count=_parameter_count(model),
            state_dict_sha256=state_sha256,
            preprocessing="identity (dataset ToTensor output)",
            device=cast(Any, self.device.type),
            artifact=artifact,
        )
        return ModelBundle(model=model, record=record, preprocess=identity_preprocess)


class TorchvisionPretrainedAdapter:
    """Load a bounded set of torchvision classifiers and official weights."""

    supported_architectures: Final = (
        "efficientnet_b0",
        "mobilenet_v3_small",
        "resnet18",
    )

    def __init__(self, artifact_root: Path, device_name: str, *, allow_downloads: bool) -> None:
        self.artifact_root = artifact_root
        self.device = resolve_device(device_name)
        self.allow_downloads = allow_downloads

    def load(
        self,
        *,
        architecture: str,
        weights: str | None,
        num_classes: int,
        seed: int,
    ) -> ModelBundle:
        """Load an untrained or officially pretrained torchvision classifier."""

        if architecture not in self.supported_architectures:
            supported = ", ".join(self.supported_architectures)
            raise RegistryError(f"unsupported torchvision architecture; choose one of: {supported}")
        if weights is not None and not self.allow_downloads:
            raise RegistryError(
                "public pretrained weight downloads are not approved by configuration"
            )

        set_global_seed(seed)
        resolved_weights: Any = None
        preprocessing = "identity (untrained torchvision model)"
        model_num_classes = num_classes
        preprocess: Callable[[Tensor], Tensor] = identity_preprocess
        if weights is not None:
            weights_enum = get_model_weights(architecture)
            try:
                resolved_weights = (
                    weights_enum.DEFAULT
                    if weights == "DEFAULT"
                    else get_weight(f"{weights_enum.__name__}.{weights}")
                )
            except (AttributeError, KeyError, ValueError) as error:
                raise RegistryError(f"unknown weights '{weights}' for {architecture}") from error
            categories = resolved_weights.meta.get("categories")
            if not isinstance(categories, list):
                raise RegistryError("pretrained weights do not declare ImageNet categories")
            model_num_classes = len(categories)
            transform = resolved_weights.transforms()
            preprocess = cast(Callable[[Tensor], Tensor], transform)
            preprocessing = str(transform)

        try:
            model = (
                get_model(architecture, weights=resolved_weights)
                if resolved_weights is not None
                else get_model(architecture, weights=None, num_classes=num_classes)
            )
        except (TypeError, ValueError) as error:
            raise RegistryError(f"could not construct torchvision model: {error}") from error
        model.eval().to(self.device)
        state_sha256 = state_dict_sha256(model.state_dict())
        artifact = _store_model_artifact(model, self.artifact_root, state_sha256)
        version = f"torchvision-{torchvision.__version__}:{weights or 'untrained'}"
        identity = f"{architecture}:{version}:{model_num_classes}:{state_sha256}"
        record = ModelVersionRecord(
            id=uuid5(NAMESPACE_URL, f"aishield:model:{identity}"),
            name=f"torchvision {architecture}",
            version=version,
            source=ModelSource.TORCHVISION,
            framework_version=torch.__version__,
            torchvision_version=torchvision.__version__,
            architecture=architecture,
            weights=weights,
            seed=seed,
            num_classes=model_num_classes,
            input_channels=3,
            parameter_count=_parameter_count(model),
            state_dict_sha256=state_sha256,
            preprocessing=preprocessing,
            device=cast(Any, self.device.type),
            artifact=artifact,
        )
        return ModelBundle(model=model, record=record, preprocess=preprocess)
