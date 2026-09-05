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
| `POST / GET` | `/api/v1/registry/remote-attacks` | Authorized query-only black-box attack on a remote endpoint / list |
| `POST / GET` | `/api/v1/registry/llm-red-team` | Authorized prompt-injection red-team of a remote LLM / list |
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
| `POST` | `/api/v1/registry/artifacts/gc` | Delete artifact files no retained record references |

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

실패한 job은 `AISHIELD_JOB_MAX_ATTEMPTS`(기본 1)까지 재시도합니다. 재시도가 소진되면
FAILED로 dead-letter되어 job 목록에 조회 가능한 증거로 남습니다(사라지지 않습니다).

Job 상태 전이는 두 프로세스가 각각 자신이 관찰한 것을 metadata store에 기록합니다
(API가 `queued`, worker가 `running`/`succeeded`/`failed`).

```bash
AISHIELD_METADATA_BACKEND=postgresql AISHIELD_JOB_BACKEND=redis \
  docker compose --profile worker up --build
```

## Remote black-box attacks (real deployed models)

White-box attacks (FGSM/PGD/…) need the model's weights and gradient. To test a
model you do **not** own the weights of — a deployed image classifier reachable
over HTTP — AIShield runs a **query-only black-box attack**: a bounded Square-style
random search that sends images and reads back class scores, never a gradient.

This is gated so it cannot be pointed at arbitrary hosts. Two independent checks
must both pass:

1. **Allowlist.** `AISHIELD_ATTACK_TARGETS_ALLOWLIST` lists the hostnames you are
   authorized to test. Empty (the default) refuses every target, so the feature is
   off until a host is named deliberately.
2. **Per-request confirmation.** The request must set `authorized: true`, an
   explicit statement that you may test this target. It is never defaulted to true.

A target that fails either check returns **403**. The query budget is bounded by
`AISHIELD_REMOTE_ATTACK_MAX_QUERIES`; a request asking for more is refused.

The endpoint you point at must speak a small JSON contract:

```
POST <endpoint_url>
request:  {"format": "aishield.image-scores.v1", "images": [[[[...]]]]}  # (N,C,H,W) in [0,1]
response: {"scores": [[...]]}                                            # (N, num_classes)
```

The recorded evidence carries the same paired clean/robust/ASR metrics as a
white-box run, plus the real query count and the maximum perturbation observed.
The target is identified by host and a secret-free fingerprint — auth headers and
query strings are never recorded.

```bash
curl -X POST http://localhost:8000/api/v1/registry/remote-attacks -H 'Content-Type: application/json' -d '{
  "endpoint_url": "http://model.internal.example.com/score",
  "num_classes": 10, "dataset_id": "<uuid>", "authorized": true,
  "epsilon": 0.03137, "max_queries": 5000, "max_samples": 256
}'
```

## LLM prompt-injection red-team

A separate track from the image attacks, with its own threat model and metrics —
no perturbation norm, no accuracy on a labelled set. It probes a remote LLM
endpoint for prompt injection: a secret canary is planted in the system prompt,
inputs try to make the model leak it, follow an injected instruction, or yield to a
jailbreak framing — including multi-turn attacks that steer across several turns
before the ask — and a detector (obfuscation-aware) decides per probe whether the
target held. Each probe records how many turns it took and whether the final reply
read as a refusal (an auxiliary signal, never used to decide success). Multi-turn
conversations are sent as a `messages` array. The aggregate is an injection success
rate by category, not robust accuracy.

These are diagnostic instruments for a model you operate, not an exploit library:
the probe texts are generic and benign, and the value is the detector telling you
whether your model is vulnerable so you can harden it.

Gated like the remote image attack: the host must be in
`AISHIELD_LLM_TARGETS_ALLOWLIST` (empty refuses every target) and each request
must set `authorized: true`; either failing returns 403.

Prompts and completions can carry sensitive content, so by default only their
SHA-256 fingerprints and the detector verdict are recorded. Set `retain_text:
true` to keep the raw text — an explicit opt-in.

The endpoint contract:

```
POST <endpoint_url>
request:  {"format": "aishield.llm-chat.v1", "system": "...", "prompt": "..."}
response: {"completion": "..."}
```

