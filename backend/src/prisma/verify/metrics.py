"""Verification metrics per docs/EVALUATION_PROTOCOL.md.

Scores are implemented here with unit tests; running them on archived
forecasts is deliberately separate (and gated on archive maturity in the
protocol). Nothing in this module writes to results/.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def crps_ensemble(members: np.ndarray | list[float], observation: float) -> float:
    """Fair ensemble CRPS: mean |x_i - y| - 0.5 * mean |x_i - x_j|.

    The double sum runs over all ordered pairs (i, j) including i == j,
    which matches the standard fair CRPS estimator for a finite ensemble.
    """
    x = np.asarray(members, dtype=float)
    y = float(observation)
    if x.ndim != 1 or x.size == 0:
        raise ValueError("members must be a non-empty 1-D array")
    if not np.isfinite(y):
        raise ValueError("observation must be finite")

    term1 = float(np.mean(np.abs(x - y)))
    term2 = float(np.mean(np.abs(x[:, None] - x[None, :])))
    return term1 - 0.5 * term2


def crps_from_samples(samples: np.ndarray, observation: float) -> float:
    """CRPS from a flat sample vector (same estimator as crps_ensemble)."""
    return crps_ensemble(samples, observation)


def crpss(scores: np.ndarray, reference_scores: np.ndarray) -> float:
    """CRPSS = 1 - mean(CRPS) / mean(CRPS_reference). NaN if reference mean is 0."""
    scores = np.asarray(scores, dtype=float)
    reference = np.asarray(reference_scores, dtype=float)
    if scores.shape != reference.shape:
        raise ValueError("scores and reference_scores must have the same shape")
    ref_mean = float(np.mean(reference))
    if ref_mean == 0:
        return float("nan")
    return 1.0 - float(np.mean(scores)) / ref_mean


def brier_score(probability: float, event: bool | int | float) -> float:
    """Brier score for a single binary forecast: (p - o)^2."""
    p = float(probability)
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"probability must be in [0, 1], got {p}")
    o = float(bool(event))
    return (p - o) ** 2


def brier_skill_score(scores: np.ndarray, reference_scores: np.ndarray) -> float:
    """BSS = 1 - mean(BS) / mean(BS_reference). NaN if reference mean is 0."""
    scores = np.asarray(scores, dtype=float)
    reference = np.asarray(reference_scores, dtype=float)
    if scores.shape != reference.shape:
        raise ValueError("scores and reference_scores must have the same shape")
    ref_mean = float(np.mean(reference))
    if ref_mean == 0:
        return float("nan")
    return 1.0 - float(np.mean(scores)) / ref_mean


def band_coverage(
    members: np.ndarray | list[float],
    observation: float,
    *,
    nominal: float = 0.90,
) -> bool:
    """True when the observation falls inside the central quantile band.

    For nominal=0.90 the band is [q5, q95]; for 0.50 it is [q25, q75].
    """
    if not 0.0 < nominal < 1.0:
        raise ValueError(f"nominal must be in (0, 1), got {nominal}")
    x = np.asarray(members, dtype=float)
    if x.ndim != 1 or x.size == 0:
        raise ValueError("members must be a non-empty 1-D array")
    alpha = (1.0 - nominal) / 2.0
    lower, upper = np.quantile(x, [alpha, 1.0 - alpha])
    return bool(lower <= observation <= upper)


def reliability_table(
    forecast_probabilities: np.ndarray | list[float],
    outcomes: np.ndarray | list[float],
    *,
    n_bins: int = 10,
) -> pd.DataFrame:
    """Reliability bins: mean forecast probability vs observed frequency.

    Returns a DataFrame with columns: bin, mean_forecast, observed_frequency, count.
    Empty bins are dropped. This feeds a reliability diagram; it does not plot.
    """
    p = np.asarray(forecast_probabilities, dtype=float)
    o = np.asarray(outcomes, dtype=float)
    if p.shape != o.shape:
        raise ValueError("forecast_probabilities and outcomes must have the same shape")
    if p.size == 0:
        raise ValueError("inputs must be non-empty")
    if np.any((p < 0) | (p > 1)):
        raise ValueError("forecast probabilities must be in [0, 1]")
    if not np.all((o == 0) | (o == 1)):
        raise ValueError("outcomes must be binary (0/1)")

    edges = np.linspace(0.0, 1.0, n_bins + 1)
    # Rightmost edge inclusive so p == 1 lands in the last bin.
    which = np.digitize(p, edges[1:-1], right=False)
    rows: list[dict[str, float | int]] = []
    for bin_id in range(n_bins):
        mask = which == bin_id
        count = int(mask.sum())
        if count == 0:
            continue
        rows.append(
            {
                "bin": bin_id,
                "mean_forecast": float(p[mask].mean()),
                "observed_frequency": float(o[mask].mean()),
                "count": count,
            }
        )
    return pd.DataFrame.from_records(rows)
