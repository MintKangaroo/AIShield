# AIShield 작업 인수인계

마지막 갱신일: 2026-07-30

## 현재 브랜치와 범위

- 작업 브랜치: `develop`
- 최신 커밋: `16806be docs: update project handoff and roadmap`
- 안정 기준: reproducible clean baseline + bounded attacks/defenses + dashboard + evidence API
- Registry/run index: API process memory, metadata는 append-only journal에도 기록
- Dataset/model/baseline artifact: configured local directory 또는 Docker volume
- 공개 download: 기본 거부

기존 사용자 작업이던 clean-baseline 구현을 보존해 완성했고, 전체 제품 흐름을 닫기 위해
다음이 추가되었습니다.

- clean accuracy/loss, confusion matrix, per-class precision/recall, latency
- environment/model/dataset/prediction evidence
- atomic JSON report와 confusion matrix PNG
- exact-config baseline rerun 검증
- artifact download endpoint와 root/symlink check
- deterministic zero-download `Signal-10` adapter
- bounded FGSM/BIM/PGD/DeepFool/CW/AutoAttack, paired metrics, norm verification, gradient warning
- dataset/model/baseline/attack/artifact를 조작하는 React dashboard
- 실제 API run을 사용한 README screenshots와 screenshot automation
- adversarial training/TRADES, hashed checkpoint evidence
- APGD/FAB/Square bounded compatibility adapters와 epsilon strength curve/restarts
- robustness score API, surrogate-to-target transfer diagnostics
- `/registry/journal` metadata audit API
- bounded background training queue와 job status API

## 검증 기준

```bash
python -m ruff check .
python -m ruff format --check .
python -m mypy .
python -m pytest
python -m aishield.schemas.export --check schemas/experiment-result.schema.json

npm --prefix web ci
npm --prefix web run build

docker compose config --quiet
docker compose --profile gpu config --quiet
```

최근 검증 결과: backend `56 passed`, coverage `93.90%`, Ruff/mypy 통과. Frontend는
`npm --prefix web run build`로 TypeScript와 Vite production build를 검증합니다.

Docker CPU smoke는 dashboard, API, `/api` proxy health를 확인합니다. Zero-download product
smoke는 Dashboard의 `Launch zero-download demo`로 dataset → model → baseline → FGSM을
실행합니다.

## 중요한 설계 결정

- `robust_accuracy`는 adversarial input 전체 sample population의 accuracy입니다.
- `attack_success_rate` 분모는 clean-correct sample입니다. Raw counts도 함께 보존합니다.
- FGSM은 one step/no random start/step=epsilon 계약을 강제합니다.
- BIM은 iterative FGSM이며 random start를 거부합니다.
- PGD default는 step=`epsilon/4`, 10 iterations, random start입니다.
- DeepFool은 bounded L2 step과 observed L2를 기록합니다.
- CW는 bounded L2 margin optimization과 observed L2를 기록합니다.
- AutoAttack은 deterministic FGSM/BIM/PGD ensemble으로 worst-margin 결과를 기록합니다.
- Defense endpoint는 bit-depth preprocessing 전후와 adaptive attack 지표를 비교합니다.
- 모든 attack input은 finite `[0,1]` tensor여야 하며 projection 후 observed L∞를 검사합니다.
- Flat gradient는 성공이 아니라 masking warning입니다.
- Synthetic dataset과 untrained SmallCNN 결과는 security benchmark가 아닙니다.
- `<artifact_root>/registry/journal.jsonl`은 canonical JSON metadata를 즉시 append/flush합니다.
- `POST /api/v1/registry/training/jobs`는 bounded in-process worker로 비동기 학습을 실행합니다.
- `GET /api/v1/registry/jobs/{id}`에서 queued/running/succeeded/failed 상태를 조회합니다.
- PostgreSQL/Redis Compose 서비스와 설정은 준비되어 있지만 실제 repository/Redis adapter는
  아직 연결하지 않았습니다. 현재 queue/journal은 교체 가능한 경계 구현입니다.

## 다음 작업 우선순위

1. PostgreSQL repository와 journal replay 기반 restart recovery
2. Redis-backed resource-isolated evaluation worker 및 CPU/CUDA image pinning
3. strength curve/run-to-run 비교와 sample triplet dashboard UI
4. black-box/white-box masking diagnostics 및 independent numerical fixtures
5. portable experiment export/import

세부 범위는 `docs/roadmap.md`를 기준으로 합니다. 새 기능은 numerical unit test, API
contract test, strict typing, README/API 문서 갱신을 함께 완료해야 합니다.

## 다음 세션 시작 명령

```bash
git switch develop
git pull --ff-only origin develop
git status --short --branch
docker compose config --quiet
```

작업 후에는 Docker backend 품질 게이트와 `npm --prefix web run build`를 실행하고,
`HANDOFF.md`, `README.md`, `docs/api.md`, `docs/roadmap.md`를 함께 갱신합니다.
