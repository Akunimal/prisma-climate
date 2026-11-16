"""Unit tests for calibration — synthetic data only, no archived forecasts."""

from __future__ import annotations

import math

import numpy as np
import pytest

from prisma.calibrate import (
    EmosParams,
    crps_gaussian,
    fit_emos_gaussian,
    fit_emos_two_stage,
    fit_quantile_mapping,
    predict_emos,
)
from prisma.calibrate.emos import SCALE_FLOOR, _crps_mean_and_grad
from prisma.calibrate.run_crpss import aggregate_crpss, score_case


def test_crps_gaussian_at_mean_equals_sigma_times_constant() -> None:
    # At z = 0 the closed form reduces to sigma * (sqrt(2) - 1) / sqrt(pi).
    assert crps_gaussian(5.0, 5.0, 2.0) == pytest.approx(
        2.0 * (math.sqrt(2.0) - 1.0) / math.sqrt(math.pi)
    )


def test_crps_gaussian_rejects_bad_inputs() -> None:
    with pytest.raises(ValueError):
        crps_gaussian(math.nan, 0.0, 1.0)
    with pytest.raises(ValueError):
        crps_gaussian(0.0, 0.0, 0.0)
    with pytest.raises(ValueError):
        crps_gaussian(0.0, 0.0, math.inf)


def test_crps_gaussian_grows_with_error() -> None:
    near = crps_gaussian(1.0, 0.0, 1.0)
    far = crps_gaussian(4.0, 0.0, 1.0)
    assert far > near > 0.0


def _biased_ensemble(rng: np.random.Generator, n: int = 400) -> tuple[np.ndarray, np.ndarray]:
    """Ensemble centered 3 degC too warm with overstated truth-independent noise."""
    truth = rng.normal(20.0, 5.0, size=n)
    members = truth[:, None] + 3.0 + rng.normal(0.0, 1.0, size=(n, 31))
    return members, truth


def test_fit_emos_recovers_bias_direction() -> None:
    rng = np.random.default_rng(7)
    members, obs = _biased_ensemble(rng)
    params = fit_emos_gaussian(members, obs)
    # Raw ensemble mean is ~3 too warm; calibrated location must shift it down.
    raw_mean = float(members.mean())
    mu, sigma = params.predict(raw_mean, float(members.std()))
    assert mu < raw_mean
    assert sigma > 0.0
    # And be closer to the mean observation than the raw mean is.
    obs_mean = float(obs.mean())
    assert abs(mu - obs_mean) < abs(raw_mean - obs_mean)


def test_fit_emos_calibrated_crps_beats_raw_on_holdout() -> None:
    rng = np.random.default_rng(11)
    train_members, train_obs = _biased_ensemble(rng, n=500)
    test_members, test_obs = _biased_ensemble(rng, n=300)
    params = fit_emos_gaussian(train_members, train_obs)

    mu, sigma = predict_emos(params, test_members)
    calibrated = np.mean(
        [crps_gaussian(y, m, s) for y, m, s in zip(test_obs, mu, sigma, strict=True)]
    )
    raw = np.mean(
        [
            crps_gaussian(y, float(row.mean()), max(float(row.std(ddof=1)), 1e-3))
            for y, row in zip(test_obs, test_members, strict=True)
        ]
    )
    assert calibrated < raw


def test_fit_emos_validates_shapes_and_size() -> None:
    with pytest.raises(ValueError):
        fit_emos_gaussian(np.ones((5, 31)), np.ones(5))  # below MIN_TRAINING
    with pytest.raises(ValueError):
        fit_emos_gaussian(np.ones((10, 31)), np.ones(11))
    with pytest.raises(ValueError):
        fit_emos_gaussian(np.ones((10, 0)), np.ones(10))
    bad = np.ones((10, 31))
    bad[0, 0] = np.nan
    with pytest.raises(ValueError):
        fit_emos_gaussian(bad, np.ones(10))


def test_predict_emos_matches_params_formula() -> None:
    params = EmosParams(a=1.0, b=0.5, c=0.2, d=0.1)
    members = np.full((4, 31), 10.0)
    members[:, :15] = 12.0  # nonzero spread
    mu, sigma = predict_emos(params, members)
    ens_mean = members.mean(axis=1)
    ens_std = members.std(axis=1, ddof=1)
    assert np.allclose(mu, params.a + params.b * ens_mean)
    assert np.allclose(sigma, np.sqrt(params.c + params.d * ens_std**2))


