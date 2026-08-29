"""Assemble the portable experiment envelope from retained registry evidence.

The envelope in :mod:`aishield.schemas.experiment` is the project's exchange
contract. This module is the only place that maps the internal run records onto
it, so an exported file and an imported file always agree on one definition.
"""

from collections.abc import Sequence
from uuid import UUID, uuid5

from aishield.attacks.contracts import AttackRunRecord
from aishield.defenses.contracts import DefenseRunRecord
from aishield.evaluation.contracts import BaselineRunRecord
from aishield.evaluation.score import RobustnessScore as RegistryRobustnessScore
from aishield.registry.contracts import DatasetRecord, ModelVersionRecord
from aishield.registry.errors import RegistryError
from aishield.schemas.experiment import (
    AccuracyMetrics,
    Artifact,
    ArtifactKind,
    AttackDefinition,
    AttackRun,
    CleanBaseline,
    Dataset,
    DefenseDefinition,
    DefenseRun,
    EnvironmentSnapshot,
    Experiment,
    ExperimentResult,
    Metric,
    ModelArtifact,
    ModelVersion,
    RobustnessScore,
    RunStatus,
    ScoreComponent,
)

#: Namespace for identifiers the envelope requires but the registry does not store.
_EXPORT_NAMESPACE = UUID("6f9619ff-8b86-d011-b42d-00c04fc964ff")

_ARTIFACT_KINDS = {
    "baseline_report": ArtifactKind.REPORT,
    "confusion_matrix": ArtifactKind.CONFUSION_MATRIX,
}


def _derived_id(*parts: str) -> UUID:
    """Derive a stable UUID so re-exporting one run never changes its identifiers."""

    return uuid5(_EXPORT_NAMESPACE, "|".join(parts))


def _dataset(record: DatasetRecord) -> Dataset:
    return Dataset(
        id=record.id,
        name=record.name.value,
        version=record.version,
        split=record.split.value,
        source="local" if record.source == "generated" else "approved_public",
        approved_for_research=True,
        manifest_sha256=record.manifest_sha256,
        sample_count=record.sample_count,
    )


def _model(record: ModelVersionRecord) -> ModelVersion:
    return ModelVersion(
        id=record.id,
        name=record.name,
        version=record.version,
        framework=record.framework,
        architecture=record.architecture,
        artifact=ModelArtifact(
            id=_derived_id("model-artifact", str(record.id)),
            uri=record.artifact.uri,
            sha256=record.artifact.sha256,
            size_bytes=record.artifact.size_bytes,
            format=record.artifact.format,
        ),
    )


def _environment(baseline: BaselineRunRecord) -> EnvironmentSnapshot:
    source = baseline.environment
    return EnvironmentSnapshot(
        python_version=source.python_version,
        platform=source.platform,
        package_versions=source.package_versions,
        git_commit=source.git_commit,
        container_image_digest=source.container_image_digest,
        device=source.device,
        cuda_version=source.cuda_version,
        cudnn_version=source.cudnn_version,
    )


def _baseline(baseline: BaselineRunRecord) -> tuple[CleanBaseline, list[Artifact]]:
    artifacts = [
        Artifact(
            id=artifact.id,
            experiment_id=baseline.id,
            kind=_ARTIFACT_KINDS.get(artifact.kind.value, ArtifactKind.OTHER),
            uri=artifact.uri,
            sha256=artifact.sha256,
            media_type=artifact.media_type,
            size_bytes=artifact.size_bytes,
        )
        for artifact in baseline.artifacts
    ]
    matrix = next(
        (
            artifact.id
            for artifact in baseline.artifacts
            if artifact.kind.value == "confusion_matrix"
        ),
        None,
    )
    clean = CleanBaseline(
        clean_accuracy=baseline.metrics.clean_accuracy,
        mean_loss=baseline.metrics.mean_loss,
        evaluated_samples=baseline.metrics.evaluated_samples,
        mean_inference_latency_ms=baseline.metrics.latency.mean_ms_per_sample,
        precision_by_class={
            metric.class_index: metric.precision for metric in baseline.metrics.per_class
        },
        recall_by_class={
            metric.class_index: metric.recall for metric in baseline.metrics.per_class
        },
        confusion_matrix_artifact_id=matrix,
    )
    return clean, artifacts


def _attack_run(experiment_id: UUID, record: AttackRunRecord) -> AttackRun:
    config = record.config
    return AttackRun(
        id=record.id,
        experiment_id=experiment_id,
        definition=AttackDefinition(
            id=_derived_id("attack-definition", str(record.id)),
            name=config.algorithm.value,
            implementation=f"aishield.attacks.runner:{config.algorithm.value}",
            norm=config.norm,
            targeted=config.targeted,
            parameters={
                "epsilon": config.epsilon,
                "step_size": config.step_size,
                "iterations": config.iterations,
                "random_start": config.random_start,
                "batch_size": config.batch_size,
                "max_samples": config.max_samples,
            },
        ),
        status=RunStatus.SUCCEEDED,
        seed=config.seed,
        accuracy=AccuracyMetrics(
            clean_accuracy=record.metrics.clean_accuracy,
            robust_accuracy=record.metrics.robust_accuracy,
            attack_success_rate=record.metrics.attack_success_rate,
            evaluated_samples=record.metrics.evaluated_samples,
        ),
    )


