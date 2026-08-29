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

- 백엔드 89 → **156 tests**, coverage 91.9% → **93.8%** (PostgreSQL 없이는 141 + 15 skip)
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

## 검증 기준

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest
python -m aishield.schemas.export --check schemas/experiment-result.schema.json

# PostgreSQL backend까지 검증하려면 (없으면 해당 테스트는 skip)
docker run -d --name aishield-pg -e POSTGRES_PASSWORD=aishield -e POSTGRES_USER=aishield \
  -e POSTGRES_DB=aishield -p 55432:5432 postgres:16-alpine
AISHIELD_TEST_DATABASE_URL=postgresql://aishield:aishield@127.0.0.1:55432/aishield \
  python -m pytest

npm --prefix web ci
npm --prefix web run check
npm --prefix web run test
npm --prefix web run build

docker compose config --quiet
docker compose --profile gpu config --quiet
```

최근 검증 결과: backend `156 passed`(PostgreSQL 포함), coverage `93.78%`, Ruff/mypy 통과.
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
- Redis Compose 서비스는 여전히 코드에서 사용하지 않습니다.

## 다음 작업 우선순위

1. Redis-backed resource-isolated evaluation worker 및 CPU/CUDA image pinning.
   Metadata 공유는 끝났으므로 이제 실행 격리만 남았습니다.
2. 선택적 API key 인증 — 현재 API는 완전 개방이며 artifact download와 학습 트리거가
   무방비입니다
3. run-to-run 비교와 sample triplet dashboard UI
4. black-box/white-box masking diagnostics 및 independent numerical fixtures
5. CI에 `pip-audit`/`npm audit`, Dependabot, 프론트엔드 ESLint 추가
6. Artifact garbage-collection 정책 — journal/DB는 무한히 늘어나고 model checkpoint도
   정리되지 않습니다
7. Redis Compose service를 `profiles`로 분리 — 여전히 기동만 하고 쓰지 않습니다
   (PostgreSQL은 이제 실제로 사용 가능하므로 그대로 둡니다)

세부 범위는 `docs/roadmap.md`를 기준으로 합니다. 새 기능은 numerical unit test, API
contract test, strict typing, README/API 문서 갱신을 함께 완료해야 합니다.

## 다음 세션 시작 명령

```bash
git switch develop
git status --short --branch
make check
npm --prefix web run test
```
