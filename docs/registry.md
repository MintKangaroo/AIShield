# Reproducible Registry

The registry provides process-local runtime handles and immutable metadata for datasets, models,
baselines, and attack runs. It does not yet persist registry rows in PostgreSQL.

## Dataset adapters

`synthetic`, `mnist`, and `cifar10` are accepted. `synthetic` creates the deterministic Signal-10
workflow dataset locally and is marked `generated`; it is not a benchmark. Each public adapter fixes its canonical public source, dataset
version, class count, input shape, and `ToTensor` transform. The record includes the requested
`train` or `test` split, sample count, torchvision version, and a SHA-256 manifest over sorted local
paths, sizes, and file contents.

Downloads default to denied. `AISHIELD_ALLOW_PUBLIC_DOWNLOADS=true` authorizes only the built-in
torchvision sources; callers cannot supply a URL. Existing files can be loaded with `download=false`.

## Model adapters

`SmallCNN` supports one-channel MNIST and three-channel CIFAR-10 inputs through a shared adaptive
architecture. Its initialization is reproducible from the recorded seed. A checkpoint name, when
provided, must resolve below `AISHIELD_MODEL_ROOT`; loading uses `torch.load(..., weights_only=True)`
and requires a tensor-only state dictionary with an exact architecture match.

The torchvision adapter supports `resnet18`, `mobilenet_v3_small`, and `efficientnet_b0`. Untrained
models require no network. Official pretrained weights are available only when public downloads are
approved, and the exact weight enum plus its preprocessing transform is recorded.

Every loaded model has two integrity values:

- `state_dict_sha256` is a deterministic hash over sorted tensor names, dtypes, shapes, and bytes;
- `artifact.sha256` hashes the actual safely loadable `.pt` state-dict file.

The state fingerprint forms part of the deterministic model-version UUID. The artifact is stored by
content-derived filename when AIShield creates it.

## Seed policy

Seeds use the unsigned 32-bit range. AIShield seeds Python, NumPy, PyTorch CPU, and all available
CUDA devices, enables deterministic algorithms, disables cuDNN benchmarking, and records the seed
on both model and evaluation results. A CUDA request fails when CUDA is unavailable rather than
silently falling back to CPU.

## Evaluation boundary

The legacy compatibility endpoint checks channel/class alignment, deterministic ordering, optional
sample caps, clean accuracy, and loss. The full baseline adds confusion matrix, per-class metrics,
latency, environment evidence, artifacts, and exact-config reruns. The attack registry retains
bounded FGSM/BIM/PGD/DeepFool records with paired clean/robust metrics, raw attack counts, prediction
fingerprints, and gradient-health warnings.
