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
| `GET` | `/api/v1/health/ready` | metadata store와 job broker 사용 가능 여부 (실패 시 503) |
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
| `POST` | `/api/v1/registry/training/jobs` | Queue bounded background training job |
| `GET` | `/api/v1/registry/jobs` | Background job list |
| `GET` | `/api/v1/registry/jobs/{id}` | Background job status |
| `POST` | `/api/v1/registry/jobs/{id}/cancel` | Cancel a job that has not started |
| `GET` | `/api/v1/registry/baselines/{id}/experiment` | Portable experiment envelope export |
| `POST` | `/api/v1/registry/experiments` | Portable experiment envelope import |
| `GET` | `/api/v1/registry/experiments` | Imported envelope list |
| `GET` | `/api/v1/registry/experiments/{id}` | Imported envelope |
| `GET` | `/api/v1/registry/journal` | Append-only metadata audit/export stream |
| `POST` | `/api/v1/registry/journal/replay` | Rebuild the in-memory index from stored metadata |

Request body는 `extra="forbid"`로 처리하므로 알 수 없는 field와 parameter typo는 422로
거부됩니다. Domain policy/compatibility 오류는 400, 존재하지 않는 registry identity는
404, 이미 시작된 job의 취소 시도는 409입니다. 모든 bounded evaluation slot이 사용 중이면
요청은 유효하지만 실행할 수 없으므로 `Retry-After`와 함께 429를 반환합니다.

모든 응답에는 `X-Request-ID` header가 포함됩니다. 요청에 같은 header를 보내면 그 값이
그대로 사용되어 proxy 구간까지 하나의 trace로 묶입니다. 서버 로그는 JSON 한 줄 형식이며
`request_id`, `run_id`, `run_kind`, `duration_ms`를 포함합니다.

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

Every loaded registry record and completed run is appended to the configured metadata
store as canonical JSON, and the write is committed before the API returns. Live PyTorch
objects remain process-local and never cross this boundary.

`AISHIELD_METADATA_BACKEND`으로 backend를 고릅니다.

| 값 | 저장 위치 | 쓰임 |
| --- | --- | --- |
| `journal` (기본) | `<artifact_root>/registry/journal.jsonl` | 서버가 필요 없는 단일 프로세스 데모 |
| `postgresql` | `registry_metadata` 테이블 | 여러 프로세스가 하나의 registry를 공유 |

두 backend는 같은 계약을 만족하며 동일한 테스트 스위트로 검증됩니다. PostgreSQL schema는
journal을 그대로 반영합니다. 즉 record 하나가 row 하나이고 payload는 같은 canonical JSON
입니다. `model_version_id`/`dataset_id`는 인덱스를 위해 컬럼으로 뽑아내지만 payload의
투영일 뿐이며 별도의 진실 원천이 아닙니다. 두 backend 모두 append-only이므로 같은 identity를
다시 기록해도 기존 row를 덮어쓰지 않습니다.

`/api/v1/registry/journal`과 `/journal/replay`는 backend와 무관하게 설정된 store를 읽습니다.

### Restart recovery

`AISHIELD_REPLAY_JOURNAL_ON_START`(기본 `true`)이면 프로세스 시작 시 저장된 metadata를
재생해 in-memory index를 복구합니다. `POST /api/v1/registry/journal/replay`로 직접 실행할 수도
있습니다. 복구 규칙은 다음과 같습니다.

- Run evidence(baseline/attack/defense/transfer/training)는 항상 복구됩니다.
- Dataset과 model handle은 디스크의 파일이 기록된 content hash와 여전히 일치할 때만
  복구됩니다. 불일치하면 조용히 넘어가지 않고 `skipped`에 이유가 남습니다.
- 복구된 model은 기록된 identity(`source`, `version`, UUID)를 그대로 유지합니다.
- Background job은 절대 복구하지 않습니다. 죽은 프로세스의 queued job은 실행된 적이
  없으므로 되살리면 거짓 증거가 됩니다.
