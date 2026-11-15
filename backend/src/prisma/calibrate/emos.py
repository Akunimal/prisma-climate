"""Gaussian EMOS (ensemble model output statistics) for daily temperature.

Two-stage least-squares fit (no scipy in this project):

1. location: obs ~ a + b * ensemble mean (OLS);
2. scale: squared residuals ~ c2 + d2 * ensemble variance (OLS, floored).

The predictive distribution is Gaussian; scoring uses the closed-form
``crps_gaussian``. Unit tests only — no archived data is fitted here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SCALE_FLOOR = 1e-3  # degC; keeps CRPS finite for degenerate ensembles
MIN_TRAINING = 10


@dataclass(frozen=True)
class EmosParams:
    """Fitted EMOS parameters: mu = a + b * ens_mean, var = (c + d * ens_std)^2."""

    a: float
    b: float
    c: float
    d: float

    def predict(self, ens_mean: float, ens_std: float) -> tuple[float, float]:
        """Return (mu, sigma) of the calibrated Gaussian."""
        mu = self.a + self.b * ens_mean
        sigma = self.c + self.d * max(ens_std, 0.0)
        return mu, max(sigma, SCALE_FLOOR)


def _as_2d(members: np.ndarray) -> np.ndarray:
    x = np.asarray(members, dtype=float)
    if x.ndim != 2 or x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("members must be a non-empty 2-D array (n_cases, n_members)")
    if not np.isfinite(x).all():
        raise ValueError("members must be finite")
    return x


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def crps_gaussian(observation: float, mu: float, sigma: float) -> float:
    """Closed-form CRPS of N(mu, sigma^2) at ``observation``.

    CRPS = sigma * [ z * (2*Phi(z) - 1) + 2*phi(z) - 1/sqrt(pi) ],
    z = (y - mu) / sigma. At y == mu it reduces to sigma / sqrt(pi).
    """
    y = float(observation)
    sigma = float(sigma)
    if not math.isfinite(y):
        raise ValueError("observation must be finite")
    if not math.isfinite(sigma) or sigma <= 0.0:
        raise ValueError("sigma must be positive and finite")
    z = (y - mu) / sigma
    return sigma * (z * (2.0 * _norm_cdf(z) - 1.0) + 2.0 * _norm_pdf(z) - 1.0 / math.sqrt(math.pi))


def fit_emos_gaussian(members: np.ndarray, observations: np.ndarray) -> EmosParams:
    """Fit EMOS on paired (ensemble members, observations) training cases.

    ``members`` is (n_cases, n_members); ``observations`` is (n_cases,).
    Requires at least ``MIN_TRAINING`` cases. The scale fit uses squared
    residuals against the ensemble variance with a plain OLS line through
    the origin-free model r^2 ~ (c + d*s)^2 approximated as
    r^2 ~ c^2 + d^2 * s^2 + 2*c*d*s; we fit r^2 ~ [1, s, s^2] and derive
    c = sqrt(max(coef0, 0)), d = sqrt(max(coef2, 0)) with the cross term
    ignored (standard two-stage simplification; documented in tests).
    """
    x = _as_2d(members)
    y = np.asarray(observations, dtype=float)
    if y.ndim != 1 or y.shape[0] != x.shape[0]:
        raise ValueError("observations must be 1-D with one value per members row")
    if not np.isfinite(y).all():
        raise ValueError("observations must be finite")
    if y.shape[0] < MIN_TRAINING:
        raise ValueError(f"need at least {MIN_TRAINING} training cases, got {y.shape[0]}")

    ens_mean = x.mean(axis=1)
    ens_std = x.std(axis=1, ddof=1) if x.shape[1] > 1 else np.zeros(x.shape[0])

    # Stage 1: location.
    design = np.column_stack([np.ones(x.shape[0]), ens_mean])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    a, b = float(coef[0]), float(coef[1])

    # Stage 2: scale from squared residuals.
    resid2 = (y - (a + b * ens_mean)) ** 2
    var_design = np.column_stack([np.ones(x.shape[0]), ens_std, ens_std**2])
    var_coef, *_ = np.linalg.lstsq(var_design, resid2, rcond=None)
    c = math.sqrt(max(float(var_coef[0]), SCALE_FLOOR**2))
    d = math.sqrt(max(float(var_coef[2]), 0.0))
    return EmosParams(a=a, b=b, c=c, d=d)


def predict_emos(params: EmosParams, members: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Calibrated (mu, sigma) per case for a (n_cases, n_members) array."""
    x = _as_2d(members)
    ens_mean = x.mean(axis=1)
    ens_std = x.std(axis=1, ddof=1) if x.shape[1] > 1 else np.zeros(x.shape[0])
    mu = params.a + params.b * ens_mean
    sigma = np.maximum(params.c + params.d * ens_std, SCALE_FLOOR)
    return mu, sigma
