"""Gaussian EMOS (ensemble model output statistics) for daily temperature.

Standard EMOS fit (Gneiting et al. 2005): the predictive distribution is

    N(mu, sigma^2),   mu = a + b * ens_mean,   sigma^2 = c + d * ens_var

with (a, b, c, d) estimated **jointly** by minimising the mean CRPS on the
training sample under ``c >= SCALE_FLOOR^2`` and ``d >= 0``. The optimiser
is a projected normalised-gradient descent with Armijo backtracking and an
analytic CRPS gradient (no scipy); the fit-time normal CDF uses an
Abramowitz–Stegun approximation (|error| < 1.5e-7) while scoring keeps the
exact ``erf`` closed form.

The earlier two-stage OLS fit survives only as ``fit_emos_two_stage`` /
``TwoStageParams`` so its failure stays executable and testable: it
over-disperses and collapses onto the scale floor when the ensemble spread
is near-constant (see tests). Never score with it.

Unit tests only — no archived data is fitted here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SCALE_FLOOR = 1e-3  # degC; keeps CRPS finite for degenerate ensembles
MIN_TRAINING = 10

_C_MIN = SCALE_FLOOR**2  # lower bound on the predictive variance
_FIT_MAX_ITER = 600
_FIT_PATIENT = 8


@dataclass(frozen=True)
class EmosParams:
    """Fitted EMOS parameters: mu = a + b * ens_mean, var = c + d * ens_var."""

    a: float
    b: float
    c: float
    d: float

    def predict(self, ens_mean: float, ens_std: float) -> tuple[float, float]:
        """Return (mu, sigma) of the calibrated Gaussian."""
        mu = self.a + self.b * ens_mean
        var = self.c + self.d * max(ens_std, 0.0) ** 2
        return mu, math.sqrt(max(var, _C_MIN))


@dataclass(frozen=True)
class TwoStageParams:
    """Historical two-stage parameters: sigma = c + d * ens_std (kept for tests)."""

    a: float
    b: float
    c: float
    d: float

    def predict(self, ens_mean: float, ens_std: float) -> tuple[float, float]:
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


def _validate_pairs(members: np.ndarray, observations: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x = _as_2d(members)
    y = np.asarray(observations, dtype=float)
    if y.ndim != 1 or y.shape[0] != x.shape[0]:
        raise ValueError("observations must be 1-D with one value per members row")
    if not np.isfinite(y).all():
        raise ValueError("observations must be finite")
    if y.shape[0] < MIN_TRAINING:
        raise ValueError(f"need at least {MIN_TRAINING} training cases, got {y.shape[0]}")
    return x, y


def _norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_pdf(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _norm_cdf_vec(z: np.ndarray) -> np.ndarray:
    """Vector normal CDF (Abramowitz & Stegun 7.1.26, |err| < 1.5e-7)."""
    x = np.abs(z)
    t = 1.0 / (1.0 + 0.2316419 * x)
    tail_poly = t * (
        0.319381530
        + t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429)))
    )
    tail = np.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi) * tail_poly
    return np.where(z >= 0.0, 1.0 - tail, tail)


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


def _crps_mean_and_grad(
    theta: np.ndarray, ens_mean: np.ndarray, ens_var: np.ndarray, obs: np.ndarray
) -> tuple[float, np.ndarray]:
    """Mean CRPS and its gradient over (a, b, c, d) for the training pairs.

    d CRPS / d mu = 1 - 2*Phi(z);  d CRPS / d sigma = 2*phi(z) - 1/sqrt(pi);
    d sigma / d c = 1 / (2 sigma); d sigma / d d = ens_var / (2 sigma).
    """
    a, b, c, d = (float(t) for t in theta)
    mu = a + b * ens_mean
    sigma = np.sqrt(np.maximum(c + d * ens_var, _C_MIN))
    z = (obs - mu) / sigma
    phi = np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    two_phi_minus = 2.0 * _norm_cdf_vec(z) - 1.0
    crps = sigma * (z * two_phi_minus + 2.0 * phi - 1.0 / math.sqrt(math.pi))
    g_mu = -two_phi_minus  # 1 - 2*Phi(z)
    g_sigma = 2.0 * phi - 1.0 / math.sqrt(math.pi)
    half_over = 1.0 / (2.0 * sigma)
    grad = np.array(
        [
            float(g_mu.mean()),
            float((g_mu * ens_mean).mean()),
            float((g_sigma * half_over).mean()),
            float((g_sigma * ens_var * half_over).mean()),
        ]
    )
    return float(crps.mean()), grad


def _project(theta: np.ndarray) -> np.ndarray:
    out = theta.copy()
    out[2] = max(out[2], _C_MIN)
    out[3] = max(out[3], 0.0)
    return out


def fit_emos_gaussian(members: np.ndarray, observations: np.ndarray) -> EmosParams:
    """Fit EMOS by minimising the mean CRPS on the training pairs.

    ``members`` is (n_cases, n_members); ``observations`` is (n_cases,).
    Requires at least ``MIN_TRAINING`` cases. Location starts from OLS and
    scale from a moment match on squared residuals; both are then refined
    jointly by projected normalised-gradient descent with Armijo
    backtracking until the objective stalls (``_FIT_MAX_ITER`` cap).
    """
    x, y = _validate_pairs(members, observations)

    ens_mean = x.mean(axis=1)
    ens_std = x.std(axis=1, ddof=1) if x.shape[1] > 1 else np.zeros(x.shape[0])
    ens_var = ens_std**2

    # Location start: OLS of obs on ensemble mean.
    design = np.column_stack([np.ones(x.shape[0]), ens_mean])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    a0, b0 = float(coef[0]), float(coef[1])

    # Scale start: moment match of squared residuals on ens_var, floored.
    resid2 = (y - (a0 + b0 * ens_mean)) ** 2
    var_design = np.column_stack([np.ones(x.shape[0]), ens_var])
    var_coef, *_ = np.linalg.lstsq(var_design, resid2, rcond=None)
    c0, d0 = float(var_coef[0]), float(var_coef[1])
    if d0 <= 0.0:
        c0, d0 = float(resid2.mean()), 0.0
    theta = _project(np.array([a0, b0, c0, d0]))

    obj, grad = _crps_mean_and_grad(theta, ens_mean, ens_var, y)
    step = 1.0
    stagnant = 0
    for _ in range(_FIT_MAX_ITER):
        gnorm = float(np.linalg.norm(grad))
        if gnorm < 1e-6:
            break
        direction = -grad / gnorm
        accepted = False
        trial_step = step
        for _ls in range(60):
            trial = _project(theta + trial_step * direction)
            delta = trial - theta
            slope = float(grad @ delta)
            trial_obj, trial_grad = _crps_mean_and_grad(trial, ens_mean, ens_var, y)
            if slope < 0.0 and trial_obj <= obj + 1e-4 * slope:
                improvement = obj - trial_obj
                theta, obj, grad = trial, trial_obj, trial_grad
                step = min(trial_step * 1.8, 50.0)
                accepted = True
                if improvement <= 1e-9 + 1e-6 * abs(obj):
                    stagnant += 1
                else:
                    stagnant = 0
                break
            trial_step *= 0.5
        if not accepted or trial_step < 1e-14:
            break
        if stagnant >= _FIT_PATIENT:
            break

    return EmosParams(a=float(theta[0]), b=float(theta[1]), c=float(theta[2]), d=float(theta[3]))


def fit_emos_two_stage(members: np.ndarray, observations: np.ndarray) -> TwoStageParams:
    """Historical two-stage OLS fit — kept only so its failure stays testable.

    Stage 1 fits obs ~ a + b * ens_mean (OLS); stage 2 fits squared
    residuals ~ [1, s, s^2] and derives c = sqrt(coef0), d = sqrt(coef2),
    ignoring the cross term, under sigma = c + d * ens_std. The test suite
    documents that it over-disperses (predictive sd far above the residual
    sd) and can collapse onto the scale floor when the ensemble spread is
    near-constant. Do not use it for scoring.
    """
    x, y = _validate_pairs(members, observations)

    ens_mean = x.mean(axis=1)
    ens_std = x.std(axis=1, ddof=1) if x.shape[1] > 1 else np.zeros(x.shape[0])

    design = np.column_stack([np.ones(x.shape[0]), ens_mean])
    coef, *_ = np.linalg.lstsq(design, y, rcond=None)
    a, b = float(coef[0]), float(coef[1])

    resid2 = (y - (a + b * ens_mean)) ** 2
    var_design = np.column_stack([np.ones(x.shape[0]), ens_std, ens_std**2])
    var_coef, *_ = np.linalg.lstsq(var_design, resid2, rcond=None)
    c = math.sqrt(max(float(var_coef[0]), SCALE_FLOOR**2))
    d = math.sqrt(max(float(var_coef[2]), 0.0))
    return TwoStageParams(a=a, b=b, c=c, d=d)


def predict_emos(params: EmosParams, members: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Calibrated (mu, sigma) per case for a (n_cases, n_members) array."""
    x = _as_2d(members)
    ens_mean = x.mean(axis=1)
    ens_std = x.std(axis=1, ddof=1) if x.shape[1] > 1 else np.zeros(x.shape[0])
    mu = params.a + params.b * ens_mean
    sigma = np.sqrt(np.maximum(params.c + params.d * ens_std**2, _C_MIN))
    return mu, sigma
