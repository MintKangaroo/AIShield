"""Run a declarative experiment file and emit a portable result envelope.

This is the headless path a CI job or a paper's replication script uses: one
file describes the dataset, model, baseline and attacks, and the command writes
a schema-valid :class:`ExperimentResult` that the API can import unchanged.
"""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aishield.attacks.contracts import AttackAlgorithm, AttackConfig
from aishield.core.config import Settings
from aishield.core.logging import configure_logging
from aishield.defenses.contracts import DefenseConfig, DefenseKind
from aishield.evaluation.contracts import BaselineConfig
from aishield.registry.contracts import DatasetName, DatasetSplit
from aishield.registry.service import RegistryService
from aishield.schemas.experiment import ExperimentResult


class SpecModel(BaseModel):
    """Strict base so a misspelled key fails the run instead of being ignored."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class DatasetSpec(SpecModel):
    name: DatasetName
    split: DatasetSplit = DatasetSplit.TEST
    download: bool = False


class ModelSpec(SpecModel):
    architecture: Literal["small_cnn"] = "small_cnn"
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    checkpoint: str | None = None


class BaselineSpec(SpecModel):
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=10_000_000)
    warmup_batches: int = Field(default=1, ge=0, le=100)


class AttackSpec(SpecModel):
    algorithm: AttackAlgorithm
    norm: Literal["linf", "l2"] | None = None
    epsilon: float = Field(default=8 / 255, gt=0.0, le=1.0)
    step_size: float | None = Field(default=None, gt=0.0, le=1.0)
    iterations: int | None = Field(default=None, ge=1, le=100)
    random_start: bool | None = None
    seed: int = Field(default=1729, ge=0, le=4_294_967_295)
    batch_size: int = Field(default=64, gt=0, le=4096)
    max_samples: int | None = Field(default=None, gt=0, le=100_000)

    def to_config(self) -> AttackConfig:
        """Resolve the documented per-algorithm defaults into a full config."""

        iterative = self.algorithm is not AttackAlgorithm.FGSM
        l2 = self.algorithm in (AttackAlgorithm.DEEPFOOL, AttackAlgorithm.CARLINI_WAGNER)
        iterations = 1 if not iterative else (self.iterations if self.iterations else 10)
        if self.step_size is not None:
            step_size = self.step_size
        elif iterative:
            step_size = min(self.epsilon / 4, self.epsilon)
        else:
            step_size = self.epsilon
        random_start = (
            self.random_start
            if self.random_start is not None
            else self.algorithm is AttackAlgorithm.PGD
        )
        return AttackConfig(
            algorithm=self.algorithm,
            norm=self.norm if self.norm is not None else ("l2" if l2 else "linf"),
            epsilon=self.epsilon,
            step_size=step_size,
            iterations=iterations,
            random_start=random_start,
            seed=self.seed,
            batch_size=self.batch_size,
            max_samples=self.max_samples,
        )


class DefenseSpec(SpecModel):
    kind: DefenseKind = DefenseKind.BIT_DEPTH
    bit_depth: int = Field(default=4, ge=1, le=8)
    attack: AttackSpec


class ExperimentSpec(SpecModel):
    """Declarative description of one reproducible experiment."""

    version: Literal[1] = 1
    name: str | None = Field(default=None, min_length=1, max_length=200)
    dataset: DatasetSpec
    model: ModelSpec = ModelSpec()
    baseline: BaselineSpec = BaselineSpec()
    attacks: list[AttackSpec] = Field(default_factory=list)
    defenses: list[DefenseSpec] = Field(default_factory=list)


def load_spec(path: Path) -> ExperimentSpec:
    """Read and validate an experiment file (JSON, or YAML when PyYAML is present)."""

    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml
        except ModuleNotFoundError as error:  # pragma: no cover - optional dependency
            raise SystemExit(
                "YAML experiment files need PyYAML; install it or use JSON instead"
            ) from error
        payload: Any = yaml.safe_load(text)
    else:
        payload = json.loads(text)
    return ExperimentSpec.model_validate(payload)


def run_spec(spec: ExperimentSpec, settings: Settings) -> ExperimentResult:
    """Execute the whole spec in order and return the portable envelope."""

    registry = RegistryService(settings)
    dataset = registry.load_dataset(
        spec.dataset.name, spec.dataset.split, download=spec.dataset.download
    )
    model = registry.load_small_cnn(
        dataset.id, seed=spec.model.seed, checkpoint=spec.model.checkpoint
    )
    baseline = registry.run_clean_baseline(
        model.id,
        dataset.id,
        config=BaselineConfig(
            seed=spec.baseline.seed,
            batch_size=spec.baseline.batch_size,
            max_samples=spec.baseline.max_samples,
            warmup_batches=spec.baseline.warmup_batches,
        ),
    )
    for attack in spec.attacks:
        registry.run_attack(model.id, dataset.id, config=attack.to_config())
    for defense in spec.defenses:
        registry.run_defense(
            model.id,
            dataset.id,
            defense=DefenseConfig(kind=defense.kind, bit_depth=defense.bit_depth),
            attack=defense.attack.to_config(),
        )
    return registry.export_experiment(baseline.id)


def main(argv: Sequence[str] | None = None) -> int:
    """Run one experiment file and write its envelope to a path or stdout."""

    parser = argparse.ArgumentParser(prog="aishield-run", description=__doc__)
    parser.add_argument("spec", type=Path, help="experiment file (.json, .yaml)")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="write the result envelope here instead of stdout",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="structured log level written to stdout (default: WARNING)",
    )
    arguments = parser.parse_args(argv)

    settings = Settings(log_level=arguments.log_level)
    configure_logging(settings.log_level)

    spec = load_spec(arguments.spec)
    result = run_spec(spec, settings)
    payload = json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"

    if arguments.output is None:
        sys.stdout.write(payload)
    else:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(payload, encoding="utf-8")
    return 0


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
