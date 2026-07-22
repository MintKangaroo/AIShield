# Architecture

## Release boundary

The first AIShield release evaluates adversarial robustness for PyTorch image classifiers. Its
metric vocabulary and future execution engine are specific to image classification. LLM security,
privacy attacks, and model extraction must use separate engines and metric contracts when those
programs are designed.

Stage 1 establishes the control plane and result contract without executing ML workloads.

```text
Browser ──> Dashboard (nginx) ──> FastAPI
                                      │
                         ┌────────────┴────────────┐
                         │                         │
                   PostgreSQL                  Redis
                 metadata (future)        queue boundary (future)

Evaluation worker (future) ──> content-addressed artifact directory
```

PostgreSQL and Redis are provisioned now so service boundaries are stable, but the API deliberately
does not report dependency readiness until persistence and queue adapters exist. The `/health/live`
endpoint reports only process liveness.

## Python boundaries

- `aishield.api` owns HTTP transport and versioned routes.
- `aishield.core` owns validated runtime configuration.
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

CPU is the default and is sufficient for the development control plane and later small MNIST/CIFAR
examples. The Compose `gpu` profile is opt-in and currently verifies NVIDIA container access only.
GPU execution workers will be added with explicit PyTorch/CUDA version pins when the evaluation
engine is introduced.
