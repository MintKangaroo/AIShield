"""Reproducible clean and adversarial model evaluation."""

from aishield.evaluation.contracts import BaselineRunRecord, BaselineVerification
from aishield.evaluation.runner import run_clean_baseline, verify_baseline_rerun

__all__ = [
    "BaselineRunRecord",
    "BaselineVerification",
    "run_clean_baseline",
    "verify_baseline_rerun",
]
