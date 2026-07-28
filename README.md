# AIShield

AIShield는 머신러닝 시스템의 보안을 안전하고 재현 가능한 방식으로 평가하기 위한 연구
플랫폼입니다. 첫 번째 릴리스는 PyTorch 이미지 분류 모델의 적대적 공격 및 방어 평가에
집중합니다.

> 현재 단계: 2단계 모델·데이터셋 레지스트리 완료. 공격 실행과 상세 clean baseline은
> 아직 구현되지 않았습니다.

## 포함된 기능

- 버전화된 경로, OpenAPI, liveness 응답을 제공하는 타입 안전 FastAPI 서비스
- API 연결 상태를 표시하는 React 및 TypeScript 기반 연구 대시보드 골격
- 엄격하게 검증되는 버전화된 실험 결과 계약과 자동 생성 JSON Schema
- PostgreSQL 및 Redis 개발 서비스
- Docker Compose 기반 CPU 데모와 선택적 NVIDIA GPU 실행 환경 점검
- pytest, Ruff, mypy, 프런트엔드 타입 검사 및 GitHub Actions
- 재현성, 아키텍처, 안전 정책 및 결과 스키마 문서
- MNIST 및 CIFAR-10의 승인된 torchvision dataset adapter
- seed가 고정되는 소형 CNN과 torchvision pretrained model adapter
- 데이터셋 manifest, 모델 state 및 실제 model artifact의 SHA-256 기록
- 모델·데이터셋 로드, 조회 및 제한된 기본 평가 API

현재 단계에는 모델 학습, 공격, 방어, 상세 baseline artifact 또는 결과 영속화 기능이
포함되지 않습니다. 레지스트리는 API 프로세스 메모리에 유지되며, 모델 artifact와 dataset
파일만 Docker volume 또는 설정된 로컬 경로에 저장됩니다. LLM 보안, 개인정보 공격, 모델
추출은 첫 번째 릴리스의 실행 엔진 범위에서 제외됩니다.

현재 구현 상태와 다음 세션의 재개 절차는 [작업 인수인계](HANDOFF.md)에 계속
갱신합니다.

## 빠른 시작: Docker CPU 데모

Docker Engine과 Docker Compose 플러그인이 필요합니다.

```bash
cp .env.example .env
docker compose up --build --wait
```

대시보드는 <http://localhost:3000>, API 문서는 <http://localhost:8000/api/docs>에서
확인할 수 있습니다. 다음 명령으로 API 상태를 직접 점검할 수도 있습니다.

```bash
curl http://localhost:8000/api/v1/health/live
```

호스트 포트가 이미 사용 중이면 `.env`의 `AISHIELD_DASHBOARD_PORT`와
`AISHIELD_API_PORT`를 다른 값으로 변경할 수 있습니다. 컨테이너 내부 포트와 서비스 간
통신은 그대로 유지됩니다.

데이터베이스 볼륨을 보존하면서 서비스를 종료하려면 다음 명령을 실행합니다.

```bash
docker compose down
```

CPU가 기본 연산 장치로 설정됩니다. 선택적 `gpu` profile은 Docker가 NVIDIA GPU에
접근할 수 있는지만 점검하며, 현재 단계에서는 공격 worker를 실행하지 않습니다.

```bash
docker compose --profile gpu run --rm gpu-check
```

GPU 점검에는 NVIDIA Container Toolkit이 필요합니다. API 이미지는 재현 가능한 CPU
실행을 위해 PyTorch `2.13.0` 및 torchvision `0.28.0` CPU wheel을 사용합니다.

공개 dataset과 pretrained weight 다운로드는 기본적으로 차단됩니다. MNIST, CIFAR-10 또는
공식 torchvision weight를 내려받도록 명시적으로 승인하려면 `.env`에서 다음 값을 변경한
뒤 서비스를 다시 시작합니다.

```dotenv
AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true
```

승인은 내장 adapter의 고정된 공식 출처에만 적용되며 임의 URL은 허용하지 않습니다.

## 로컬 개발 환경

Python 3.11 또는 3.12와 Node.js 22를 지원합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install torch==2.13.0 torchvision==0.28.0 \
  --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,ml]"
make check

