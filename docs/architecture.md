# Architecture

## Release boundary

The first AIShield release evaluates adversarial robustness for PyTorch image classifiers. Its
metric vocabulary and future execution engine are specific to image classification. LLM security,
privacy attacks, and model extraction must use separate engines and metric contracts when those
programs are designed.

Stages 1 and 2 establish the control plane, result contract, and in-process registry. The registry
loads approved datasets and models and can run a bounded compatibility evaluation, but it is not the
stage 3 clean-baseline engine.

```text
Browser ──> Dashboard (nginx) ──> FastAPI
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                   PostgreSQL                  Redis
                 metadata (future)        queue boundary (future)

Evaluation worker (future) ──> content-addressed artifact directory
```

PostgreSQL and Redis are provisioned so service boundaries are stable, but registry metadata remains
in process until a persistence adapter is introduced. The API deliberately does not report
dependency readiness before those adapters use the dependencies. The `/health/live` endpoint reports
only process liveness.

## Python boundaries

- `aishield.api` owns HTTP transport and versioned routes.
- `aishield.core` owns validated runtime configuration.
- `aishield.registry` owns approved dataset/model adapters, deterministic seeding, hashing, safe
  state-dict loading, in-memory handles, and basic evaluation.
- `aishield.schemas` owns framework-independent exchange contracts.
- Future `domain`, `registry`, `evaluation`, `attacks`, `defenses`, `metrics`, and `infrastructure`
  packages will depend inward on domain interfaces rather than on FastAPI or worker frameworks.

Attack implementations will share a common typed interface and remain independent of API and queue
transport. Artifact rendering will use matplotlib outside the attack algorithm so numerical tests do
not depend on image output.

## Storage direction

The canonical stage 1 result is a self-contained JSON document validated by schema version `1.0`.
PostgreSQL will hold queryable identities and scalar metadata in a later milestone; large model,
image, matrix, and report artifacts remain content-addressed files whose checksums are stored in the
result. This avoids storing opaque binaries in relational rows and keeps exports portable.

## Compute profiles

CPU is the default and runs the registry with pinned PyTorch/torchvision CPU wheels. The Compose
`gpu` profile is opt-in and currently verifies NVIDIA container access only.
GPU execution workers will be added with explicit PyTorch/CUDA version pins when the evaluation
engine is introduced.
