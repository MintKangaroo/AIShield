# Roadmap

AIShield는 headline score보다 검증 가능한 연구 근거를 우선합니다. 각 milestone은 strict
contract, numerical test, API test, documentation을 함께 완료해야 합니다.

## 완료

1. **Foundation** — FastAPI/React/Compose, versioned schema, CI, security/reproducibility policy.
2. **Registry** — Signal-10/MNIST/CIFAR-10, SmallCNN/torchvision, safe checkpoint, content hashes.
3. **Clean baseline** — accuracy, loss, confusion matrix, per-class metric, latency, JSON/PNG
   artifacts, same-seed rerun verification.
4. **FGSM** — input-range validation, L∞ projection, paired clean/robust metric, gradient health.
5. **PGD** — validated epsilon/step/iterations, random start, iterative projection, raw counts.
6. **Research dashboard MVP** — guided registry, baseline/attack execution, run inspection,
   confusion matrix, reproducibility verification, artifact downloads, responsive layout.

## 다음

7. **Additional attacks** *(in progress)*
   - ✅ BIM (iterative FGSM without random start)
   - ✅ DeepFool (bounded L2 steps)
   - ✅ Carlini–Wagner (bounded L2 optimization)
   - ✅ AutoAttack-style deterministic FGSM/BIM/PGD ensemble adapter
   - ✅ deterministic epsilon strength-curve endpoint
   - ✅ APGD/FAB/Square bounded compatibility adapters (reference parity warning)
   - ✅ epsilon strength curves and bounded multiple restarts
   - algorithm별 independent numerical fixtures
   - ✅ query-only black-box attack against an authorized remote endpoint (real
     deployed models, no weights) — allowlist + per-request confirmation gated

8. **Defense evaluation** *(in progress)*
   - ✅ bit-depth preprocessing defense baseline with before/after/adaptive metrics
   - ✅ adversarial training and TRADES checkpoint adapters with hashed evidence
   - ✅ surrogate-to-target transfer attack evidence
   - ✅ defense-aware adaptive reevaluation (bit-depth)
   - iterative-vs-single-step and black-box-vs-white-box masking diagnostics

9. **Persistence and isolation** *(in progress)*
   - ✅ append-only JSON metadata journal and flush boundary
   - ✅ journal read/audit API
   - ✅ bounded in-process worker queue and job status API
   - ✅ journal replay restart recovery with content-hash verification
   - ✅ bounded queue backlog, retention, cancellation, and job journaling
   - ✅ process-wide concurrent-run limit with 429 back-pressure
   - ✅ PostgreSQL registry/run metadata (opt-in backend behind one shared contract)
   - ✅ readiness endpoint that checks the configured store instead of guessing
   - ✅ Redis-backed job queue and out-of-process evaluation worker
   - ✅ CPU/CUDA worker images pinned by digest, with the deployed digest recorded
     in every evidence envelope
   - ✅ artifact garbage collection: orphan sweep with a dry-run preview
   - ✅ worker dead-letter handling: bounded retries, then a FAILED record kept for inspection

10. **Transparent robustness score**
    - ✅ versioned public formula
    - ✅ raw input metrics retained alongside every component
    - ✅ missing/invalid attack evidence cannot silently improve the score

11. **Dashboard expansion** *(in progress)*
    - ✅ strength curves
    - ✅ defense before/after/adaptive view와 gradient masking 경고
    - ✅ surrogate-to-target transfer view
    - ✅ background job/training 상태 추적과 진행 중 자동 갱신
    - ✅ robustness score 집계 UI
    - ✅ append-only journal 감사 view
    - ✅ portable experiment export/import
    - ✅ run-to-run comparison that blocks uncontrolled comparisons and flags
      misleading deltas
    - ✅ remote black-box attack dashboard surface
    - sample triplets

12. **Access control** *(in progress)*
    - ✅ optional API key over the whole registry surface, off by default
    - ✅ dashboard prompts for a key instead of reporting an outage
    - per-key scopes and audit of who ran what

13. **Separate LLM security design** *(in progress)*
    - ✅ image engine과 분리된 threat/metric contract (`aishield.llm`)
    - ✅ prompt/response privacy controls (hash-by-default, text opt-in)
    - ✅ authorization: allowlist + per-request confirmation before any probe
    - ✅ prompt-injection / system-prompt-leak probes with detectors, query-only
    - ✅ jailbreak-framing category (roleplay/hypothetical/developer/prefix) against a
      benign planted token
    - ✅ obfuscation-aware detectors (hyphen/space/reverse/base64/base32/hex)
    - ✅ dashboard surface
    - ✅ conversation-level / multi-turn probes with a refusal detector
    - broader probe corpus and per-turn evidence

추가 attack이나 defense 하나의 결과만으로 보편적인 강건성을 주장하지 않습니다. 다음
milestone으로 이동하기 전에 이전 단계의 raw metric과 quality gate가 유지되어야 합니다.

---

## 남은 작업 (deferred backlog — 2026-09-05 기준)

핵심 9개 영역은 모두 shipped·main 반영·라이브 동작 확인 완료. 아래는 *깨진 것이
아니라 더 하면 좋은 것들*로, 우선순위 순.

1. **artifact_root 배포 문서화** *(quick win)* — 기본 `artifact_root=artifacts`가
   쓰기 불가한 위치일 때 baseline append가 500이 난다. `AISHIELD_ARTIFACT_ROOT`를
   쓰기 가능한 경로로 지정하도록 README/배포 가이드에 명시.
2. **LLM probe 코퍼스 확장 + per-turn evidence** — probe 다양성을 넓히고 멀티턴
   대화의 턴별 증거를 남긴다. probe는 계속 benign/diagnostic 유지 (성공해도
   무해한 planted token만 노출).
3. **PostgreSQL 경로 커버리지** — 현재 51%. 라이브 PostgreSQL 대상 통합 테스트를
   CI(서비스 컨테이너)로 돌려 실경로를 검증.
4. **GPU 실행 end-to-end 검증** — CUDA 워커 이미지는 빌드·핀 검증까지만 됨. 실제
   GPU에서의 학습/공격 실행은 미검증 (개발 머신에 GPU 없음). GPU 러너 확보 시 확인.
5. **메타데이터 레코드 집합 상한** — append-only 저널은 설계상 무한 증가. 레코드
   자체의 bounding/compaction은 별도 backend 과제 (GC는 orphan artifact만 회수).
6. **per-key scope + 감사** — 누가 무엇을 실행했는지 API 키 스코프·감사 로그.
7. **decision-only HopSkipJump 정교화** — 현재 boundary attack은 label-only 기본형.