npm --prefix web ci
npm --prefix web run dev
```

다른 터미널에서 API를 실행합니다.

```bash
source .venv/bin/activate
aishield-api
```

Vite 개발 서버는 `/api` 요청을 `localhost:8000`으로 전달합니다.

## 브랜치 운영 규칙

| 브랜치 | 용도 |
| --- | --- |
| `main` | 항상 실행 가능한 검증된 안정 버전 |
| `develop` | 다음 릴리스 기능을 모으는 통합 브랜치 |
| `feat/<기능명>` | `develop`에서 분기하는 기능별 작업 |
| `fix/<문제명>` | 버그 수정 작업 |
| `docs/<문서명>` | 문서만 변경하는 작업 |

기능·수정·문서 브랜치는 품질 검사를 통과한 후 `develop`에 병합합니다. 전체 CPU 데모까지
검증한 릴리스만 `develop`에서 `main`으로 병합하며, 완료되지 않은 기능을 `main`에 직접
커밋하지 않습니다.

## 레지스트리 API 예시

다운로드가 승인된 환경에서 MNIST test split을 로드합니다.

```bash
curl -X POST http://localhost:8000/api/v1/registry/datasets \
  -H 'Content-Type: application/json' \
  -d '{"name":"mnist","split":"test","download":true}'
```

응답의 dataset `id`를 사용해 동일한 입력 형태와 class 수를 갖는 seed 고정 CNN을
생성합니다.

```bash
curl -X POST http://localhost:8000/api/v1/registry/models/small-cnn \
  -H 'Content-Type: application/json' \
  -d '{"dataset_id":"<dataset-id>","seed":1729}'
```

기본 평가는 `POST /api/v1/registry/evaluations`에서 실행합니다. 이 단계의 응답은
`clean_accuracy`와 `mean_loss`를 제공하며, 공격이 아직 실행되지 않았음을 분명히 하기 위해
`robust_accuracy`는 `null`, 상태는 `not_evaluated`로 반환합니다. 전체 endpoint와 요청
형식은 <http://localhost:8000/api/docs> 또는 [API 문서](docs/api.md)를 참고하십시오.

## 실험 결과 계약

[`schemas/experiment-result.schema.json`](schemas/experiment-result.schema.json)은
`src/aishield/schemas/experiment.py`의 Pydantic 계약에서 생성됩니다. 계약을 의도적으로
변경한 경우 다음 명령으로 스키마를 다시 생성하고 일치 여부를 확인합니다.

```bash
aishield-export-schema schemas/experiment-result.schema.json
make schema-check
```

성공한 공격 실행 결과는 clean accuracy, robust accuracy, 공격 성공률 및 평가 샘플 수가
모두 기록되지 않으면 직렬화할 수 없습니다. 향후 종합 Robustness Score를 도입하더라도
원시 metric은 항상 함께 보존합니다. 자세한 내용은
[실험 결과 스키마 문서](docs/experiment-schema.md)를 참고하십시오.

## 프로젝트 구조

```text
src/aishield/api/       FastAPI 애플리케이션 및 버전화된 API 경로
src/aishield/core/      실행 환경 설정
src/aishield/registry/  Dataset/model adapter, checksum 및 기본 평가
src/aishield/schemas/   안정적인 실험 결과 교환 계약
web/                    React 및 TypeScript 대시보드
docker/                 API 및 대시보드 컨테이너 이미지
schemas/                생성된 버전화 JSON Schema
tests/                  백엔드 API 및 계약 테스트
docs/                   아키텍처와 연구 정책 문서
```

## 재현성 및 연구 정책

실험에는 로컬 데이터 또는 명시적으로 승인된 공개 데이터셋만 사용할 수 있습니다. 모든
결과에는 데이터셋 버전과 manifest hash, 모델 artifact hash, seed, 공격 파라미터 및 환경
버전을 기록해야 합니다. 방어 기법은 한 번의 공격 실패만으로 유효하다고 판단하지 않으며,
transfer attack과 adaptive attack을 통해 gradient masking 가능성을 점검합니다.

평가 기능을 추가하기 전에 [재현성 정책](docs/reproducibility.md)과
[위협 모델](docs/threat-model.md)을 확인하십시오.

품질 기준은 [기여 가이드](CONTRIBUTING.md), 비공개 취약점 신고 절차는
[보안 정책](SECURITY.md)을 참고하십시오. AIShield는 MIT License로 배포됩니다.
