"""Score-based black-box attack over a query oracle.

This is what separates a red-team of a *deployed* model from a white-box lab run:
there is no gradient and no access to the weights, only the scores the model
returns for images we send it. The attack is a bounded Square-style random search
(Andriushchenko et al., 2020) — it perturbs a random square region per step, keeps
the change only when the class margin drops, and stops at a per-image query budget.

The oracle is any callable mapping a batch of ``[0, 1]`` images to class scores, so
the same attack runs against a local model wrapped as an oracle (tested offline) or
a remote HTTP endpoint (the real target). Nothing here knows which.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

import torch
from torch import Tensor

#: Batch scores for images in [0, 1]; shape (N, C, H, W) -> (N, num_classes).
ScoreOracle = Callable[[Tensor], Tensor]

BOUND_TOLERANCE = 1e-6


@dataclass(frozen=True)
class BlackBoxResult:
    """Outcome of one black-box evaluation, in the same shape the runner records."""

    clean_predictions: list[int]
    adversarial_predictions: list[int]
    targets: list[int]
    total_queries: int
    maximum_observed_linf: float


def prediction_fingerprint(targets: list[int], predictions: list[int]) -> str:
    """Order-sensitive digest of an evaluation, matching the white-box runner."""

    digest = hashlib.sha256(b"aishield-attack-predictions-v1\0")
    for target, prediction in zip(targets, predictions, strict=True):
        digest.update(target.to_bytes(8, "big", signed=True))
        digest.update(prediction.to_bytes(8, "big", signed=True))
    return digest.hexdigest()


def _margins(scores: Tensor, targets: Tensor) -> Tensor:
    """Untargeted margin: true-class score minus the best other class.

    Negative means the model already misclassifies the input, which is the
    black-box success signal since we never see a loss or a gradient.
    """

    true_score = scores.gather(1, targets.unsqueeze(1)).squeeze(1)
    masked = scores.clone()
    masked.scatter_(1, targets.unsqueeze(1), float("-inf"))
    best_other = masked.amax(dim=1)
    return true_score - best_other


def _square_side(height: int, width: int, step: int, total_steps: int) -> int:
    """Shrink the perturbed square over the budget, as Square Attack does."""

    fraction = 0.30 if step < total_steps * 0.1 else 0.15 if step < total_steps * 0.5 else 0.08
    side = max(1, int(round((fraction * height * width) ** 0.5)))
    return min(side, height, width)


class _Counter:
    def __init__(self) -> None:
        self.total = 0

    def wrap(self, oracle: ScoreOracle) -> ScoreOracle:
        def counted(images: Tensor) -> Tensor:
            self.total += int(images.shape[0])
            return oracle(images)

        return counted


def run_square_attack(
    oracle: ScoreOracle,
    inputs: Tensor,
    targets: Tensor,
    *,
    epsilon: float,
    max_queries: int,
    num_classes: int,
    generator: torch.Generator,
) -> tuple[Tensor, int]:
    """Perturb a batch within an L-infinity ball using only oracle scores.

    Returns the adversarial batch and the number of queries actually spent. Every
    query is counted, so a caller can report the real cost of the attack.
    """

    if inputs.ndim != 4:
        raise ValueError("black-box inputs must be a (N, C, H, W) batch")
    if not torch.isfinite(inputs).all():
        raise ValueError("black-box inputs must be finite")
    if float(inputs.min()) < 0.0 or float(inputs.max()) > 1.0:
        raise ValueError("black-box inputs must lie in [0, 1]")
    if max_queries < 1:
        raise ValueError("max_queries must be at least 1")

    counter = _Counter()
    counted = counter.wrap(oracle)
    batch, channels, height, width = inputs.shape

    def scored(images: Tensor) -> Tensor:
        scores = counted(images)
        if scores.shape != (images.shape[0], num_classes):
            raise ValueError("oracle returned scores of the wrong shape")
        if not torch.isfinite(scores).all():
            raise ValueError("oracle returned non-finite scores")
        return scores

    # Square's vertical-stripe initialisation: each column is pushed to a random
    # extreme of the L-infinity ball, then clamped back into the image range.
    stripes = torch.randint(0, 2, (batch, channels, 1, width), generator=generator).float()
    delta = (stripes * 2.0 - 1.0) * epsilon
    best = torch.clamp(inputs + delta, 0.0, 1.0)
    best_margins = _margins(scored(best), targets)
    succeeded = best_margins < 0

    # One query per image was already spent on the initialisation above.
    steps = max(1, max_queries - 1)
    for step in range(steps):
        if bool(succeeded.all()):
            break
        active = (~succeeded).nonzero(as_tuple=True)[0]
        candidate = best.clone()
        side = _square_side(height, width, step, steps)
        for index in active.tolist():
            top = int(torch.randint(0, height - side + 1, (1,), generator=generator).item())
            left = int(torch.randint(0, width - side + 1, (1,), generator=generator).item())
            sign = torch.randint(0, 2, (channels, 1, 1), generator=generator).float() * 2.0 - 1.0
            patch = inputs[index, :, top : top + side, left : left + side] + sign * epsilon
            candidate[index, :, top : top + side, left : left + side] = patch
        candidate = torch.clamp(candidate, 0.0, 1.0)

        margins = _margins(scored(candidate[active]), targets[active])
        improved = margins < best_margins[active]
        improved_index = active[improved]
        best[improved_index] = candidate[improved_index]
        best_margins[improved_index] = margins[improved]
        succeeded = best_margins < 0

    linf = float((best - inputs).abs().amax().item()) if batch else 0.0
    if linf > epsilon + BOUND_TOLERANCE:
        raise ValueError("black-box perturbation exceeded the configured L-infinity bound")
    return best, counter.total


def evaluate_black_box(
    oracle: ScoreOracle,
    batches: list[tuple[Tensor, Tensor]],
    *,
    epsilon: float,
    max_queries: int,
    num_classes: int,
    seed: int,
) -> BlackBoxResult:
    """Run the attack over a dataset and produce paired clean/adversarial evidence."""

    generator = torch.Generator().manual_seed(seed)
    counter = _Counter()
    counted = counter.wrap(oracle)

    targets_all: list[int] = []
    clean_all: list[int] = []
    adversarial_all: list[int] = []
    maximum_linf = 0.0

    for inputs, targets in batches:
        clean_scores = counted(inputs)
        clean_predictions = clean_scores.argmax(dim=1)
        adversarial, _ = run_square_attack(
            counted,
            inputs,
            targets,
            epsilon=epsilon,
            max_queries=max_queries,
            num_classes=num_classes,
            generator=generator,
        )
        adversarial_predictions = counted(adversarial).argmax(dim=1)
        maximum_linf = max(maximum_linf, float((adversarial - inputs).abs().amax().item()))
        targets_all.extend(int(v) for v in targets.tolist())
        clean_all.extend(int(v) for v in clean_predictions.tolist())
        adversarial_all.extend(int(v) for v in adversarial_predictions.tolist())

    if not targets_all:
        raise ValueError("black-box evaluation produced no samples")

    return BlackBoxResult(
        clean_predictions=clean_all,
        adversarial_predictions=adversarial_all,
        targets=targets_all,
        total_queries=counter.total,
        maximum_observed_linf=maximum_linf,
    )
