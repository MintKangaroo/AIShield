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

8. **Defense evaluation** *(in progress)*
   - ✅ bit-depth preprocessing defense baseline with before/after/adaptive metrics
   - ✅ adversarial training and TRADES checkpoint adapters with hashed evidence
   - ✅ surrogate-to-target transfer attack evidence
   - ✅ defense-aware adaptive reevaluation (bit-depth)
   - iterative-vs-single-step and black-box-vs-white-box masking diagnostics

9. **Persistence and isolation**
   - ✅ append-only JSON metadata journal and flush boundary
   - PostgreSQL registry/run metadata
   - Redis-backed job queue and resource-bounded worker
   - process restart recovery and artifact garbage-collection policy
   - CPU/CUDA worker image digest pinning

10. **Transparent robustness score**
    - ✅ versioned public formula
    - ✅ raw input metrics retained alongside every component
    - ✅ missing/invalid attack evidence cannot silently improve the score

11. **Dashboard expansion**
    - strength curves, run-to-run comparison, sample triplets
    - defense before/after/adaptive view
    - portable experiment export/import

12. **Separate LLM security design**
    - image engine과 분리된 threat/metric contract
    - prompt/response privacy controls
    - 실행 기능 전에 authorization과 benchmark policy 확정

추가 attack이나 defense 하나의 결과만으로 보편적인 강건성을 주장하지 않습니다. 다음
milestone으로 이동하기 전에 이전 단계의 raw metric과 quality gate가 유지되어야 합니다.
