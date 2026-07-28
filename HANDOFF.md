# AIShield 작업 인수인계

마지막 갱신일: 2026-07-28

이 문서는 새 Codex 세션이나 다른 기여자가 현재 상태를 빠르게 확인하고, 완료된 작업을
되풀이하지 않은 채 다음 단계부터 이어가기 위한 기준 문서입니다.

## 저장소와 브랜치

- GitHub: <https://github.com/MintKangaroo/AIShield>
- `main`: 전체 검증을 통과한 실행 가능한 안정 버전
- `develop`: 다음 릴리스 통합 브랜치
- `feat/<기능명>`: `develop`에서 분기하는 기능 작업
- `fix/<문제명>`: 버그 수정
- `docs/<문서명>`: 문서 전용 변경

기능 브랜치는 해당 단계의 테스트를 통과한 뒤 `develop`에 통합한다. 1~10단계 전체 범위와
CPU Docker 데모가 검증되기 전에는 `develop`의 미완성 릴리스를 `main`에 합치지 않는다.

## 완료된 작업

### 1단계 — 플랫폼 초기화

커밋 메시지: `chore: initialize AIShield research platform`

- FastAPI, React/TypeScript, PostgreSQL, Redis, Docker Compose 골격
- CPU 기본 실행과 선택적 GPU profile
- pytest, Ruff, mypy, GitHub Actions
- 엄격한 실험 결과 Pydantic 계약과 JSON Schema
- 한국어 README, 재현성·아키텍처·API·로드맵 문서

### 2단계 — 모델·데이터셋 레지스트리

커밋 메시지: `feat(registry): add reproducible model and dataset registry`
GitHub 통합: PR `#1`, `develop` merge commit `35710c2`

- 승인된 MNIST/CIFAR-10 torchvision adapter
- seed 기반 `SmallCNN`과 allowlist 기반 torchvision model adapter
- dataset manifest, 모델 state dict, artifact SHA-256
- dataset version/split, 모델·프레임워크 버전, seed, preprocessing 기록
- weights-only checkpoint 로드와 model root 경로 이탈 차단
- 모델·데이터셋 로드/조회 및 제한된 호환성 평가 API
- 공개 dataset/weight 다운로드 기본 차단
- 구성 가능한 Docker 호스트 포트

검증 결과:

- Python 3.11 및 3.12 정적 검사 통과
- 단위/API 테스트 39개 통과, line coverage 96.94%
- React TypeScript 검사와 production build 통과
- CPU/GPU Compose 설정 검증 통과
- CPU Compose 실제 기동, API·대시보드·nginx proxy health 검증 통과
- 실제 MNIST adapter와 torchvision pretrained weight 로드 검증 완료

### README와 작업 문서

- `docs/readme` 브랜치에서 한국어 README를 전체 재구성했다.
- 실제 CPU Compose 대시보드를 Playwright로 촬영한
  `docs/assets/dashboard-overview.png`를 README에 포함했다.
- README에 범위, 아키텍처, Docker/로컬 실행, 다운로드 승인, registry API 예시,
  재현성, 보안 경계, 품질 검사, 브랜치 운영과 전체 로드맵을 정리했다.

## 중요한 설계 결정

- 레지스트리는 현재 API 프로세스 메모리에만 존재한다. dataset과 model artifact 파일만
  Docker volume 또는 설정된 로컬 경로에 유지한다. PostgreSQL 영속화는 후속 작업이다.
- serialization에 따라 달라질 수 있는 artifact hash와 별도로, tensor 이름·dtype·shape·
  raw bytes를 사용하는 canonical state dict hash를 기록한다.
- dataset ID는 이름, 고정 adapter version, split, 로컬 manifest hash에서 결정한다.
- `AISHIELD_ALLOW_PUBLIC_DOWNLOADS=false`가 기본값이며, 허용하더라도 내장 adapter와 공식
  torchvision weight 외의 임의 URL은 받지 않는다.
- 2단계 평가는 model/dataset 호환성을 확인하는 최소 기능이다. confusion matrix,
  per-class metric, latency, baseline artifact, 재실행 비교는 3단계 책임이다.
- 공격을 실행하지 않은 결과는 `robust_accuracy: null`과
  `robust_accuracy_status: "not_evaluated"`로 명시한다.

## 다음 작업

다음 기능 브랜치는 `develop`에서 `feat/clean-baseline`으로 만든다.

3단계 완료 조건:

1. clean accuracy와 mean loss를 계산한다.
2. confusion matrix와 class별 precision/recall을 계산한다.
3. warm-up과 반복 측정을 구분한 inference latency를 기록한다.
4. machine-readable metric과 matplotlib 결과 이미지를 baseline artifact로 저장한다.
5. 모델 hash, dataset manifest, seed, 환경 snapshot을 결과에 포함한다.
6. 동일 seed 재실행 결과가 허용 오차 안에서 같은지 검증한다.
7. 공격 미실행 상태에서도 clean accuracy와 robust accuracy 미평가 상태를 함께 노출한다.
8. 독립 단위/API 테스트와 Docker CPU smoke test를 통과시킨다.

3단계 커밋 메시지:

```text
feat(evaluation): implement clean model baseline evaluation
```

이후에는 프로젝트 로드맵의 4~10단계를 같은 방식으로 진행하며, 각 단계가 끝날 때 이
문서의 완료 목록, 검증 결과, 다음 브랜치와 구체적인 작업 항목을 갱신한다.

## 재개 절차

```bash
git status --short --branch
git log --oneline --decorate -10
git branch -vv
docker compose config --quiet
docker compose --profile gpu config --quiet
```

Python 3.11 또는 3.12 환경에서:

```bash
python -m pip install torch==2.13.0 torchvision==0.28.0 \
  --index-url https://download.pytorch.org/whl/cpu
python -m pip install -e ".[dev,ml]"
make check
npm --prefix web ci
npm --prefix web run build
```

작업 디렉터리가 dirty이면 기존 변경을 사용자 작업으로 간주하고 덮어쓰지 않는다. 실제
dataset 다운로드는 느릴 수 있으므로 단위 테스트에서는 fixture adapter를 사용하되, 단계별
통합 시 승인된 공개 dataset으로 최소 한 번 smoke test를 수행한다.
