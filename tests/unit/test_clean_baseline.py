import json
from collections.abc import Callable
from pathlib import Path
from uuid import UUID

import pytest
import torch
from pydantic import ValidationError
from torch import Tensor, nn
from torch.utils.data import TensorDataset

from aishield.evaluation.contracts import (
    BaselineArtifactKind,
    BaselineConfig,
    CleanBaselineMetrics,
)
from aishield.evaluation.environment import capture_environment, discover_git_commit
from aishield.evaluation.runner import run_clean_baseline, verify_baseline_rerun
from aishield.registry.contracts import (
    DatasetName,
    DatasetRecord,
    DatasetSplit,
    ModelArtifactRecord,
    ModelSource,
    ModelVersionRecord,
)
from aishield.registry.datasets import DatasetBundle
from aishield.registry.errors import RegistryError
from aishield.registry.models import ModelBundle, identity_preprocess
from aishield.registry.reproducibility import sha256_file


class LookupClassifier(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.anchor = nn.Parameter(torch.zeros(1))
        self.register_buffer("prediction_map", torch.tensor([0, 0, 1, 2]))

    def forward(self, inputs: Tensor) -> Tensor:
        indices = inputs[:, 0, 0, 0].to(dtype=torch.long)
        predictions = self.get_buffer("prediction_map")[indices]
        logits = torch.full((inputs.shape[0], 3), -2.0, device=inputs.device)
        return logits.scatter(1, predictions.unsqueeze(1), 2.0) + self.anchor * 0


def baseline_bundles(
    tmp_path: Path,
    *,
    targets: Tensor | None = None,
) -> tuple[ModelBundle, DatasetBundle]:
    model_record = ModelVersionRecord(
        id=UUID("00000000-0000-4000-8000-000000000201"),
        name="lookup classifier",
        version="fixture-v1",
        source=ModelSource.SMALL_CNN,
        framework_version=torch.__version__,
        architecture="LookupClassifier",
        seed=1729,
        num_classes=3,
        input_channels=1,
        parameter_count=1,
        state_dict_sha256="a" * 64,
        preprocessing="identity",
        device="cpu",
        artifact=ModelArtifactRecord(
            uri=(tmp_path / "model.pt").resolve().as_uri(),
            sha256="b" * 64,
            size_bytes=1,
        ),
    )
    inputs = torch.zeros(4, 1, 2, 2)
    inputs[:, 0, 0, 0] = torch.arange(4)
    actual_targets = targets if targets is not None else torch.tensor([0, 1, 1, 2])
    dataset_record = DatasetRecord(
        id=UUID("00000000-0000-4000-8000-000000000202"),
        name=DatasetName.MNIST,
        version="fixture-v1",
        split=DatasetSplit.TEST,
        source_uri="https://example.invalid/approved-fixture",
        manifest_sha256="c" * 64,
        sample_count=4,
        num_classes=3,
        input_shape=(1, 2, 2),
        transform="identity",
        torchvision_version="fixture",
    )
    return (
        ModelBundle(
            model=LookupClassifier().eval(),
            record=model_record,
            preprocess=identity_preprocess,
        ),
        DatasetBundle(
            dataset=TensorDataset(inputs, actual_targets),
            record=dataset_record,
        ),
    )


def ticking_clock(step_ns: int = 2_000_000) -> Callable[[], int]:
    value = 0

    def tick() -> int:
        nonlocal value
        value += step_ns
        return value

    return tick


def test_clean_baseline_computes_metrics_and_artifacts(tmp_path: Path) -> None:
    model, dataset = baseline_bundles(tmp_path)

    result = run_clean_baseline(
        model,
        dataset,
        artifact_root=tmp_path / "artifacts",
        config=BaselineConfig(seed=1729, batch_size=2, max_samples=4, warmup_batches=1),
        clock=ticking_clock(),
    )

    assert result.metrics.clean_accuracy == 0.75
    assert result.metrics.robust_accuracy is None
    assert result.metrics.robust_accuracy_status == "not_evaluated"
    assert result.metrics.evaluated_samples == 4
    assert result.metrics.confusion_matrix == ((1, 0, 0), (1, 1, 0), (0, 0, 1))
    assert result.metrics.per_class[0].precision == 0.5
    assert result.metrics.per_class[1].recall == 0.5
    assert result.metrics.per_class[2].support == 1
    assert result.metrics.latency.warmup_batches == 1
    assert result.metrics.latency.measured_batches == 2
    assert result.metrics.latency.total_forward_ms == 4.0
    assert result.metrics.latency.mean_ms_per_sample == 1.0
    assert len(result.metrics.prediction_sha256) == 64
    assert result.environment.package_versions["torch"] == torch.__version__
    assert {artifact.kind for artifact in result.artifacts} == {
        BaselineArtifactKind.REPORT,
        BaselineArtifactKind.CONFUSION_MATRIX,
    }

    artifacts = {
        artifact.kind: Path(artifact.uri.removeprefix("file://")) for artifact in result.artifacts
    }
    report_path = artifacts[BaselineArtifactKind.REPORT]
    image_path = artifacts[BaselineArtifactKind.CONFUSION_MATRIX]
    assert sha256_file(report_path) == next(
        artifact.sha256
        for artifact in result.artifacts
        if artifact.kind is BaselineArtifactKind.REPORT
    )
    assert json.loads(report_path.read_text(encoding="utf-8"))["metrics"]["clean_accuracy"] == 0.75
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_same_seed_rerun_verifies_deterministic_evidence_not_latency(tmp_path: Path) -> None:
    model, dataset = baseline_bundles(tmp_path)
    config = BaselineConfig(seed=1729, batch_size=2, warmup_batches=0)
    first = run_clean_baseline(
        model,
        dataset,
        artifact_root=tmp_path / "first",
        config=config,
        clock=ticking_clock(),
    )

    clock = ticking_clock(step_ns=4_000_000)
    second = run_clean_baseline(
        model,
        dataset,
        artifact_root=tmp_path / "second",
        config=config,
        clock=clock,
    )
    verification = verify_baseline_rerun(first, second)

    assert verification.reproducible is True
    assert all(check.passed for check in verification.checks)
    assert verification.excluded_from_pass_fail == ("latency",)
    assert first.id != second.id
    assert first.metrics.latency.total_forward_ms != second.metrics.latency.total_forward_ms


def test_rerun_verification_exposes_prediction_mismatch(tmp_path: Path) -> None:
    model, dataset = baseline_bundles(tmp_path)
    baseline = run_clean_baseline(
        model,
        dataset,
        artifact_root=tmp_path / "artifacts",
        config=BaselineConfig(seed=1, batch_size=4, warmup_batches=0),
        clock=ticking_clock(),
    )
    changed_metrics = baseline.metrics.model_copy(update={"prediction_sha256": "d" * 64})
    changed = baseline.model_copy(update={"metrics": changed_metrics})

    verification = verify_baseline_rerun(baseline, changed)

    assert verification.reproducible is False
    failed = {check.name for check in verification.checks if not check.passed}
    assert failed == {"prediction_fingerprint"}


def test_baseline_rejects_targets_outside_registered_classes(tmp_path: Path) -> None:
    model, dataset = baseline_bundles(tmp_path, targets=torch.tensor([0, 1, 2, 3]))

    with pytest.raises(RegistryError, match="outside the registered class range"):
        run_clean_baseline(
            model,
            dataset,
            artifact_root=tmp_path / "artifacts",
            config=BaselineConfig(seed=1, batch_size=4, warmup_batches=0),
        )


def test_baseline_metrics_require_aligned_confusion_matrix(tmp_path: Path) -> None:
    model, dataset = baseline_bundles(tmp_path)
    result = run_clean_baseline(
        model,
        dataset,
        artifact_root=tmp_path / "artifacts",
        config=BaselineConfig(seed=1, batch_size=4, warmup_batches=0),
        clock=ticking_clock(),
    )
    payload = result.metrics.model_dump()
    payload["confusion_matrix"] = ((1, 0), (0, 1))

    with pytest.raises(ValidationError, match="confusion matrix"):
        CleanBaselineMetrics.model_validate(payload)


def test_environment_snapshot_records_versions_and_injected_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AISHIELD_GIT_COMMIT", "f" * 40)

    snapshot = capture_environment(torch.device("cpu"))

    assert discover_git_commit() == "f" * 40
    assert snapshot.git_commit == "f" * 40
    assert snapshot.device == "cpu"
    assert snapshot.deterministic_algorithms is True
    assert {"aishield", "matplotlib", "numpy", "torch", "torchvision"} <= set(
        snapshot.package_versions
    )
