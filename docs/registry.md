# Reproducible Registry

Stage 2 provides process-local runtime handles and immutable metadata for datasets and models. It
does not yet persist registry rows in PostgreSQL.

## Dataset adapters

Only `mnist` and `cifar10` are accepted. Each adapter fixes its canonical public source, dataset
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

## Basic evaluation boundary

Stage 2 evaluation exists to verify that a loaded model and dataset work together. It checks channel
and class compatibility, uses deterministic ordering and an optional sample cap, and returns clean
accuracy plus cross-entropy loss. `robust_accuracy` remains explicitly `null/not_evaluated`.

Confusion matrices, per-class precision/recall, inference latency, artifacts, and same-seed rerun
comparisons are reserved for the stage 3 clean-baseline evaluator.
