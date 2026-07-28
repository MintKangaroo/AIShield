# API

All application endpoints live under `/api/v1`. FastAPI serves OpenAPI at `/api/openapi.json`,
Swagger UI at `/api/docs`, and ReDoc at `/api/redoc`.

## Endpoints in stage 1

| Method | Path | Meaning |
| --- | --- | --- |
| `GET` | `/api/v1` | Service version and release scope |
| `GET` | `/api/v1/health/live` | Process liveness and configured compute device |
| `POST` | `/api/v1/registry/datasets` | Load an approved MNIST/CIFAR-10 split |
| `GET` | `/api/v1/registry/datasets` | List datasets loaded in this API process |
| `POST` | `/api/v1/registry/models/small-cnn` | Create or restore a dataset-compatible CNN |
| `POST` | `/api/v1/registry/models/torchvision` | Load an allowlisted torchvision classifier |
| `GET` | `/api/v1/registry/models` | List models loaded in this API process |
| `POST` | `/api/v1/registry/evaluations` | Run a bounded basic clean evaluation |

Liveness does not imply PostgreSQL or Redis readiness. Dependency checks will be introduced with
the adapters that use them, preventing a misleading healthy response.

Registry entries are currently process-local and disappear when the API restarts. Model artifacts
and dataset files persist in configured storage. PostgreSQL persistence belongs to a later milestone.

The basic evaluation endpoint validates model input channels and class count, fixes the requested
seed, disables shuffle, and supports `max_samples`. It intentionally does not claim adversarial
robustness: `robust_accuracy` is always `null` with status `not_evaluated` until an attack runs.

Attack, defense, detailed baseline artifact, and export endpoints belong to later milestones. New
endpoints must use typed request/response models, reject unknown fields at trust boundaries, and
remain backward compatible within an API version.