def test_emos_params_predict_floors_sigma() -> None:
    params = EmosParams(a=0.0, b=1.0, c=0.0, d=0.0)
    _, sigma = params.predict(1.0, 1.0)
    assert sigma > 0.0


def test_quantile_mapping_shifts_by_constant() -> None:
    rng = np.random.default_rng(3)
    forecast = rng.normal(10.0, 2.0, size=500)
    observations = forecast + 4.0
    qm = fit_quantile_mapping(forecast, observations)
    mapped = qm.apply(np.array([8.0, 10.0, 12.0]))
    assert np.allclose(mapped, [12.0, 14.0, 16.0], atol=0.5)


def test_quantile_mapping_clips_outside_training_range() -> None:
    forecast = np.linspace(0.0, 10.0, 100)
    observations = forecast  # identity inside
    qm = fit_quantile_mapping(forecast, observations)
    mapped = qm.apply(np.array([-5.0, 15.0]))
    # Clipped to observed range endpoints, not extrapolated.
    assert mapped[0] == pytest.approx(0.0)
    assert mapped[1] == pytest.approx(10.0)


def test_quantile_mapping_validates_inputs() -> None:
    with pytest.raises(ValueError):
        fit_quantile_mapping(np.ones(5), np.ones(5))  # below MIN_TRAINING
    with pytest.raises(ValueError):
        fit_quantile_mapping(np.ones(10), np.ones(9))
    with pytest.raises(ValueError):
        fit_quantile_mapping(np.array([1.0] * 10 + [np.nan]), np.ones(11))
    qm = fit_quantile_mapping(np.arange(10.0), np.arange(10.0))
    with pytest.raises(ValueError):
        qm.apply(np.array([np.nan]))


def test_quantile_mapping_identity_when_same_distribution() -> None:
    rng = np.random.default_rng(5)
    sample = rng.normal(0.0, 1.0, size=2000)
    qm = fit_quantile_mapping(sample, sample.copy())
    probe = np.linspace(-2.0, 2.0, 21)
    assert np.allclose(qm.apply(probe), probe, atol=0.15)


# --- synthetic known-truth cases (same construction as the EMOS diagnosis) ---


