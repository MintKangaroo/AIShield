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

## Initial controls

- No model deserialization, dataset download, or attack execution exists in stage 1.
- Result contracts reject unknown fields and broken cross-experiment references.
- Dataset records require `local` or `approved_public` provenance and explicit approval.
- Model and artifact records require SHA-256 content hashes.
- The API container runs as a non-root user; secrets and generated artifacts are ignored by Git.
- GitHub Actions receives read-only repository permissions.

## Planned ML-specific controls

- Prefer weights-only state dictionaries or safe tensor formats; never accept arbitrary pickle data
  as a trusted model artifact.
- Clamp adversarial inputs to the valid normalized input range and numerically verify norm bounds.
- Run untrusted evaluation inputs in resource-constrained workers with time, memory, and sample caps.
- Treat preprocessing defenses and unexpectedly flat gradients as possible gradient masking.
- Compare stronger iterative attacks, transfer attacks, random restarts, and adaptive attacks before
  claiming robustness.
- Store clean accuracy beside robust accuracy so a defense cannot hide utility collapse.

## Out of scope

Unauthorized datasets, personal data, production secrets, malware, credential collection, evasion
of third-party security controls, and attacks against systems without explicit authorization are
prohibited. LLM attacks, model extraction, and privacy inference are separate future programs and
are not implied by the image-classification engine.