```bash
curl -X POST http://localhost:8000/api/v1/registry/llm-red-team -H 'Content-Type: application/json' -d '{
  "endpoint_url": "http://llm.internal.example.com/chat", "authorized": true,
  "categories": ["system_prompt_leak", "instruction_override"]
}'
```

## Authentication

기본값은 **열림**입니다. `AISHIELD_API_KEY`(16자 이상)를 설정하면 `/api/v1/registry`의
**모든** route가 키를 요구합니다. 라우터 단위로 적용하므로 새 route를 추가할 때 보호를
빠뜨릴 수 없습니다.

| 경로 | 키 필요 |
| --- | --- |
| `/api/v1/registry/**` | ✅ 읽기 포함 (artifact는 증거이므로) |
| `/api/v1/health/live`, `/health/ready` | ❌ 프로브는 비밀 없이 동작해야 함 |
| `/api/v1`, `/api/docs`, `/api/openapi.json` | ❌ 스키마만, 데이터 없음 |

키는 두 header 중 하나로 보냅니다.

```bash
curl -H "X-API-Key: $AISHIELD_API_KEY" http://localhost:8000/api/v1/registry/datasets
curl -H "Authorization: Bearer $AISHIELD_API_KEY" http://localhost:8000/api/v1/registry/datasets
```

비교는 `secrets.compare_digest`로 수행하므로 타이밍으로 키를 복원할 수 없습니다. 키는
로그에 남지 않고 URL에 들어가지 않습니다 — query parameter로 받으면 proxy와 server 로그에
그대로 남기 때문입니다.

Dashboard는 401을 받으면 "API가 죽었다"가 아니라 **키 입력을 요청**합니다. 입력한 키는
`sessionStorage`에만 두어 탭을 닫으면 사라집니다. Artifact와 envelope 다운로드는 header를
실을 수 없는 `<a href>` 대신 인증된 fetch 후 blob으로 저장합니다.

인증되지 않은 요청은 존재하지 않는 리소스에도 404가 아니라 401을 반환합니다. 키 없는
호출자가 무엇이 존재하는지 알 수 없어야 하기 때문입니다.

## Reproducible images

모든 base image는 tag가 아니라 digest로 고정되어 있습니다. Tag는 움직이므로, 고정하지
않으면 같은 Dockerfile을 다시 빌드해도 다른 결과가 나올 수 있습니다.

빌드 시 `AISHIELD_CONTAINER_IMAGE_DIGEST`를 주입하면 그 값이 모든 evidence envelope의
`container_image_digest`에 기록되어, 결과를 만들어낸 이미지를 역추적할 수 있습니다.

```bash
docker build -f docker/api.Dockerfile \
  --build-arg AISHIELD_CONTAINER_IMAGE_DIGEST="$(docker inspect --format='{{index .RepoDigests 0}}' <image>)" \
  --build-arg AISHIELD_GIT_COMMIT="$(git rev-parse HEAD)" .
```

값이 digest 형식이 아니면 기록하지 않고 경고를 남깁니다. 잘못된 provenance는 없는 것보다
나쁘기 때문입니다 — 재현을 시도하는 사람을 엉뚱한 이미지로 보냅니다.

### CUDA worker

`docker/worker.cuda.Dockerfile`은 CPU 이미지와 **같은 torch 버전**을 CUDA wheel로 설치합니다.
결과가 device 때문에 달라질 수는 있어도 framework 버전 때문에 달라지지는 않습니다.
`AISHIELD_COMPUTE_DEVICE=cuda`이면 CUDA를 쓸 수 없을 때 조용히 CPU로 내려가지 않고 기동에
실패하므로, CUDA로 기록된 run은 실제로 CUDA를 사용한 것입니다.

```bash
AISHIELD_METADATA_BACKEND=postgresql AISHIELD_JOB_BACKEND=redis \
  docker compose --profile gpu-worker up --build
```

## Artifact garbage collection

`POST /api/v1/registry/artifacts/gc` reclaims artifact files that no retained
baseline or model references any more — a checkpoint for an evicted model, a
directory for a baseline no longer held, or an interrupted `.tmp` write. It never
removes a file a live record points to, never follows symlinks, and never touches
the append-only journal. Pass `dry_run=true` to preview what would be removed
(files, directories, reclaimed bytes) without deleting.

Bounding the record set itself — as opposed to orphaned files — is a separate,
backend-level concern the append-only journal deliberately leaves alone.

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
