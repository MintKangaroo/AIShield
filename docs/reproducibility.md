# Reproducibility Policy

An AIShield result is reproducible only when another authorized researcher can reconstruct the
inputs, environment, algorithm settings, and metric procedure. A matching headline number alone is
not sufficient.

## Required record

Every experiment export must include:

- a stable dataset name and version, exact split, sample count, approval provenance, and manifest
  SHA-256;
- a stable model name and version, architecture, framework, artifact URI, and artifact SHA-256;
- the experiment seed and the seed for each attack or defense run;
- each attack/defense implementation identifier and complete parameter mapping;
- Python, PyTorch, torchvision, and relevant dependency versions, OS/platform, CPU or GPU device,
  Git commit, and container digest when available;
- content hashes and media types for generated artifacts;
- raw metrics, evaluated sample counts, and any documented aggregation formula.

Paths and URIs may identify local objects but must not embed credentials.

## Determinism

Evaluation code will seed Python, NumPy, PyTorch CPU, and all CUDA devices from the recorded seed.
DataLoader generators and workers receive derived, recorded seeds. Deterministic PyTorch algorithms
are enabled where supported, benchmark-based cuDNN selection is disabled, and known nondeterministic
operations must fail or be called out in the result.

GPU kernels and dependency changes can still cause numerical differences. Same-environment reruns
must match discrete predictions and artifact hashes where deterministic operations are available;
floating metrics use an explicitly documented tolerance. A rerun never silently overwrites the
original result—it creates a linked comparison record.

## Metric integrity

- Completed attack evaluations always report clean accuracy, robust accuracy, attack success rate,
  and evaluated sample count together.
- Robust accuracy uses the same eligible sample population and preprocessing contract as clean
  accuracy; any alternate denominator is named separately.
- A robustness score never replaces raw metrics and always names its formula version, components,
  normalization, and weights.
- Sample artifacts include original input, visible perturbation rendering, and adversarial input when
  an attack creates them.

## Defense claims and gradient masking

A defense is not considered robust because one white-box gradient attack fails. Evaluation must
check attack-strength monotonicity, multiple random restarts, black-box transferability, iterative
attacks stronger than FGSM, and an adaptive attack aware of preprocessing or defense behavior.
Suspiciously low gradients, iterative attacks underperforming single-step attacks, or black-box
attacks outperforming white-box attacks are recorded as warning signals rather than positive scores.

## Data authorization

Only operator-provided local datasets or explicitly approved public datasets may be evaluated.
Dataset adapters must not accept arbitrary download URLs. Approved adapters will pin canonical
sources and verify a versioned manifest. Raw data, adversarial samples, and model weights remain out
of Git.
