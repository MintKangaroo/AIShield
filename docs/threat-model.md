# Threat Model

## Scope and assets

AIShield is a defensive research platform for operator-provided models and local or explicitly
approved public image datasets. Sensitive assets include model weights, dataset samples and labels,
experiment metadata, generated adversarial examples, artifacts, database credentials, and future
queue payloads.

## Trust boundaries

- API and dashboard input is untrusted.
- Dataset archives, model files, checkpoints, and serialized tensors are untrusted even when local.
- PostgreSQL, Redis, artifact storage, and future evaluation workers are separate trust boundaries.
- A downloaded public dataset is permitted only after its source is approved and its version or
  manifest checksum is recorded.

## Implemented controls

- Result and request contracts reject unknown fields and broken cross-experiment references.
- Public datasets use fixed built-in sources and require an operator-level download opt-in.
- The default synthetic adapter is generated locally and is explicitly marked non-benchmark data.
- Checkpoints resolve below a configured root, reject symlinks/path traversal, and load with
  `weights_only=True` plus strict key/shape matching.
- Dataset manifest, model state/artifact, prediction sequence, and generated artifact use SHA-256.
- FGSM/PGD validate finite raw inputs in `[0,1]`, clamp outputs, project perturbations, and
  numerically check the observed L-infinity bound.
- Attack responses keep clean and robust accuracy together and expose raw denominator/counts.
- Zero input gradients produce a masking warning rather than a robustness claim.
- Artifact downloads require a record owned by the requested run and a regular file below the
  configured artifact root.
- API container runs as a non-root user; secrets, raw data, weights, and generated artifacts are
  ignored by Git. GitHub Actions uses read-only repository permissions.

## Remaining controls

- Move evaluation to resource-constrained workers with time, memory, concurrency, and sample caps.
- Add transfer/adaptive attacks, multiple restarts, and strength monotonicity checks before defense
  claims.
- Add artifact retention, recovery, and authenticated multi-user authorization before deployment
  outside a trusted local research environment.

## Out of scope

Unauthorized datasets, personal data, production secrets, malware, credential collection, evasion
of third-party security controls, and attacks against systems without explicit authorization are
prohibited. LLM attacks, model extraction, and privacy inference are separate future programs and
are not implied by the image-classification engine.
