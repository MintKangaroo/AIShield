# API

All application endpoints live under `/api/v1`. FastAPI serves OpenAPI at `/api/openapi.json`,
Swagger UI at `/api/docs`, and ReDoc at `/api/redoc`.

## Endpoints in stage 1

| Method | Path | Meaning |
| --- | --- | --- |
| `GET` | `/api/v1` | Service version and release scope |
| `GET` | `/api/v1/health/live` | Process liveness and configured compute device |

Liveness does not imply PostgreSQL or Redis readiness. Dependency checks will be introduced with
the adapters that use them, preventing a misleading healthy response.

Registry, evaluation, attack, defense, artifact, and export endpoints belong to later milestones.
New endpoints must use typed request/response models, reject unknown fields at trust boundaries,
and remain backward compatible within an API version.
