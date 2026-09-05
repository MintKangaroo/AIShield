# AIShield 작업 인수인계

마지막 갱신일: 2026-08-29

## 현재 브랜치와 범위

- 작업 브랜치: `develop`
- 안정 기준: reproducible clean baseline + bounded attacks/defenses + dashboard + evidence API
- Registry/run index: API process memory. 모든 metadata는 append-only journal에 기록되며
  프로세스 시작 시 journal replay로 복구됩니다.
- Dataset/model/baseline artifact: configured local directory 또는 Docker volume
- 공개 download: 기본 거부

## 이번 세션에서 추가된 것

### 1. 백엔드 기능의 대시보드 노출

`defenses`, `defenses/transfer`, `robustness-score`, `jobs`, `journal`은 API에만 있고 UI에서
도달할 수 없었습니다. 이제 전부 노출됩니다.

- **Defense lab** 페이지 — before/after/adaptive 비교, gradient masking 경고, transfer 표
- **Jobs & training** 페이지 — queued/running/succeeded/failed/cancelled 상태와 소요 시간.
  진행 중인 job이 있으면 2.5초 간격으로 자동 갱신하고, 없으면 폴링하지 않습니다.
- **Journal** 페이지 — kind별 필터, 원본 JSON 확인, replay 실행과 요약
- **Attack lab** — run 다중 선택 → robustness score 집계(formula version, evidence coverage,
  해석 한계 경고). APGD/FAB/Square도 선택 가능해졌습니다.
- `App.tsx` 1,904줄을 `components/`, `forms/`, `pages/`, `hooks/`로 분해했습니다.

### 2. 구조화 로깅

`src/aishield/core/logging.py` — JSON 한 줄 포매터, `X-Request-ID` 상관 id(contextvar).
`src/aishield/api/middleware.py` — 요청 단위 id 부여·전파·응답 header 반영, 소요 시간 기록.
`RegistryService._timed_run`이 모든 baseline/attack/defense/transfer/training 실행의
시작·완료·실패를 run_id·duration과 함께 남깁니다.

### 3. Job queue 결함 수정

- `max_pending`(기본 16) 초과 시 거부 → 429. 이전에는 무제한 큐잉이 가능했습니다.
- 완료 job record는 `retained_jobs`(기본 256)만 보존하고 오래된 것부터 제거합니다.
- job record가 journal에 기록됩니다(observer 경계).
- 시작 전 job 취소(`POST /jobs/{id}/cancel`, 이미 시작했으면 409).
- worker 실패 시 traceback이 로그에 남습니다. 이전에는 `str(error)`만 남았습니다.
- job 등록 전에 model/dataset을 검증해 잘못된 입력이 실패 job이 아니라 404가 됩니다.

### 4. 동시 실행 상한

`AISHIELD_MAX_CONCURRENT_RUNS`(기본 1) 프로세스 전역 semaphore. 동기 API 요청은 slot이
없으면 즉시 429 + `Retry-After`, background worker는 `job_slot_timeout_seconds`까지 대기.

### 5. 테스트

- 백엔드 89 → **240 tests**, coverage 91.9% → **93.4%**
  (PostgreSQL/Redis 없이도 198 passed + 42 skipped, coverage 91.5%로 gate 통과)
- 프론트엔드 0 → **54 tests** (+ run-comparison 로직 17, 대시보드 커밋에서 합류 예정)
- `RedisJobQueue`는 주입한 in-memory client로도 검증하므로, 서버 없이 `pytest`만 돌려도
  90% gate가 유지됩니다. 실제 broker 대상 통합 테스트는 그대로 CI에서 돕니다.
- 신규: `test_jobs_queue.py`, `test_registry_journal.py`, `test_registry_jobs.py`,
  `test_logging.py`, `test_experiment_export.py`, `test_cli_experiment.py`,
  `test_journal_replay.py`, `test_dashboard_contract.py`
- 프론트엔드 테스트 **0 → 43** (Vitest + Testing Library). `format`, `attacks`, `api`,
  `useRegistry`, `AttackForm`, `JournalTable`, `JobsTable`을 다룹니다.
- `test_dashboard_contract.py`는 대시보드가 호출하는 모든 경로가 실제 OpenAPI에 있는지
  검사합니다. 이 테스트가 실제 버그를 하나 잡았습니다(아래 참조).

### 6. Portable experiment export/import

`src/aishield/registry/experiment.py`가 retained run record를 `ExperimentResult` envelope으로
변환합니다. `GET /baselines/{id}/experiment`로 내보내고 `POST /experiments`로 가져옵니다.
Aggregate score를 포함해도 근거가 된 raw metric이 함께 남습니다. 가져온 envelope은 감사용
증거이며 새 run을 만들 수 있는 runnable handle이 아닙니다.

