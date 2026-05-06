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


def _erfinv(x: float) -> float:
    """Inverse error function via Winitzki approximation + Newton-Raphson refinement."""
    if abs(x) >= 1:
        return math.copysign(float('inf'), x)
    if x == 0:
        return 0.0
    a = 0.147
    ln1mx2 = math.log(1 - x * x)
    t = 2 / (math.pi * a) + ln1mx2 / 2
    approx = math.copysign(math.sqrt(math.sqrt(t * t - ln1mx2 / a) - t), x)
    for _ in range(2):
        approx -= (math.erf(approx) - x) * math.exp(approx * approx) * math.sqrt(math.pi) / 2
    return approx


def confidence_pct_to_z(pct: float) -> float:
    """Convert a confidence percentage (0–100) to its z-score threshold.

    Inverse of z_to_confidence. Used to convert a user-supplied min confidence %
    into a z-score for SQL filtering against the stored confidence_score column.
    """
    if pct <= 0:
        return 0.0
    if pct >= 100:
        return float('inf')
    return math.sqrt(2) * _erfinv(pct / 100)