def _defense_run(experiment_id: UUID, record: DefenseRunRecord) -> DefenseRun:
    metrics = record.metrics
    return DefenseRun(
        id=record.id,
        experiment_id=experiment_id,
        definition=DefenseDefinition(
            id=_derived_id("defense-definition", str(record.id)),
            name=record.defense.kind.value,
            implementation=f"aishield.defenses.runner:{record.defense.kind.value}",
            parameters={
                "bit_depth": record.defense.bit_depth,
                "attack_algorithm": record.attack_algorithm.value,
            },
        ),
        status=RunStatus.SUCCEEDED,
        before=AccuracyMetrics(
            clean_accuracy=metrics.clean_accuracy_before,
            robust_accuracy=metrics.robust_accuracy_before,
            attack_success_rate=metrics.attack_success_rate_before,
            evaluated_samples=metrics.evaluated_samples,
        ),
        after=AccuracyMetrics(
            clean_accuracy=metrics.clean_accuracy_after,
            robust_accuracy=metrics.robust_accuracy_after,
            attack_success_rate=metrics.attack_success_rate_after,
            evaluated_samples=metrics.evaluated_samples,
        ),
        adaptive_attack_evaluated=True,
    )


def _raw_metrics(
    experiment_id: UUID,
    baseline: BaselineRunRecord,
    attacks: Sequence[AttackRunRecord],
) -> list[Metric]:
    """Keep every aggregate traceable to the raw scalars it was computed from."""

    metrics = [
        Metric(
            id=_derived_id("metric", str(baseline.id), "clean_accuracy"),
            experiment_id=experiment_id,
            name="clean_accuracy",
            value=baseline.metrics.clean_accuracy,
            unit="ratio",
        ),
        Metric(
            id=_derived_id("metric", str(baseline.id), "mean_loss"),
            experiment_id=experiment_id,
            name="mean_loss",
            value=baseline.metrics.mean_loss,
            unit="nats",
        ),
    ]
    for record in attacks:
        for name, value, unit in (
            ("robust_accuracy", record.metrics.robust_accuracy, "ratio"),
            ("attack_success_rate", record.metrics.attack_success_rate, "ratio"),
            ("maximum_observed_linf", record.metrics.maximum_observed_linf, "linf"),
        ):
            metrics.append(
                Metric(
                    id=_derived_id("metric", str(record.id), name),
                    experiment_id=experiment_id,
                    name=name,
                    value=value,
                    unit=unit,
                    attack_run_id=record.id,
                )
            )
    return metrics


def _score(
    score: RegistryRobustnessScore,
    attacks: Sequence[AttackRunRecord],
    metrics: Sequence[Metric],
) -> RobustnessScore:
    by_run = {record.id: record for record in attacks}
    components = [
        ScoreComponent(
            name=by_run[run_id].config.algorithm.value,
            raw_value=by_run[run_id].metrics.robust_accuracy,
            normalized_value=by_run[run_id].metrics.robust_accuracy,
            weight=1.0 / len(score.attack_run_ids),
        )
        for run_id in score.attack_run_ids
        if run_id in by_run
    ]
    if not components:
        raise RegistryError("robustness score references attack runs missing from the export")
    raw_metric_ids = [
        metric.id
        for metric in metrics
        if metric.name == "robust_accuracy" and metric.attack_run_id in by_run
    ]
    return RobustnessScore(
        version=score.formula_version,
        value=score.score,
        formula="mean of robust accuracy over the selected attack runs",
        components=components,
        raw_metric_ids=raw_metric_ids,
    )


def build_experiment_result(
    baseline: BaselineRunRecord,
    dataset: DatasetRecord,
    model: ModelVersionRecord,
    *,
    attacks: Sequence[AttackRunRecord] = (),
    defenses: Sequence[DefenseRunRecord] = (),
    score: RegistryRobustnessScore | None = None,
) -> ExperimentResult:
    """Build one self-contained, schema-valid envelope for a baseline and its runs.

    Only runs that share the baseline's model and dataset are eligible; mixing
    targets would produce an envelope whose metrics cannot be compared.
    """

    if dataset.id != baseline.dataset_id:
        raise RegistryError("dataset does not belong to the baseline run")
    if model.id != baseline.model_version_id:
        raise RegistryError("model does not belong to the baseline run")
    for record in attacks:
        if record.model_version_id != model.id or record.dataset_id != dataset.id:
            raise RegistryError(f"attack run {record.id} targets a different model or dataset")
    for defense in defenses:
        if defense.model_version_id != model.id or defense.dataset_id != dataset.id:
            raise RegistryError(f"defense run {defense.id} targets a different model or dataset")

    clean, artifacts = _baseline(baseline)
    metrics = _raw_metrics(baseline.id, baseline, attacks)
    return ExperimentResult(
        experiment=Experiment(
            id=baseline.id,
            name=f"{model.architecture} / {dataset.name.value} {dataset.split.value}",
            status=RunStatus.SUCCEEDED,
            seed=baseline.config.seed,
            dataset_id=dataset.id,
            model_version_id=model.id,
            created_at=baseline.created_at,
            finished_at=baseline.created_at,
        ),
        dataset=_dataset(dataset),
        model=_model(model),
        environment=_environment(baseline),
        baseline=clean,
        attack_runs=[_attack_run(baseline.id, record) for record in attacks],
        defense_runs=[_defense_run(baseline.id, record) for record in defenses],
        metrics=metrics,
        artifacts=artifacts,
        robustness_score=None if score is None else _score(score, attacks, metrics),
    )