### 7. 헤드리스 CLI

`aishield-run experiment.json --output result.json` — dataset → model → baseline → attacks →
defenses를 실행하고 schema-valid envelope을 출력합니다. Spec은 `extra="forbid"`라 오타 난
parameter가 조용히 기본값으로 실행되지 않습니다.

### 8. Journal replay 재시작 복구

`AISHIELD_REPLAY_JOURNAL_ON_START`(기본 true). Run evidence는 항상 복구하고, dataset/model
handle은 디스크 파일이 기록된 content hash와 일치할 때만 복구합니다. 복구된 model은 기록된
identity를 유지합니다. Background job은 복구하지 않습니다. 손상된 journal이 API 기동을
막지 않습니다.

### 9. PostgreSQL metadata backend

`src/aishield/registry/store.py`에 `MetadataStore` 프로토콜을 두고 두 구현을 둡니다.

| backend | 저장 위치 | 용도 |
| --- | --- | --- |
| `journal` (기본) | `<artifact_root>/registry/journal.jsonl` | 서버 없는 단일 프로세스 데모 |
| `postgresql` | `registry_metadata` 테이블 | 여러 프로세스가 하나의 registry를 공유 |

- Schema는 journal을 그대로 반영합니다(record 하나 = row 하나, 같은 canonical JSON).
  `model_version_id`/`dataset_id`는 인덱스용 컬럼으로 뽑지만 payload의 투영일 뿐입니다.
- `tests/unit/test_metadata_store.py`가 **하나의 계약 테스트를 두 backend에 모두** 돌립니다.
  `AISHIELD_TEST_DATABASE_URL`이 없으면 PostgreSQL 쪽은 skip합니다.
- `tests/unit/test_postgres_registry.py`가 전체 registry 흐름·재시작 복구·두 프로세스 공유를
  실제 데이터베이스로 검증합니다.
- `.[postgres]` extra(sqlalchemy + psycopg3). Docker image에는 포함되어 있습니다.
- CI backend job에 postgres 16 service를 붙여 실제로 실행합니다.

### 10. Readiness 엔드포인트

`GET /api/v1/health/ready` — 설정된 store에 실제로 접근해 보고 실패하면 503. `/health/live`는
프로세스 liveness만 보고하므로 데이터베이스가 죽어도 200을 유지합니다. 증거를 기록할 수 없는
프로세스를 healthy로 보고하면 정작 중요한 실패가 가려지기 때문에 두 신호를 분리했습니다.
데이터베이스가 시작 시점에 닿지 않으면 API는 조용히 뜨지 않고 명확한 오류로 실패합니다.

### 11. 프로세스 밖 evaluation worker (Redis)

API가 job을 수락만 하고, 별도 `aishield-worker` 프로세스가 실행합니다.

- Task를 closure가 아니라 직렬화 가능한 기술자(`aishield/jobs/tasks.py`)로 바꿨습니다.
  closure는 프로세스 경계를 넘을 수 없어서 이게 선결 조건이었습니다.
- `JobBackend` 프로토콜 뒤에 두 구현: `inprocess`(기본, thread pool)와 `redis`.
- Worker는 runtime handle을 넘겨받지 않습니다. 공유 metadata store에서 dataset/model을
  직접 복구하고 content hash를 검증한 뒤 실행합니다. 따라서 `redis` job backend는
  `postgresql` metadata backend와 함께 씁니다.
- `BLPOP`으로 원자적으로 가져가므로 두 worker가 같은 job을 실행하지 않습니다(테스트로 고정).
- Job 상태 전이는 두 프로세스가 각자 관찰한 것을 metadata store에 기록합니다
  (API가 `queued`, worker가 `running`/`succeeded`/`failed`).
- `docker compose --profile worker up`으로 실행합니다. `.[redis]` extra.

실제 검증: API와 worker를 별개의 OS 프로세스로 띄워 job이 worker에서만 실행되고
(API 로그에 training run 0건), worker가 만든 증거가 공유 저장소를 통해 API에 보이는 것을
확인했습니다.

### 12. 재현 가능한 이미지와 provenance 기록

- 모든 base image(python/node/nginx/postgres/redis/cuda)를 tag가 아니라 **digest**로
  고정했습니다. Tag는 움직이므로 고정하지 않으면 같은 Dockerfile이 다른 결과를 냅니다.
