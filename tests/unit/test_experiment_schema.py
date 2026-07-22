import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError

from aishield.schemas import ExperimentResult
from aishield.schemas.experiment import AccuracyMetrics, AttackRun, RunStatus
from aishield.schemas.export import main, rendered_schema

EXPERIMENT_ID = UUID("00000000-0000-4000-8000-000000000001")
DATASET_ID = UUID("00000000-0000-4000-8000-000000000002")
MODEL_ID = UUID("00000000-0000-4000-8000-000000000003")
MODEL_ARTIFACT_ID = UUID("00000000-0000-4000-8000-000000000004")
RESULT_ARTIFACT_ID = UUID("00000000-0000-4000-8000-000000000005")
ATTACK_ID = UUID("00000000-0000-4000-8000-000000000006")
ATTACK_RUN_ID = UUID("00000000-0000-4000-8000-000000000007")


def valid_result() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "experiment": {
            "id": str(EXPERIMENT_ID),
            "name": "reproducibility smoke test",
            "status": "succeeded",
            "seed": 1729,
            "dataset_id": str(DATASET_ID),
            "model_version_id": str(MODEL_ID),
            "created_at": "2026-07-22T10:00:00Z",
            "started_at": "2026-07-22T10:00:01Z",
            "finished_at": "2026-07-22T10:00:02Z",
        },
        "dataset": {
            "id": str(DATASET_ID),
            "name": "fixture-dataset",
            "version": "1",
            "split": "test",
            "source": "local",
            "approved_for_research": True,
            "manifest_sha256": "a" * 64,
            "sample_count": 1,
        },
        "model": {
            "id": str(MODEL_ID),
            "name": "fixture-model",
            "version": "1",
            "framework": "pytorch",
            "architecture": "TinyCNN",
            "artifact": {
                "id": str(MODEL_ARTIFACT_ID),
                "uri": "file:///models/tiny-cnn.pt",
                "sha256": "b" * 64,
                "size_bytes": 128,
                "format": "pytorch_state_dict",
            },
        },
        "environment": {
            "python_version": "3.12.4",
            "platform": "Linux-x86_64",
            "package_versions": {"torch": "2.7.1", "torchvision": "0.22.1"},
            "git_commit": "c" * 40,
            "container_image_digest": "sha256:" + "d" * 64,
            "device": "cpu",
        },
        "baseline": {
            "clean_accuracy": 1.0,
            "mean_loss": 0.01,
            "evaluated_samples": 1,
            "mean_inference_latency_ms": 0.5,
            "precision_by_class": {0: 1.0},
            "recall_by_class": {0: 1.0},
        },
        "attack_runs": [
            {
                "id": str(ATTACK_RUN_ID),
                "experiment_id": str(EXPERIMENT_ID),
                "definition": {
                    "id": str(ATTACK_ID),
                    "name": "FGSM",
                    "implementation": "aishield.attacks.fgsm:FGSM",
                    "norm": "linf",
                    "targeted": False,
                    "parameters": {"epsilon": 0.03},
                },
                "status": "succeeded",
                "seed": 1729,
                "accuracy": {
                    "clean_accuracy": 1.0,
                    "robust_accuracy": 0.0,
                    "attack_success_rate": 1.0,
                    "evaluated_samples": 1,
                },
            }
        ],
        "sample_results": [
            {
                "id": "00000000-0000-4000-8000-000000000008",
                "experiment_id": str(EXPERIMENT_ID),
                "attack_run_id": str(ATTACK_RUN_ID),
                "sample_index": 0,
                "true_label": 0,
                "clean_prediction": 0,
                "adversarial_prediction": 1,
                "attack_succeeded": True,
                "artifact_ids": [str(RESULT_ARTIFACT_ID)],
            }
        ],
        "artifacts": [
            {
                "id": str(RESULT_ARTIFACT_ID),
                "experiment_id": str(EXPERIMENT_ID),
                "kind": "adversarial_image",
                "uri": "file:///artifacts/adversarial.png",
                "sha256": "e" * 64,
                "media_type": "image/png",
                "size_bytes": 256,
            }
        ],
    }


def test_result_contract_records_reproducibility_and_paired_accuracy() -> None:
    result = ExperimentResult.model_validate(valid_result())

    assert result.experiment.seed == 1729
    assert result.model.artifact.sha256 == "b" * 64
    assert result.attack_runs[0].accuracy == AccuracyMetrics(
        clean_accuracy=1.0,
        robust_accuracy=0.0,
        attack_success_rate=1.0,
        evaluated_samples=1,
    )
    assert result.experiment.created_at == datetime(2026, 7, 22, 10, tzinfo=UTC)


@pytest.mark.parametrize("reference", ["dataset", "model", "record", "artifact"])
def test_result_contract_rejects_broken_references(reference: str) -> None:
    payload = deepcopy(valid_result())
    replacement = "00000000-0000-4000-8000-000000000099"
    if reference == "dataset":
        payload["dataset"]["id"] = replacement
    elif reference == "model":
        payload["model"]["id"] = replacement
    elif reference == "record":
        payload["attack_runs"][0]["experiment_id"] = replacement
    else:
        payload["sample_results"][0]["artifact_ids"] = [replacement]

    with pytest.raises(ValidationError):
        ExperimentResult.model_validate(payload)


def test_succeeded_attack_requires_clean_and_robust_accuracy() -> None:
    attack_run = deepcopy(valid_result()["attack_runs"])[0]
    del attack_run["accuracy"]

    with pytest.raises(ValidationError, match="paired accuracy"):
        AttackRun.model_validate(attack_run)

    attack_run["status"] = RunStatus.PENDING
    assert AttackRun.model_validate(attack_run).accuracy is None


def test_succeeded_result_requires_clean_baseline() -> None:
    payload = valid_result()
    del payload["baseline"]

    with pytest.raises(ValidationError, match="clean baseline"):
        ExperimentResult.model_validate(payload)


def test_schema_export_is_deterministic_and_checkable(tmp_path: Path) -> None:
    destination = tmp_path / "experiment-result.schema.json"
    main([str(destination)])

    parsed = json.loads(destination.read_text(encoding="utf-8"))
    assert parsed["$id"].endswith("experiment-result-1.0.json")
    assert destination.read_text(encoding="utf-8") == rendered_schema()
    main(["--check", str(destination)])


def test_schema_check_rejects_drift(tmp_path: Path) -> None:
    stale = tmp_path / "stale.json"
    stale.write_text("{}\n", encoding="utf-8")

    with pytest.raises(SystemExit):
        main(["--check", str(stale)])
