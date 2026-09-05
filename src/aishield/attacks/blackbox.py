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


#: Batch labels for images in [0, 1]; shape (N, C, H, W) -> (N,) class indices.
DecisionOracle = Callable[[Tensor], Tensor]


def run_decision_attack(
    oracle: DecisionOracle,
    inputs: Tensor,
    targets: Tensor,
    *,
    epsilon: float,
    max_queries: int,
    generator: torch.Generator,
) -> tuple[Tensor, int]:
    """Perturb a batch within an L-infinity ball using only predicted labels.

    This is the harder black-box setting: the model returns a class, not scores,
    so there is no margin to descend. The attack first random-searches the ball
    for any perturbation that flips the label, then binary-searches back toward
    the clean image to shrink the perturbation while staying misclassified — a
    bounded decision-based (boundary) attack, not a claim of parity with a named
    reference implementation.
    """

    if inputs.ndim != 4:
        raise ValueError("decision-based inputs must be a (N, C, H, W) batch")
    if not torch.isfinite(inputs).all():
        raise ValueError("decision-based inputs must be finite")
    if float(inputs.min()) < 0.0 or float(inputs.max()) > 1.0:
        raise ValueError("decision-based inputs must lie in [0, 1]")
    if max_queries < 1:
        raise ValueError("max_queries must be at least 1")

    spent = 0

    def labelled(images: Tensor) -> Tensor:
        nonlocal spent
        spent += int(images.shape[0])
        labels = oracle(images)
        if labels.shape != (images.shape[0],):
            raise ValueError("decision oracle must return one label per image")
        return labels

    best = inputs.clone()
    # A flip found so far for each image; drives the boundary refinement.
    flipped_input = inputs.clone()
    has_flip = torch.zeros(inputs.shape[0], dtype=torch.bool)

    # Phase 1: random search within the ball for an initial label flip.
    search_budget = max(1, max_queries // 2)
    steps = max(1, search_budget // max(1, inputs.shape[0]))
    _, channels, height, width = inputs.shape
    for _ in range(steps):
        if bool(has_flip.all()):
            break
        active = (~has_flip).nonzero(as_tuple=True)[0]
        # A single-sign perturbation over a random block shifts that region's mean,
        # which per-pixel random noise averages away. Still decision-only: we read
        # a label, not a score.
        delta = torch.zeros((active.shape[0], channels, height, width))
        for row in range(active.shape[0]):
            bh = int(torch.randint(1, height + 1, (1,), generator=generator).item())
            bw = int(torch.randint(1, width + 1, (1,), generator=generator).item())
            top = int(torch.randint(0, height - bh + 1, (1,), generator=generator).item())
            left = int(torch.randint(0, width - bw + 1, (1,), generator=generator).item())
            sign = torch.randint(0, 2, (channels, 1, 1), generator=generator).float() * 2.0 - 1.0
            delta[row, :, top : top + bh, left : left + bw] = sign * epsilon
        candidate = torch.clamp(inputs[active] + delta, 0.0, 1.0)
        labels = labelled(candidate)
        newly = labels != targets[active]
        idx = active[newly]
        flipped_input[idx] = candidate[newly]
        best[idx] = candidate[newly]
        has_flip[idx] = True

    # Phase 2: for images with a flip, binary-search toward the clean image so the
    # recorded perturbation reflects the boundary, not the initial random jump.
    low = torch.zeros(inputs.shape[0])  # 0 -> clean, 1 -> the found flip
    high = torch.ones(inputs.shape[0])
    refine_steps = max(0, (max_queries - spent) // max(1, int(has_flip.sum()) or 1))
    for _ in range(min(refine_steps, 20)):
        active = has_flip.nonzero(as_tuple=True)[0]
        if active.shape[0] == 0:
            break
        mid = ((low[active] + high[active]) / 2.0).view(-1, 1, 1, 1)
        candidate = torch.clamp(
            inputs[active] + mid * (flipped_input[active] - inputs[active]), 0.0, 1.0
        )
        labels = labelled(candidate)
        still = labels != targets[active]
        # Where it still flips, we can move closer to clean (lower high); otherwise
        # we went too far, so raise the floor.
        high_idx = active[still]
        low_idx = active[~still]
        high[high_idx] = (low[high_idx] + high[high_idx]) / 2.0
        best[high_idx] = candidate[still]
        low[low_idx] = (low[low_idx] + high[low_idx]) / 2.0

    linf = float((best - inputs).abs().amax().item()) if inputs.shape[0] else 0.0
    if linf > epsilon + BOUND_TOLERANCE:
        raise ValueError("decision-based perturbation exceeded the configured L-infinity bound")
    return best, spent


def evaluate_black_box_decision(
    oracle: DecisionOracle,
    batches: list[tuple[Tensor, Tensor]],
    *,
    epsilon: float,
    max_queries: int,
    seed: int,
) -> BlackBoxResult:
    """Run the decision-based attack over a dataset using only predicted labels."""

    generator = torch.Generator().manual_seed(seed)
    spent = 0

    def counted(images: Tensor) -> Tensor:
        nonlocal spent
        spent += int(images.shape[0])
        return oracle(images)

    targets_all: list[int] = []
    clean_all: list[int] = []
    adversarial_all: list[int] = []
    maximum_linf = 0.0

    for inputs, targets in batches:
        clean_labels = counted(inputs)
        adversarial, queries = run_decision_attack(
            oracle,
            inputs,
            targets,
            epsilon=epsilon,
            max_queries=max_queries,
            generator=generator,
        )
        spent += queries
        adversarial_labels = counted(adversarial)
        maximum_linf = max(maximum_linf, float((adversarial - inputs).abs().amax().item()))
        targets_all.extend(int(v) for v in targets.tolist())
        clean_all.extend(int(v) for v in clean_labels.tolist())
        adversarial_all.extend(int(v) for v in adversarial_labels.tolist())

    if not targets_all:
        raise ValueError("decision-based evaluation produced no samples")

    return BlackBoxResult(
        clean_predictions=clean_all,
        adversarial_predictions=adversarial_all,
        targets=targets_all,
        total_queries=spent,
        maximum_observed_linf=maximum_linf,
    )
