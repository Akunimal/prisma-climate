"""Unit tests for calibration — synthetic data only, no archived forecasts."""

from __future__ import annotations

import math

import numpy as np
import pytest

from prisma.calibrate import (
    EmosParams,
    crps_gaussian,
    fit_emos_gaussian,
    fit_quantile_mapping,
    predict_emos,
)


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
    assert np.allclose(sigma, params.c + params.d * ens_std)


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
