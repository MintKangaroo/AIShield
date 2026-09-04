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
    REG --> DEFENSE["Bit-depth defense<br/>before / after / adaptive"]
    DEFENSE --> EVIDENCE

PostgreSQL ─ optional shared metadata store (AISHIELD_METADATA_BACKEND=postgresql)
Redis      ─ isolated worker boundary (future)
```

PostgreSQL은 이제 선택 가능한 metadata backend입니다(`AISHIELD_METADATA_BACKEND=postgresql`).
기본값 `journal`은 서버 없이 단일 프로세스로 동작합니다. Redis는 `AISHIELD_JOB_BACKEND=redis`일 때 job broker로
사용합니다. 이때 API는 job을 수락만 하고, 별도 `aishield-worker` 프로세스가 실행합니다.

`/health/live`는 여전히 process liveness만 보고합니다. 실제 dependency 확인은
`/health/ready`가 담당하며, 설정된 store에 접근해 보고 실패하면 503을 반환합니다.

## Package boundaries

- `aishield.api` — HTTP transport, strict request model, error translation, OpenAPI,
  and the optional API key applied at the registry router.
- `aishield.core` — validated immutable runtime settings.
- `aishield.registry` — adapter allowlist, runtime handle, safe checkpoint, hash, orchestration.
- `aishield.evaluation` — clean metric, latency, environment capture, artifact rendering,
  exact-config verification.
- `aishield.attacks` — framework-independent attack contract와 bounded FGSM/BIM/PGD/DeepFool/CW/AutoAttack runner,
  그리고 가중치 없이 score만으로 배포 모델을 공격하는 query-only black-box(Square) + 원격 HTTP 클라이언트.
- `aishield.schemas` — portable versioned experiment exchange contract.
- `aishield.llm` — separate LLM red-team track (prompt-injection probes, detectors,
  remote chat client); its own threat/metric contract, never mixed with the image engine.
- `aishield.jobs` — job status contract, serializable task descriptors, and the
  in-process and Redis backends behind one protocol.
- `aishield.registry.store` — metadata persistence protocol shared by the journal and
  PostgreSQL backends; runtime handles never cross it.
- `aishield.cli` — headless experiment runner producing the exchange envelope.

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

Registry metadata와 run record는 memory에 있지만, 모든 record는 append-only journal에도
기록됩니다. Process가 시작되면 journal을 재생해 index를 복구하므로 재등록이 필요하지
않습니다. Dataset/model/baseline 파일은 local directory 또는 Docker volume에 남습니다.

### Metadata replay

```text
configured metadata store (journal file 또는 PostgreSQL table)
  -> run evidence 복구 (항상)
  -> dataset/model handle 복구 (기록된 content hash가 디스크와 일치할 때만)
  -> 기록된 model identity(source/version/UUID) 유지
  -> background job은 복구하지 않음 (죽은 프로세스의 queued job은 실행된 적이 없음)
  -> 손상된 entry는 skip 사유와 함께 보고, API 기동은 실패하지 않음
```

### Worker isolation

```text
API process                     shared boundary            worker process
  accept job  ── serialized task ──> Redis list  ──BLPOP──> claim (atomic)
                                                            replay metadata
                                                            verify content hash
  read status <── job records ───── Redis hash <──────────  run + record
  read evidence <── metadata store (PostgreSQL) <─────────  append evidence
```

Task는 closure가 아니라 직렬화 가능한 기술자입니다. Worker는 runtime handle을 넘겨받지
않고 공유 metadata에서 직접 복구하므로, 두 프로세스는 저장소와 broker 외에 아무것도
공유하지 않습니다.

### Execution slots

모든 heavy evaluation은 프로세스 전역 `BoundedSemaphore`를 통과합니다. 동기 API 요청은
slot이 없으면 즉시 429를 받고, background worker는 대기합니다. 이 경계가 없으면 여러 개의
전체 torch 평가가 한 장비에서 겹치며 latency 근거가 왜곡되고 메모리가 고갈됩니다.

### Observability

모든 로그는 JSON 한 줄이며 `request_id`(요청 단위), `run_kind`, `run_id`, `duration_ms`를
포함합니다. `X-Request-ID`를 보내면 그 값이 proxy 구간까지 그대로 전파됩니다.

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

CPU가 기본이며 Docker image는 PyTorch/torchvision CPU wheel을 pin합니다. 모든 base image는
tag가 아니라 digest로 고정합니다.

CUDA evaluation worker는 `gpu-worker` profile로 제공합니다. CPU 이미지와 같은 torch 버전을
CUDA wheel로 설치하므로 결과가 framework 버전 때문에 달라지지 않으며,
`AISHIELD_COMPUTE_DEVICE=cuda`는 CUDA를 쓸 수 없을 때 조용히 CPU로 내려가지 않고 기동에
실패합니다. Compose `gpu-check` profile은 NVIDIA Container Toolkit 접근만 확인합니다.

빌드 시 주입한 `AISHIELD_CONTAINER_IMAGE_DIGEST`는 모든 evidence envelope에 기록됩니다.
digest 형식이 아닌 값은 기록하지 않고 경고를 남깁니다.
