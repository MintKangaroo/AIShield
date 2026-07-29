# AIShield 작업 인수인계

마지막 갱신일: 2026-07-28

## 현재 브랜치와 범위

- 작업 브랜치: `feat/clean-baseline`
- 안정 기준: reproducible clean baseline + bounded FGSM/BIM/PGD + functional dashboard
- Registry/run index: API process memory
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
- bounded FGSM/BIM/PGD, paired metrics, L∞ verification, gradient warning
- dataset/model/baseline/attack/artifact를 조작하는 React dashboard
- 실제 API run을 사용한 README screenshots와 screenshot automation

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

Docker CPU smoke는 dashboard, API, `/api` proxy health를 확인합니다. Zero-download product
smoke는 Dashboard의 `Launch zero-download demo`로 dataset → model → baseline → FGSM을
실행합니다.

## 중요한 설계 결정

- `robust_accuracy`는 adversarial input 전체 sample population의 accuracy입니다.
- `attack_success_rate` 분모는 clean-correct sample입니다. Raw counts도 함께 보존합니다.
- FGSM은 one step/no random start/step=epsilon 계약을 강제합니다.
- BIM은 iterative FGSM이며 random start를 거부합니다.
- PGD default는 step=`epsilon/4`, 10 iterations, random start입니다.
- 모든 attack input은 finite `[0,1]` tensor여야 하며 projection 후 observed L∞를 검사합니다.
- Flat gradient는 성공이 아니라 masking warning입니다.
- Synthetic dataset과 untrained SmallCNN 결과는 security benchmark가 아닙니다.
- PostgreSQL/Redis는 아직 persistence/worker 구현이 아니며 문서에서도 future boundary로
  표시합니다.

## 다음 작업 우선순위

1. PostgreSQL run/registry persistence와 restart recovery
2. Redis-backed resource-isolated evaluation worker
3. BIM/DeepFool/CW/AutoAttack 및 strength curve
4. transfer/adaptive attack과 defense evaluation
5. raw metric을 유지하는 versioned robustness score

세부 범위는 `docs/roadmap.md`를 기준으로 합니다. 새 기능은 numerical unit test, API
contract test, strict typing, README/API 문서 갱신을 함께 완료해야 합니다.