- Journal이 손상되어도 API 기동은 실패하지 않습니다. 오류는 로그로 남기고 계속합니다.

## Execution boundary

`AISHIELD_JOB_BACKEND`으로 background job의 실행 위치를 고릅니다.

| 값 | 실행 위치 | 용도 |
| --- | --- | --- |
| `inprocess` (기본) | API 프로세스의 thread pool | 단일 컨테이너 데모 |
| `redis` | 별도 `aishield-worker` 프로세스 | 무거운 평가를 API와 분리 |

`redis` backend에서 API는 job을 **수락만** 하고 실행하지 않습니다. Task는 closure가 아니라
직렬화 가능한 기술자(`aishield.jobs.tasks`)로 큐에 들어가며, worker가 `BLPOP`으로 원자적으로
가져갑니다. 따라서 두 worker가 같은 job을 실행하는 일은 없습니다.

Worker는 runtime handle을 전달받지 않습니다. 공유 metadata store에서 dataset/model을
직접 복구하고 content hash를 검증한 뒤 실행하므로, 기록된 identity와 달라진 입력으로는
평가할 수 없습니다. 이 구조가 성립하려면 metadata가 공유되어야 하므로 `redis` job backend는
`postgresql` metadata backend와 함께 씁니다.

Job 상태 전이는 두 프로세스가 각각 자신이 관찰한 것을 metadata store에 기록합니다
(API가 `queued`, worker가 `running`/`succeeded`/`failed`).

```bash
AISHIELD_METADATA_BACKEND=postgresql AISHIELD_JOB_BACKEND=redis \
  docker compose --profile worker up --build
```

## Concurrency boundary

`AISHIELD_MAX_CONCURRENT_RUNS`(기본 `1`)가 동시에 실행 가능한 heavy evaluation 수를
제한합니다. 동기 API 요청은 slot이 없으면 즉시 429를 받고, background worker는
`AISHIELD_JOB_SLOT_TIMEOUT_SECONDS`까지 대기합니다. Job queue는
`AISHIELD_JOB_MAX_PENDING`(기본 16)을 초과하면 새 job을 거부하고,
`AISHIELD_JOB_RETAINED_RECORDS`(기본 256)개를 넘는 완료 job record는 오래된 것부터
정리합니다.

## Portable experiment envelope

`GET /api/v1/registry/baselines/{id}/experiment`는 하나의 baseline과 같은
model/dataset을 대상으로 한 모든 attack·defense 증거를 `schemas/experiment-result.schema.json`
계약에 맞는 self-contained envelope으로 내보냅니다. Aggregate score를 포함하더라도 그
근거가 된 raw metric이 함께 남으므로 점수만 남고 원본이 사라지는 일은 없습니다.
`POST /api/v1/registry/experiments`로 다시 가져올 수 있으며, 가져온 envelope은 감사용
증거일 뿐 새 run을 만들 수 있는 runnable handle이 아닙니다.

## Runtime boundary

Registry handle(torch module, dataset object)과 live run index는 process-local입니다.
Metadata와 model/dataset artifact는 configured storage에 남습니다. `postgresql` backend에서는
여러 프로세스가 같은 metadata를 공유하지만, runtime handle은 각 프로세스가 replay로 직접
복구합니다. Redis 기반 worker isolation은 다음 운영 단계입니다.

## Health boundary

`/health/live`는 프로세스 liveness만 보고합니다. dependency 상태를 가장하지 않으므로
데이터베이스가 죽어도 200을 반환합니다. `/health/ready`는 설정된 metadata store에 실제로
접근해 보고 실패하면 503을 반환합니다. 두 신호를 분리하는 이유는, 증거를 기록할 수 없는
프로세스를 healthy로 보고하면 정작 중요한 실패가 가려지기 때문입니다.