- `container_image_digest`는 evidence 계약에 **있었지만 아무도 채우지 않아 항상 null**
  이었습니다. 이제 빌드 시 `--build-arg AISHIELD_CONTAINER_IMAGE_DIGEST=...`로 주입하면
  모든 evidence envelope에 기록됩니다.
- digest 형식이 아닌 값은 기록하지 않고 경고만 남깁니다. 잘못된 provenance는 없는 것보다
  나쁘기 때문입니다 — 재현을 시도하는 사람을 엉뚱한 이미지로 보냅니다.
- `docker/worker.cuda.Dockerfile` + `gpu-worker` compose profile. CPU 이미지와 **같은
  torch 버전**을 CUDA wheel로 설치하므로 결과가 framework 버전 때문에 달라지지 않습니다.
  `AISHIELD_COMPUTE_DEVICE=cuda`는 CUDA를 쓸 수 없으면 조용히 CPU로 내려가지 않고 기동에
  실패합니다.
- CUDA 이미지는 **빌드와 import까지만 검증했습니다.** 이 머신에 GPU가 없어 GPU 실행은
  검증하지 못했습니다. 확인한 것: torch 2.13.0+cu126, cudnn 91002, entry point, digest 기록,
  그리고 GPU 없이 `cuda`를 요구하면 기동을 거부하는 것.

### 13. 선택적 API key 인증

기본값은 **열림**입니다. 로컬 데모와 CI가 비밀 관리 없이 동작하도록 한 선택이며, 운영에서만
`AISHIELD_API_KEY`(16자 이상)를 설정합니다.

- 라우터 단위로 적용하므로 새 route를 추가할 때 보호를 빠뜨릴 수 없습니다. 테스트가
  OpenAPI에서 registry route를 읽어 전부 401인지 확인합니다.
- 읽기도 보호합니다. artifact가 이 플랫폼이 지키려는 증거이기 때문입니다.
- Health probe와 OpenAPI 스키마는 열어둡니다. 프로브는 비밀 없이 동작해야 하고, 스키마에는
  데이터가 없습니다.
- `X-API-Key` 또는 `Authorization: Bearer`. 비교는 `secrets.compare_digest`(타이밍 공격 방지).
- 키는 로그에 남지 않고 URL에 들어가지 않습니다. query parameter로 받으면 proxy·server
  로그에 그대로 남기 때문입니다.
- Dashboard는 401을 "API 죽음"이 아니라 **키 요청**으로 구분해 처리합니다(`ApiState`에
  `unauthorized` 추가). 키는 `sessionStorage`에만 두어 탭을 닫으면 사라집니다.
- Artifact/envelope 다운로드는 `<a href>`가 header를 실을 수 없으므로 인증된 fetch 후
  blob 저장으로 바꿨습니다.

실제 브라우저로 전 과정을 확인했습니다: 키 없이 접속 → "API KEY REQUIRED" + 키 입력창 자동
표시 → 키 입력 → 콘솔 해제 → baseline 목록 표시 → envelope 다운로드 성공.

### 14. 실제 배포 모델 대상 query-only black-box 공격

**질문: 이게 실제 AI 모델 모의해킹이 되나?** 이제 이미지 분류기에 한해 **된다.** 가중치를
갖고 있지 않은 배포 모델을 HTTP로 공격합니다.

- `aishield/attacks/blackbox.py` — score 기반 bounded Square 탐색. gradient 없이 oracle이
  돌려주는 score만으로 margin을 낮춥니다. 로컬 모델을 oracle로 감싸 오프라인 테스트하고,
  원격 endpoint에도 그대로 씁니다. 코어는 어느 쪽인지 모릅니다.
- `aishield/attacks/remote.py` — 원격 분류기 HTTP 클라이언트(stdlib urllib, 런타임 의존성
  없음). 작은 JSON 계약(`aishield.image-scores.v1`), 응답 형식·유한성 엄격 검증.
- `POST /api/v1/registry/remote-attacks`.

**인가 (임의 대상 공격 방지, 두 관문 모두 필요):**
- `AISHIELD_ATTACK_TARGETS_ALLOWLIST`에 등록된 host만. 비어 있으면 전부 거부(기본 off).
- 요청마다 `authorized: true` 명시. 기본값 아님.
- 둘 중 하나라도 실패 → 403. query 예산은 `AISHIELD_REMOTE_ATTACK_MAX_QUERIES`로 상한.
- secret(auth header, query string)은 evidence에 기록하지 않음. 대상은 host + 지문으로만.

