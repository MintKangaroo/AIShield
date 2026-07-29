# Architecture

## Release boundary

현재 release는 PyTorch 이미지 분류 모델의 재현 가능한 clean/FGSM/BIM/PGD/DeepFool/CW/AutoAttack-style 평가를 제공합니다.
LLM security, privacy inference, model extraction은 같은 metric contract에 섞지 않습니다.

```text
Browser
  └─> React Dashboard
        └─> nginx /api proxy
              └─> FastAPI
                    └─> RegistryService (process-local handles and run index)
                          ├─> Dataset adapters
                          ├─> Model adapters
                          ├─> Clean baseline engine ─> JSON / PNG artifacts
                          └─> FGSM / BIM / PGD / DeepFool / CW / AutoAttack engine ─> paired attack evidence

PostgreSQL ─ metadata persistence boundary (future)
Redis      ─ isolated worker boundary (future)
```

PostgreSQL과 Redis는 Compose에서 향후 service boundary를 고정하지만 현재 registry에서
사용하지 않습니다. 따라서 `/health/live`는 process liveness만 보고하며 dependency
readiness를 가장하지 않습니다.

## Package boundaries

- `aishield.api` — HTTP transport, strict request model, error translation, OpenAPI.
- `aishield.core` — validated immutable runtime settings.
- `aishield.registry` — adapter allowlist, runtime handle, safe checkpoint, hash, orchestration.
- `aishield.evaluation` — clean metric, latency, environment capture, artifact rendering,
  exact-config verification.
- `aishield.attacks` — framework-independent attack contract와 bounded FGSM/BIM/PGD/DeepFool/CW/AutoAttack runner.
- `aishield.schemas` — portable versioned experiment exchange contract.

Attack runner는 API에 의존하지 않습니다. Raw input tensor에 perturbation을 만들고
`ModelBundle.preprocess`를 통과한 model loss의 gradient를 사용합니다. 모든 adversarial
input은 raw domain `[0, 1]`로 clamp하고 projection 후 실제 L∞를 검증합니다.

## Identities and storage

Dataset identity:

```text
UUIDv5(name, adapter version, split, directory manifest SHA-256)
```

Model identity:

```text
UUIDv5(architecture, adapter version, classes/channels, canonical state SHA-256)
```

Artifact는 configured root 아래 파일이며 API record에 URI, media type, size, SHA-256을
보존합니다. Download endpoint는 run에 등록된 artifact인지, resolved path가 artifact root
아래인지, symlink가 아닌 regular file인지 다시 확인합니다.

Registry metadata와 run record는 현재 memory에 있으므로 process restart 후 재등록해야
합니다. Dataset/model/baseline 파일은 local directory 또는 Docker volume에 남습니다.

## Execution sequence

### Clean baseline

```text
compatibility check
  -> deterministic seed
  -> ordered DataLoader
  -> warm-up
  -> inference + latency
  -> accuracy/loss/matrix/class metrics
  -> environment snapshot
  -> atomic JSON and PNG
  -> immutable run record
```

### Attack

```text
compatibility and [0,1] validation
  -> paired clean prediction
  -> input gradient
  -> FGSM step, iterative BIM, randomized PGD, bounded L2 DeepFool/CW, or AutoAttack ensemble
  -> L∞ projection + [0,1] clamp
  -> numerical bound verification
  -> adversarial prediction
  -> clean/robust/ASR and fingerprints
  -> gradient-health warning
```

## Compute profiles

CPU가 기본이며 Docker image는 PyTorch/torchvision CPU wheel을 pin합니다. Compose
`gpu-check` profile은 NVIDIA Container Toolkit 접근만 확인합니다. CUDA evaluation
worker는 dependency/image digest, scheduling, resource isolation이 구현된 뒤 별도 profile로
추가합니다.
