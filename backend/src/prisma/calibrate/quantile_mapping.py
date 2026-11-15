"""Empirical quantile mapping (nonparametric CDF matching).

Transfer function built from paired training samples: quantiles of the
raw forecast sample mapped to quantiles of the observation sample at the
same levels. Applied per ensemble member; values outside the training
forecast range are clipped to the observed range (no extrapolation —
documented, keeps the method honest on tails).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

N_QUANTILES = 101  # levels 0, 0.01, ..., 1.00
MIN_TRAINING = 10


@dataclass(frozen=True)
class QuantileMapping:
    """Piecewise-linear transfer function from forecast to observed quantiles."""

    levels: np.ndarray  # (k,) in [0, 1]
    forecast_quantiles: np.ndarray  # (k,)
    observed_quantiles: np.ndarray  # (k,)

    def apply(self, values: np.ndarray) -> np.ndarray:
        """Map forecast values through the transfer function (clipped)."""
        x = np.asarray(values, dtype=float)
        if not np.isfinite(x).all():
            raise ValueError("values must be finite")
        mapped = np.interp(x, self.forecast_quantiles, self.observed_quantiles)
        return mapped


def fit_quantile_mapping(forecast: np.ndarray, observations: np.ndarray) -> QuantileMapping:
    """Fit the transfer function on paired training samples.

    ``forecast`` and ``observations`` are 1-D arrays of equal length
    (same cases, e.g. raw ensemble mean vs station observation).
    """
    f = np.asarray(forecast, dtype=float)
    y = np.asarray(observations, dtype=float)
    if f.ndim != 1 or y.ndim != 1 or f.shape[0] != y.shape[0]:
        raise ValueError("forecast and observations must be 1-D of equal length")
    if f.shape[0] < MIN_TRAINING:
        raise ValueError(f"need at least {MIN_TRAINING} training cases, got {f.shape[0]}")
    if not np.isfinite(f).all() or not np.isfinite(y).all():
        raise ValueError("forecast and observations must be finite")

    levels = np.linspace(0.0, 1.0, N_QUANTILES)
    return QuantileMapping(
        levels=levels,
        forecast_quantiles=np.quantile(f, levels),
        observed_quantiles=np.quantile(y, levels),
    )
