"""Unit tests for verification metrics — analytical values only, no data files."""

from __future__ import annotations

import math

import pytest

from prisma.verify.metrics import (
    band_coverage,
    brier_score,
    brier_skill_score,
    crps_ensemble,
    crps_from_samples,
    crpss,
    reliability_table,
)


def test_crps_single_member_equals_absolute_error() -> None:
    assert crps_ensemble([10.0], 12.5) == pytest.approx(2.5)


def test_crps_perfect_forecast_is_zero() -> None:
    assert crps_ensemble([5.0, 5.0, 5.0], 5.0) == pytest.approx(0.0)


def test_crps_two_members_analytical() -> None:
    # term1 = mean(|0-1|, |2-1|) = 1.0
    # term2 = mean of |xi-xj| over ordered pairs = (0+2+2+0)/4 = 1.0
    # CRPS = 1.0 - 0.5 * 1.0 = 0.5
    assert crps_ensemble([0.0, 2.0], 1.0) == pytest.approx(0.5)


def test_crps_matches_hand_computed_three_members() -> None:
    members = [1.0, 2.0, 3.0]
    observation = 2.0
    term1 = (1 + 0 + 1) / 3
    pairwise = [
        abs(1 - 1),
        abs(1 - 2),
        abs(1 - 3),
        abs(2 - 1),
        abs(2 - 2),
        abs(2 - 3),
        abs(3 - 1),
        abs(3 - 2),
        abs(3 - 3),
    ]
    term2 = sum(pairwise) / 9
    expected = term1 - 0.5 * term2
    assert crps_ensemble(members, observation) == pytest.approx(expected)
    assert crps_from_samples(members, observation) == pytest.approx(expected)


def test_crps_rejects_empty_and_nonfinite() -> None:
    with pytest.raises(ValueError):
        crps_ensemble([], 1.0)
    with pytest.raises(ValueError):
        crps_ensemble([1.0], math.nan)


def test_crpss_known_value() -> None:
    # 1 - 0.8 / 1.0 = 0.2
    assert crpss([0.8, 0.8], [1.0, 1.0]) == pytest.approx(0.2)
    assert math.isnan(crpss([1.0], [0.0]))
    with pytest.raises(ValueError):
        crpss([1.0], [1.0, 2.0])


def test_brier_score_values() -> None:
    assert brier_score(0.7, True) == pytest.approx(0.09)
    assert brier_score(0.3, False) == pytest.approx(0.09)
    assert brier_score(1.0, True) == pytest.approx(0.0)
    assert brier_score(0.0, True) == pytest.approx(1.0)
    with pytest.raises(ValueError):
        brier_score(1.5, True)


def test_brier_skill_score() -> None:
    assert brier_skill_score([0.1], [0.2]) == pytest.approx(0.5)
    assert math.isnan(brier_skill_score([0.1], [0.0]))


def test_band_coverage_nominal_90_and_50() -> None:
    members = list(range(100))  # 0..99
    # np.quantile(0..99, 0.05) = 4.95, q95 = 94.05, q25 = 24.75, q75 = 74.25
    assert band_coverage(members, 50, nominal=0.90) is True
    assert band_coverage(members, 5, nominal=0.90) is True
    assert band_coverage(members, 0, nominal=0.90) is False
    assert band_coverage(members, 99, nominal=0.90) is False
    assert band_coverage(members, 50, nominal=0.50) is True
    assert band_coverage(members, 0, nominal=0.50) is False
    with pytest.raises(ValueError):
        band_coverage(members, 50, nominal=1.5)


def test_reliability_table_bins() -> None:
    forecasts = [0.1, 0.1, 0.6, 0.6, 0.9, 0.9]
    outcomes = [0, 0, 1, 0, 1, 1]
    table = reliability_table(forecasts, outcomes, n_bins=10)
    assert list(table.columns) == ["bin", "mean_forecast", "observed_frequency", "count"]
    assert table["count"].sum() == 6
    row01 = table.loc[table["mean_forecast"].round(1) == 0.1].iloc[0]
    assert row01["observed_frequency"] == pytest.approx(0.0)
    assert row01["count"] == 2


def test_reliability_table_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        reliability_table([0.5], [0.5, 1.0])
    with pytest.raises(ValueError):
        reliability_table([1.5], [1.0])
    with pytest.raises(ValueError):
        reliability_table([0.5], [2.0])
    with pytest.raises(ValueError):
        reliability_table([], [])


def test_reliability_table_p_equals_one_in_last_bin() -> None:
    table = reliability_table([1.0, 1.0], [1, 0], n_bins=10)
    assert len(table) == 1
    assert table.iloc[0]["bin"] == 9
    assert table.iloc[0]["observed_frequency"] == pytest.approx(0.5)
