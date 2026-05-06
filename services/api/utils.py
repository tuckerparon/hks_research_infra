# ── HUMAN REVIEW ──────────────────────────────────────────
# Reviewer:
# Date:
# Changes from AI draft:
# Notes:
# ──────────────────────────────────────────────────────────

import math


def _norm_cdf(z: float) -> float:
    """Normal CDF using Python's built-in math.erf — no scipy needed."""
    return (1 + math.erf(z / math.sqrt(2))) / 2


def z_to_confidence(z: float) -> float:
    """Convert a z-score to a confidence percentage.

    Uses the two-tailed normal CDF: the probability that a reading this many
    standard deviations from the mean is genuinely anomalous rather than noise.

    Examples:
        z=2.0  → ~95.45%
        z=3.0  → ~99.73%
        z=4.0  → ~99.994%
    """
    return round((1 - 2 * (1 - _norm_cdf(abs(z)))) * 100, 2)