**실제 검증:** 테스트가 진짜 `ThreadingHTTPServer`로 모델을 띄우고 loopback TCP로
query-only 공격을 수행합니다(`test_attacks_a_real_served_model_over_http`). ε=0.4가
0.35 signal을 이겨 예측을 뒤집고, bound 준수, query 수가 실제 서버 호출 수와 일치함을
확인했습니다. 인가 거부 5종(플래그·빈 allowlist·미등록 host·query 상한·잘못된 scheme)도 고정.

**아직 아닌 것 (정직하게):** 이미지 분류기 + score 반환 endpoint에 한합니다. LLM 레드팀은
별도 트랙(메모리 [[llm-redteam-followup]]에 기록, 추후 진행). decision-only(라벨만 반환)
endpoint용 HopSkipJump류는 아직 없습니다 — 현재는 score 기반 Square만.

### 15. LLM 레드팀 트랙 (첫 슬라이스)

이미지 엔진과 **완전히 분리된** `aishield.llm` 패키지. 위협·지표 계약을 재사용하지 않습니다
(L∞·accuracy 없음). query-only prompt-injection 레드팀:

- system prompt에 canary를 심고, 유출(`system_prompt_leak`)·주입 marker 강제
  (`instruction_override`)를 시도, probe별 detector가 성공 판정. 지표는 카테고리별
  injection success rate.
- **probe는 진단 도구이지 exploit 무기고가 아닙니다.** 텍스트는 일반적·무해하게 유지;
  가치는 "내 모델이 이 부류에 취약한가"를 측정하는 detector에 있습니다.
- 인가: `AISHIELD_LLM_TARGETS_ALLOWLIST` + 요청별 `authorized` (이미지 원격 공격과 동일).
- 프라이버시: prompt/completion 기본 해시만 저장, `retain_text` opt-in 시에만 원문.
- `aishield/llm/{contracts,probes,remote,runner}.py`, `POST/GET /registry/llm-red-team`.
- 실제 HTTP LLM 서버로 end-to-end 검증(취약 모델 ISR 1.0 vs 하드닝 0.0), 인가 거부 3종.

**추가 완료 (2차):** jailbreak-framing 카테고리(roleplay/hypothetical/developer/prefix,
무해한 planted token 대상), 난독화 인식 detector(하이픈/공백/역순/base64/base32/hex),
그리고 대시보드 **LLM red-team** 페이지(취약/held 판정, 카테고리별 hit, probe별 결과,
text redaction 표시). 실제 취약 LLM을 HTTP로 띄워 14/14 성공을 콘솔에서 확인.

**추가 완료 (3차):** multi-turn(대화 수준) probe — 여러 턴 유도 후 추출. chat 계약(messages)
지원, ProbeResult에 turns/refused 추가, 난독화/거부 detector. 실증: crescendo-취약 모델이
단일 턴 jailbreak는 전부 막지만 multi-turn엔 무너짐(single 0.00 vs multi 0.67).

**아직 아닌 것:** 더 넓은 probe corpus, per-turn 증거.

## 이번에 잡은 실제 버그

1. **대시보드가 존재하지 않는 경로 호출** — transfer는 `/registry/defenses/transfer`인데
   client가 `/registry/transfers`를 불렀습니다. 처음 작성한 테스트도 같은 오답을 encode해서
   통과했고, OpenAPI 대조 테스트를 추가하고 나서야 드러났습니다.
2. **Journal replay가 trained checkpoint를 놓침** — checkpoint 파일명을 `{state_sha}.pt`로
   추측했는데 trained model은 `trained-{state_sha}.pt`입니다. 기록된 artifact URI에서
   파일명을 읽도록 고쳤습니다.
3. **Journal replay가 trained model의 identity를 덮어씀** — `SmallCNNAdapter.load`가 파생한
   record를 그대로 쓰면 trained model이 새 SmallCNN identity로 되살아났습니다. 이제 가중치만
   검증하고 기록된 record를 유지합니다.
4. **Job backend를 추출하면서 job record 저널링이 빠짐** — `JobQueue` 생성에서 `observer`를
   떨어뜨렸습니다. `test_registry_jobs.py`가 즉시 잡았고, 두 backend 모두에 observer를
   복구했습니다.

## 검증 기준

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest
python -m aishield.schemas.export --check schemas/experiment-result.schema.json

# PostgreSQL/Redis backend까지 검증하려면 (없으면 해당 테스트는 skip)
docker run -d --name aishield-pg -e POSTGRES_PASSWORD=aishield -e POSTGRES_USER=aishield \
  -e POSTGRES_DB=aishield -p 55432:5432 postgres:16-alpine
docker run -d --name aishield-redis -p 56379:6379 redis:7-alpine
AISHIELD_TEST_DATABASE_URL=postgresql://aishield:aishield@127.0.0.1:55432/aishield \
AISHIELD_TEST_REDIS_URL=redis://127.0.0.1:56379/0 \
  python -m pytest

