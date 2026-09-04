"""Contract for the score-based black-box attack.

The attack must reduce accuracy using only oracle scores, never exceed the
L-infinity bound, count every query, and behave deterministically for a seed.
"""

import torch

from aishield.attacks.blackbox import evaluate_black_box, run_square_attack


class QuadrantOracle:
    """An above-chance model: the label is the brightest 4x4 quadrant."""

    def __init__(self, scale: float = 5.0) -> None:
        self.scale = scale

    def __call__(self, images: torch.Tensor) -> torch.Tensor:
        return (
            torch.stack(
                [
                    images[:, :, :4, :4].mean((1, 2, 3)),
                    images[:, :, :4, 4:].mean((1, 2, 3)),
                    images[:, :, 4:, :4].mean((1, 2, 3)),
                    images[:, :, 4:, 4:].mean((1, 2, 3)),
                ],
                dim=1,
            )
            * self.scale
        )


def _quadrant_batch(count: int, signal: float, seed: int) -> tuple[torch.Tensor, torch.Tensor]:
    generator = torch.Generator().manual_seed(seed)
    images = torch.rand(count, 1, 8, 8, generator=generator) * 0.3
    labels = torch.randint(0, 4, (count,), generator=generator)
    for index, label in enumerate(labels):
        row = 0 if label < 2 else 4
        column = 0 if label % 2 == 0 else 4
        images[index, :, row : row + 4, column : column + 4] += signal
    return images.clamp(0, 1), labels


def test_the_attack_leaves_a_strong_model_correct_within_a_tiny_bound() -> None:
    oracle = QuadrantOracle()
    images, labels = _quadrant_batch(16, signal=0.6, seed=1)

    adversarial, queries = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.05,
        max_queries=100,
        num_classes=4,
        generator=torch.Generator().manual_seed(3),
    )

    assert float((adversarial - images).abs().amax()) <= 0.05 + 1e-6
    assert queries > 0
    # A 0.05 budget cannot overcome a 0.6 signal, so predictions should hold.
    assert bool((oracle(adversarial).argmax(1) == labels).all())


def test_the_attack_flips_predictions_when_the_budget_allows() -> None:
    oracle = QuadrantOracle()
    images, labels = _quadrant_batch(24, signal=0.35, seed=2)
    assert bool((oracle(images).argmax(1) == labels).all())  # all clean-correct

    adversarial, _ = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.4,
        max_queries=300,
        num_classes=4,
        generator=torch.Generator().manual_seed(5),
    )

    flipped = int((oracle(adversarial).argmax(1) != labels).sum())
    assert flipped == 24
    assert float((adversarial - images).abs().amax()) <= 0.4 + 1e-6


def test_the_attack_is_deterministic_for_a_seed() -> None:
    oracle = QuadrantOracle()
    images, labels = _quadrant_batch(12, signal=0.35, seed=4)

    first, first_queries = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.3,
        max_queries=150,
        num_classes=4,
        generator=torch.Generator().manual_seed(9),
    )
    second, second_queries = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.3,
        max_queries=150,
        num_classes=4,
        generator=torch.Generator().manual_seed(9),
    )

    assert torch.equal(first, second)
    assert first_queries == second_queries


def test_a_successful_attack_spends_fewer_queries() -> None:
    """Images that succeed drop out, so an easier bound costs fewer queries."""

    oracle = QuadrantOracle()
    images, labels = _quadrant_batch(24, signal=0.35, seed=2)

    _, hard = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.3,
        max_queries=400,
        num_classes=4,
        generator=torch.Generator().manual_seed(1),
    )
    _, easy = run_square_attack(
        oracle,
        images,
        labels,
        epsilon=0.5,
        max_queries=400,
        num_classes=4,
        generator=torch.Generator().manual_seed(1),
    )

    assert easy < hard


def test_evaluate_reports_paired_predictions_and_queries() -> None:
    oracle = QuadrantOracle()
    images, labels = _quadrant_batch(20, signal=0.35, seed=6)

    result = evaluate_black_box(
        oracle, [(images, labels)], epsilon=0.4, max_queries=200, num_classes=4, seed=7
    )

    assert len(result.clean_predictions) == 20
    assert len(result.adversarial_predictions) == 20
    assert result.targets == [int(v) for v in labels.tolist()]
    assert result.total_queries > 20  # clean pass plus search
    assert result.maximum_observed_linf <= 0.4 + 1e-6


def test_bad_inputs_and_budgets_are_rejected() -> None:
    oracle = QuadrantOracle()
    labels = torch.zeros(2, dtype=torch.long)
    generator = torch.Generator().manual_seed(0)

    for bad in (
        torch.rand(2, 8, 8),  # not 4-D
        torch.full((2, 1, 8, 8), 2.0),  # outside [0, 1]
        torch.full((2, 1, 8, 8), float("nan")),  # non-finite
    ):
        try:
            run_square_attack(
                oracle,
                bad,
                labels,
                epsilon=0.1,
                max_queries=10,
                num_classes=4,
                generator=generator,
            )
        except ValueError:
            continue
        raise AssertionError("expected the attack to reject a malformed input batch")

    good = torch.rand(2, 1, 8, 8, generator=generator)
    try:
        run_square_attack(
            oracle,
            good,
            labels,
            epsilon=0.1,
            max_queries=0,
            num_classes=4,
            generator=generator,
        )
    except ValueError:
        return
    raise AssertionError("expected a zero query budget to be rejected")
