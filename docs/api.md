# API

AIShield의 endpoint는 `/api/v1` 아래에 있습니다.

- OpenAPI JSON: `/api/openapi.json`
- Swagger UI: `/api/docs`
- ReDoc: `/api/redoc`

## Endpoints

| Method | Path | Meaning |
| --- | --- | --- |
| `GET` | `/api/v1` | Service version과 release scope |
| `GET` | `/api/v1/health/live` | Process liveness와 configured device |
| `POST` | `/api/v1/registry/datasets` | Built-in dataset split load |
| `GET` | `/api/v1/registry/datasets` | 현재 process의 dataset list |
| `POST` | `/api/v1/registry/models/small-cnn` | Seeded/checkpoint SmallCNN load |
| `POST` | `/api/v1/registry/models/torchvision` | Allowlist torchvision model load |
| `GET` | `/api/v1/registry/models` | 현재 process의 model list |
| `POST` | `/api/v1/registry/evaluations` | Legacy bounded clean compatibility check |
| `POST` | `/api/v1/registry/baselines` | Full clean baseline과 artifact 생성 |
| `GET` | `/api/v1/registry/baselines` | Baseline list |
| `GET` | `/api/v1/registry/baselines/{id}` | Baseline evidence |
| `POST` | `/api/v1/registry/baselines/{id}/verify` | Exact-config rerun과 evidence 비교 |
| `GET` | `/api/v1/registry/baselines/{id}/artifacts/{artifact_id}` | Registered artifact download |
| `POST` | `/api/v1/registry/attacks` | Bounded FGSM/BIM/PGD/DeepFool/CW/AutoAttack run |
| `GET` | `/api/v1/registry/attacks` | Attack run list |
| `GET` | `/api/v1/registry/attacks/{id}` | Attack run evidence |

Request body는 `extra="forbid"`로 처리하므로 알 수 없는 field와 parameter typo는 422로
거부됩니다. Domain policy/compatibility 오류는 400, 존재하지 않는 registry identity는
404입니다.

## Dataset policy

`synthetic` adapter는 다운로드 없이 deterministic `Signal-10`을 만듭니다. `mnist`와
`cifar10`은 고정된 torchvision source만 사용하며 `download=true`는
`AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true`일 때만 허용됩니다. API caller가 URL을 전달하는
endpoint는 없습니다.

## Baseline contract

Baseline은 clean accuracy/loss뿐 아니라 다음을 반환합니다.

- confusion matrix와 class별 precision/recall/support
- warm-up과 measured batch를 구분한 latency
- ordered target/prediction SHA-256
- model state/artifact와 dataset manifest SHA-256
- dependency/device/Git/container environment snapshot
- JSON report와 confusion matrix PNG artifact record

`POST /baselines/{id}/verify`는 원본 설정으로 새 run을 만들고 configuration, model,
dataset, environment, prediction fingerprint, matrix, accuracy, loss를 비교합니다. Latency는
기록하지만 pass/fail에서 제외합니다.

## Attack contract

지원 algorithm은 `fgsm`, `bim`, `pgd`, `deepfool`, `cw`, `autoattack`입니다. FGSM/BIM/PGD/
AutoAttack은 `linf`, DeepFool/CW는 `l2` norm을 사용합니다.

공통 request:

```json
{
  "model_version_id": "00000000-0000-0000-0000-000000000000",
  "dataset_id": "00000000-0000-0000-0000-000000000000",
  "algorithm": "pgd",
  "epsilon": 0.031372549,
  "step_size": 0.007843137,
  "iterations": 10,
  "random_start": true,
  "seed": 1729,
  "batch_size": 64,
  "max_samples": 256
}
```

FGSM default는 `step_size=epsilon`, `iterations=1`, `random_start=false`입니다. BIM default는
`step_size=epsilon/4`, `iterations=10`, `random_start=false`이고 PGD default는 같은 step과
iteration에 `random_start=true`를 사용합니다. BIM은 iterative FGSM with projection이며,
randomized start가 필요한 경우 PGD를 사용합니다. DeepFool default는 `norm=l2`,
`step_size=epsilon`, `iterations=20`, `random_start=false`이고 CW default는 같은 norm에
`iterations=50`, margin optimization을 사용합니다. AutoAttack은 deterministic FGSM/BIM/PGD
ensemble로 각 표본의 최악 margin을 선택합니다. 표준 APGD/FAB/Square 조합과는 구분됩니다.

응답은 같은 sample population의 clean/robust accuracy, clean-correct denominator 기반
attack success rate, raw counts, maximum observed L∞/L2, clean/adversarial prediction fingerprints,
gradient status를 포함합니다. 입력 gradient가 모두 0이면 run은 실패로 꾸며지지 않고
`gradient_status="flat"`과 warning을 반환합니다.

## Runtime boundary

Registry handle과 run index는 process-local입니다. API 재시작 후 list가 초기화되지만
dataset/model/baseline artifact 파일은 configured storage에 남습니다. PostgreSQL/Redis는
향후 persistence/worker 경계이며 현재 endpoint readiness에 포함되지 않습니다.