npm --prefix web ci
npm --prefix web run check
npm --prefix web run test
npm --prefix web run build

docker compose config --quiet
docker compose --profile gpu config --quiet
```

최근 검증 결과: backend `255 passed`(PostgreSQL·Redis 포함) / `213 passed + 42 skipped`
(서비스 없이), coverage `93.36%` / `91.61%`, Ruff/mypy 통과. Frontend `54 passed`.
Frontend `43 passed`, TypeScript no-emit과 Vite production build 통과.

라이브 검증도 수행했습니다: 실제 uvicorn + Vite dev server를 띄우고 defense·transfer·
job queue·429 back-pressure·export/import·재시작 복구를 확인했으며, Defense lab / Jobs /
Journal / Attack lab(score) 페이지를 Playwright로 캡처해 렌더링을 확인했습니다.

## 환경 주의사항 (로컬)

이 저장소에는 이전에 root 권한으로 실행된 흔적이 남아 있어 일부 작업이 막힙니다.
다음 명령을 한 번 실행해야 `npm ci`와 `npm run build`가 정상 동작합니다.

```bash
sudo rm -rf web/dist web/node_modules .coverage artifacts/registry .ruff_cache
npm --prefix web ci
```

`.venv`는 이번 세션에서 Python 3.12로 재생성했습니다(이전 것은 `/workspace` 경로를 가리키는
깨진 interpreter였습니다).

## 중요한 설계 결정

- `robust_accuracy`는 adversarial input 전체 sample population의 accuracy입니다.
- `attack_success_rate` 분모는 clean-correct sample입니다. Raw counts도 함께 보존합니다.
- FGSM은 one step/no random start/step=epsilon 계약을 강제합니다.
- BIM은 iterative FGSM이며 random start를 거부합니다.
- PGD default는 step=`epsilon/4`, 10 iterations, random start입니다.
- Flat gradient는 성공이 아니라 masking warning입니다.
- Synthetic dataset과 untrained SmallCNN 결과는 security benchmark가 아닙니다.
- `max_concurrent_runs=1`이 기본값인 이유: 한 장비에서 여러 전체 torch 평가를 동시에
  실행하면 latency 근거가 왜곡되고 메모리가 고갈됩니다. Background job이 slot을 잡고 있으면
  동기 요청이 429를 받는 것은 의도된 동작입니다.
- Journal replay는 절대 다운로드하지 않습니다. 이미 존재하는 split만 다시 읽습니다.
- Metadata backend는 `journal`이 기본입니다. PostgreSQL은 여러 프로세스가 registry를
  공유해야 할 때만 켭니다. 두 backend는 append-only이며 같은 계약 테스트를 통과합니다.
- 데이터베이스가 시작 시점에 닿지 않으면 API는 뜨지 않습니다. 증거를 기록할 수 없는 상태로
  기동하는 것보다 명확히 실패하는 편이 낫다고 판단했습니다.
- Job backend는 `inprocess`가 기본입니다. `redis`는 무거운 평가를 API에서 떼어낼 때만
  켜며, worker가 metadata를 공유해야 하므로 `postgresql`과 함께 씁니다.
- Worker는 실패한 job을 재시도하지 않습니다. 재시도가 안전한지는 task 종류에 따라 다르고,
  현재는 실패를 증거로 남기는 편이 조용히 다시 도는 것보다 낫다고 판단했습니다.

## 다음 작업 우선순위

1. 선택적 API key 인증 — 현재 API는 완전 개방이며 artifact download와 학습 트리거가
   무방비입니다
3. run-to-run 비교와 sample triplet dashboard UI
4. black-box/white-box masking diagnostics 및 independent numerical fixtures
5. CI에 `pip-audit`/`npm audit`, Dependabot, 프론트엔드 ESLint 추가
6. (완료) Artifact garbage collection — orphan sweep. retained record가 참조하지 않는
   checkpoint·baseline 디렉터리·.tmp만 삭제(현재 레코드는 불변), dry-run 미리보기 제공.
   레코드 집합 자체의 상한은 append-only 저널 특성상 별도 backend 과제로 남김
7. Worker의 dead-letter 처리 — 현재 실패한 job은 기록만 되고 재시도하지 않습니다

세부 범위는 `docs/roadmap.md`를 기준으로 합니다. 새 기능은 numerical unit test, API
contract test, strict typing, README/API 문서 갱신을 함께 완료해야 합니다.

## 다음 세션 시작 명령

```bash
git switch develop
git status --short --branch
make check
npm --prefix web run test
```