def _synthetic_cases_ab() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Seasonal obs; A = stationary +2.5 warm bias; B = +2.5 -> -2.5 flip."""
    rng = np.random.default_rng(7)
    n, k = 240, 31
    t = np.arange(n)
    obs = 18.0 + 8.0 * np.sin(2 * np.pi * t / 365.0) + rng.normal(0.0, 1.5, n)
    mem_a = obs[:, None] + 2.5 + rng.normal(0.0, 1.2, (n, k))
    mem_b = obs[:, None] + np.where(t < 120, 2.5, -2.5)[:, None] + rng.normal(
        0.0, 1.2, (n, k)
    )
    return obs, mem_a, mem_b


def _crpss_on_eval(params, members: np.ndarray, obs: np.ndarray, start: int) -> float:
    raw, cal = [], []
    for i in range(start, members.shape[0]):
        scored = score_case(members[i], float(obs[i]), emos_params=params, qm=None)
        raw.append(scored["crps_raw"])
        cal.append(scored["crps_emos"])
    return aggregate_crpss(np.asarray(raw), np.asarray(cal))


def test_fit_emos_recovers_bias_and_spread_on_synthetic_a() -> None:
    obs, mem_a, _ = _synthetic_cases_ab()
    params = fit_emos_gaussian(mem_a[:120], obs[:120])

    # Bias: mean applied correction ~ -2.5 degC.
    applied = params.a + (params.b - 1.0) * mem_a[:120].mean(axis=1)
    assert float(applied.mean()) == pytest.approx(-2.5, abs=0.5)

    # Spread: predictive sd matches the residual sd (0.6 < ratio < 1.6).
    mu_tr, sigma_tr = predict_emos(params, mem_a[:120])
    resid_sd = float(np.std(obs[:120] - mu_tr, ddof=1))
    ratio = float(sigma_tr.mean()) / resid_sd
    assert 0.6 < ratio < 1.6, ratio

    # Skill: beats the raw ensemble on held-out eval cases.
    assert _crpss_on_eval(params, mem_a, obs, start=120) > 0.0


def test_fit_emos_synthetic_b_not_degenerate_to_floor() -> None:
    obs, _, mem_b = _synthetic_cases_ab()
    params = fit_emos_gaussian(mem_b[:120], obs[:120])

    # A near-constant spread must not collapse the variance onto the floor.
    assert params.c > SCALE_FLOOR
    mu_tr, sigma_tr = predict_emos(params, mem_b[:120])
    resid_sd = float(np.std(obs[:120] - mu_tr, ddof=1))
    ratio = float(sigma_tr.mean()) / resid_sd
    assert 0.6 < ratio < 1.6, ratio

    # The regime flip still hurts — the chronological failure is in the data,
    # not in the fit: the -2.5 correction learned on train doubles the error.
    assert _crpss_on_eval(params, mem_b, obs, start=120) < 0.0


def test_fit_emos_recovers_known_spread_skill() -> None:
    rng = np.random.default_rng(21)
    n, k = 400, 31
    ens_mean = rng.normal(0.0, 6.0, n)
    driver = rng.uniform(0.8, 3.0, n)
    members = ens_mean[:, None] + driver[:, None] * rng.normal(0.0, 1.0, (n, k))
    true_var = 1.0 + 0.5 * driver**2
    obs = -1.5 + 0.9 * ens_mean + rng.normal(0.0, np.sqrt(true_var))

    params = fit_emos_gaussian(members[:300], obs[:300])
    assert params.a == pytest.approx(-1.5, abs=0.5)
    assert params.b == pytest.approx(0.9, abs=0.15)

    mu_tr, sigma_tr = predict_emos(params, members[:300])
    sigma_true = np.sqrt(true_var[:300])
    assert mu_tr.shape == sigma_tr.shape
    ratio = float(sigma_tr.mean()) / float(sigma_true.mean())
    assert 0.7 < ratio < 1.3, ratio
    corr = float(np.corrcoef(sigma_tr, sigma_true)[0, 1])
    assert corr > 0.9, corr


def test_two_stage_fit_documents_overdispersion_failure() -> None:
    """Historical fit: predictive sd far above the residual sd (case A)."""
    obs, mem_a, _ = _synthetic_cases_ab()
    old = fit_emos_two_stage(mem_a[:120], obs[:120])
    mu_tr = old.a + old.b * mem_a[:120].mean(axis=1)
    resid_sd = float(np.std(obs[:120] - mu_tr, ddof=1))
    ens_mean = mem_a[:120].mean(axis=1)
    ens_std = mem_a[:120].std(axis=1, ddof=1)
    # Historical parametrisation: sigma = c + d * ens_std.
    mu_p, sigma_p = old.predict(float(ens_mean[0]), float(ens_std[0]))
    assert mu_p == pytest.approx(float(mu_tr[0]))
    assert sigma_p == pytest.approx(float(old.c + old.d * ens_std[0]), rel=1e-12)
    assert float((old.c + old.d * ens_std).mean()) / resid_sd > 1.6


def test_two_stage_fit_documents_floor_collapse_failure() -> None:
    """Historical fit collapses to the scale floor on near-constant spread."""
    obs, _, mem_b = _synthetic_cases_ab()
    old = fit_emos_two_stage(mem_b[:120], obs[:120])
    assert old.c == pytest.approx(SCALE_FLOOR, rel=0.5)
    # Scoring with it is unusable: the degenerate width destroys the CRPSS.
    assert _crpss_on_eval(old, mem_b, obs, start=120) < -1.0


def test_crps_gradient_matches_finite_differences() -> None:
    rng = np.random.default_rng(3)
    n = 40
    ens_mean = rng.normal(10.0, 3.0, n)
    ens_var = rng.uniform(0.5, 4.0, n)
    obs = 11.0 + 0.8 * ens_mean + rng.normal(0.0, 1.2, n)
    theta = np.array([0.5, 0.9, 1.4, 0.3])
    _, grad = _crps_mean_and_grad(theta, ens_mean, ens_var, obs)
    eps = 1e-6
    for i in range(theta.size):
        plus, minus = theta.copy(), theta.copy()
        plus[i] += eps
        minus[i] -= eps
        obj_p, _ = _crps_mean_and_grad(plus, ens_mean, ens_var, obs)
        obj_m, _ = _crps_mean_and_grad(minus, ens_mean, ens_var, obs)
        fd = (obj_p - obj_m) / (2.0 * eps)
        assert float(grad[i]) == pytest.approx(fd, rel=1e-4, abs=1e-6)
