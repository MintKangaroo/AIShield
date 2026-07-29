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
| `POST` | `/api/v1/registry/attack-curves` | Same attack over increasing epsilon strengths |
| `POST` | `/api/v1/registry/defenses` | Before/after preprocessing-defense evaluation |
| `GET` | `/api/v1/registry/defenses` | Defense evaluation list |
| `POST` | `/api/v1/registry/defenses/transfer` | Surrogate-to-target transfer evaluation |
| `GET` | `/api/v1/registry/defenses/transfer` | Transfer evaluation list |
| `POST` | `/api/v1/registry/robustness-score` | Transparent aggregate over attack evidence |
| `POST` | `/api/v1/registry/training` | Adversarial training 또는 TRADES checkpoint 생성 |
| `GET` | `/api/v1/registry/training` | Training evidence list |
| `GET` | `/api/v1/registry/journal` | Append-only metadata audit/export stream |

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

지원 algorithm은 `fgsm`, `bim`, `pgd`, `deepfool`, `cw`, `autoattack`, `apgd`, `fab`, `square`입니다. FGSM/BIM/PGD/
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
ensemble로 각 표본의 최악 margin을 선택합니다. APGD/FAB/Square는 bounded deterministic
compatibility adapter이며 원본 reference library와의 수치적 parity를 주장하지 않습니다.

응답은 같은 sample population의 clean/robust accuracy, clean-correct denominator 기반
attack success rate, raw counts, maximum observed L∞/L2, clean/adversarial prediction fingerprints,
gradient status를 포함합니다. 입력 gradient가 모두 0이면 run은 실패로 꾸며지지 않고
`gradient_status="flat"`과 warning을 반환합니다.

`POST /registry/attack-curves`는 같은 모델·데이터에서 epsilon을 증가시키며 반복 실행합니다.
`restarts`를 지정하면 각 epsilon을 seed를 증가시켜 여러 번 실행하므로, 결과를 곡선으로
그리거나 restart별 최악값을 선택할 수 있습니다.

## Defense contract

`POST /registry/defenses`는 현재 `bit_depth` 전처리 방어를 지원합니다. `bit_depth=4`는
입력을 16단계로 양자화한 뒤 원래 model preprocessing을 적용합니다. 응답은 같은 표본에서
방어 전/후 clean accuracy, robust accuracy, attack success rate와 adaptive gradient 상태를
함께 기록합니다. 양자화는 비미분 연산이므로 adaptive gradient가 flat이면 강건성 증거가
아니라 gradient-masking 경고로 해석해야 합니다.

## Training contract

`POST /registry/training`은 원본 model bundle을 복제한 뒤 `adversarial_training` 또는
`trades` 목적함수로 CPU-safe 학습을 수행합니다. 원본 checkpoint는 변경하지 않으며,
학습 checkpoint의 state SHA-256, dataset manifest, 환경 snapshot과 최종 clean/PGD
robust metric을 `TrainingRunRecord`로 보존합니다. `step_size`는 `epsilon`보다 클 수
없고, `max_samples`로 데모·CI 실행 규모를 제한할 수 있습니다.

## Persistence boundary

Every loaded registry record and completed run is appended to
`<artifact_root>/registry/journal.jsonl` with canonical JSON and flushed immediately.
The journal is an audit/export boundary for future PostgreSQL and worker migration; live
PyTorch objects remain process-local and are never serialized into the journal.

## Runtime boundary

Registry handle과 live run index는 process-local입니다. metadata journal과 model/dataset
artifact는 configured storage에 남으며, PostgreSQL/Redis worker migration은 다음 운영 단계입니다.
