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
