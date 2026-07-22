# Experiment Result Schema

The canonical exchange format is the generated JSON Schema at
`schemas/experiment-result.schema.json`. Its source of truth is the strict Pydantic model in
`aishield.schemas.experiment`; unknown fields are rejected so typos cannot silently weaken the
reproducibility record.

## Aggregate structure

| Domain | Representation | Key invariant |
| --- | --- | --- |
| Dataset | `dataset` | Local or approved-public source, explicit approval, manifest SHA-256 |
| ModelArtifact | `model.artifact` | Content URI, format, size, SHA-256 |
| ModelVersion | `model` | PyTorch architecture/version bound to one artifact |
| Experiment | `experiment` | Seed, lifecycle timestamps, dataset/model references |
| AttackDefinition | `attack_runs[].definition` | Implementation, norm, targeting mode, all parameters |
| AttackRun | `attack_runs[]` | Seed and paired clean/robust/attack metrics on success |
| DefenseDefinition | `defense_runs[].definition` | Implementation and complete parameters |
| DefenseRun | `defense_runs[]` | Before/after metrics and adaptive-attack flag |
| SampleResult | `sample_results[]` | Clean/adversarial predictions and comparison artifact links |
| Metric | `metrics[]` | Raw scalar value, unit, optional attack/defense/class context |
| Artifact | `artifacts[]` | Kind, URI, media type, byte size, SHA-256 |
| EnvironmentSnapshot | `environment` | Runtime/package/device/container/Git versions |
| RobustnessScore | `robustness_score` | Formula version, weighted components, raw metric references |

`baseline` records clean accuracy, loss, class precision/recall, latency, and an optional confusion
matrix artifact. A completed attack's `accuracy` object is indivisible: clean accuracy, robust
accuracy, attack success rate, and sample count appear together.

All child records carry the same experiment UUID. Sample artifact references must resolve within the
export. These invariants are enforced beyond the structural JSON Schema by Pydantic model
validation.

## Versioning

`schema_version` starts at `1.0`. Backward-compatible optional additions increment the minor
version; removals, semantic changes, or stricter interpretations require a major version and a
migration document. The committed schema is checked against generated output in CI.

This is an interchange and archival design, not the final PostgreSQL table layout. Relational
migrations will preserve these identities when persistence is implemented.
