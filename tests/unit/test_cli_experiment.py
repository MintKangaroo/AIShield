"""Contract for the headless experiment runner."""

import json
from pathlib import Path

import pytest

from aishield.attacks.contracts import AttackAlgorithm
from aishield.cli.experiment import AttackSpec, ExperimentSpec, load_spec, main, run_spec
from aishield.core.config import Settings
from aishield.schemas.experiment import ExperimentResult


def _spec_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": 1,
        "dataset": {"name": "synthetic", "split": "test"},
        "model": {"seed": 1729},
        "baseline": {"seed": 1729, "batch_size": 2, "max_samples": 4, "warmup_batches": 0},
        "attacks": [
            {"algorithm": "fgsm", "epsilon": 0.1, "batch_size": 2, "max_samples": 4},
        ],
    }
    payload.update(overrides)
    return payload


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        artifact_root=tmp_path / "artifacts",
        model_root=tmp_path / "models",
        dataset_root=tmp_path / "datasets",
        allow_public_downloads=False,
    )


def test_fgsm_defaults_satisfy_the_single_step_contract() -> None:
    config = AttackSpec(algorithm=AttackAlgorithm.FGSM, epsilon=0.1).to_config()

    assert config.iterations == 1
    assert config.random_start is False
    assert config.step_size == pytest.approx(config.epsilon)


def test_pgd_defaults_use_a_quarter_step_and_random_start() -> None:
    config = AttackSpec(algorithm=AttackAlgorithm.PGD, epsilon=0.1).to_config()

    assert config.random_start is True
    assert config.iterations == 10
    assert config.step_size == pytest.approx(0.025)


def test_bim_defaults_refuse_a_random_start() -> None:
    assert AttackSpec(algorithm=AttackAlgorithm.BIM, epsilon=0.1).to_config().random_start is False


def test_l2_attacks_default_to_the_l2_norm() -> None:
    assert AttackSpec(algorithm=AttackAlgorithm.DEEPFOOL, epsilon=0.1).to_config().norm == "l2"
    assert (
        AttackSpec(algorithm=AttackAlgorithm.CARLINI_WAGNER, epsilon=0.1).to_config().norm == "l2"
    )


def test_spec_rejects_an_unknown_key() -> None:
    with pytest.raises(ValueError):
        ExperimentSpec.model_validate(_spec_payload(baselines={}))


def test_load_spec_reads_json(tmp_path: Path) -> None:
    path = tmp_path / "experiment.json"
    path.write_text(json.dumps(_spec_payload()), encoding="utf-8")

    spec = load_spec(path)

    assert spec.dataset.name.value == "synthetic"
    assert len(spec.attacks) == 1


def test_run_spec_produces_an_importable_envelope(tmp_path: Path) -> None:
    spec = ExperimentSpec.model_validate(_spec_payload())

    result = run_spec(spec, _settings(tmp_path))

    assert result.baseline is not None
    assert len(result.attack_runs) == 1
    assert result.robustness_score is not None
    ExperimentResult.model_validate(result.model_dump(mode="json"))


def test_run_spec_executes_a_defense(tmp_path: Path) -> None:
    spec = ExperimentSpec.model_validate(
        _spec_payload(
            attacks=[],
            defenses=[
                {
                    "kind": "bit_depth",
                    "bit_depth": 4,
                    "attack": {
                        "algorithm": "fgsm",
                        "epsilon": 0.1,
                        "batch_size": 2,
                        "max_samples": 4,
                    },
                }
            ],
        )
    )

    result = run_spec(spec, _settings(tmp_path))

    assert len(result.defense_runs) == 1


def test_main_writes_the_envelope_to_a_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AISHIELD_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AISHIELD_MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("AISHIELD_DATASET_ROOT", str(tmp_path / "datasets"))
    spec_path = tmp_path / "experiment.json"
    spec_path.write_text(json.dumps(_spec_payload()), encoding="utf-8")
    output = tmp_path / "out" / "result.json"

    assert main([str(spec_path), "--output", str(output)]) == 0

    envelope = ExperimentResult.model_validate(json.loads(output.read_text(encoding="utf-8")))
    assert envelope.schema_version == "1.0"
    assert len(envelope.attack_runs) == 1


def test_main_writes_to_stdout_by_default(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AISHIELD_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    monkeypatch.setenv("AISHIELD_MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("AISHIELD_DATASET_ROOT", str(tmp_path / "datasets"))
    spec_path = tmp_path / "experiment.json"
    spec_path.write_text(json.dumps(_spec_payload(attacks=[])), encoding="utf-8")

    assert main([str(spec_path)]) == 0

    envelope = ExperimentResult.model_validate(json.loads(capsys.readouterr().out))
    assert envelope.attack_runs == []
