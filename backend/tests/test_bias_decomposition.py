"""Unit tests for bias decomposition — pure functions only, no network."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest

from prisma.report.bias_decomposition import (
    adjust_elevation,
    best_day_lag,
    bias_after_shift,
    decompose_location,
    fetch_raw_grid_cached,
    hourly_sampling_correction,
    missing_ranges,
    parabolic_peak,
    precip_orography_record,
)


def test_adjust_elevation_lowers_values_when_grid_is_higher() -> None:
    # Grid 1000 m above station → station air is warmer → add +6.5 °C.
    out = adjust_elevation(
        pd.Series([30.0, 31.0]),
        grid_elevation_m=2000.0,
        station_elevation_m=1000.0,
    )
    assert out.tolist() == pytest.approx([36.5, 37.5])


def test_adjust_elevation_raises_values_when_grid_is_lower() -> None:
    # Station 500 m above grid → station air is colder → subtract 3.25 °C.
    out = adjust_elevation(pd.Series([10.0]), grid_elevation_m=100.0, station_elevation_m=600.0)
    assert out.iloc[0] == pytest.approx(10.0 - 6.5 * 0.5)


def test_parabolic_peak_symmetric() -> None:
    # Peak exactly at the centre sample.
    assert parabolic_peak(10.0, 12.0, 10.0) == pytest.approx(12.0)


def test_parabolic_peak_off_centre() -> None:
    # Concave-down parabola through (0,0), (1,1), (2,0) peaks at x=1, y=1.
    assert parabolic_peak(0.0, 1.0, 0.0) == pytest.approx(1.0)
    # Left sample higher than right → vertex left of centre, peak above y_center.
    peak = parabolic_peak(0.6, 1.0, 0.0)
    assert peak is not None
    assert peak > 1.0


def test_parabolic_peak_rejects_non_peak() -> None:
    assert parabolic_peak(1.0, 1.0, 1.0) is None  # flat
    assert parabolic_peak(0.0, 1.0, 2.0) is None  # concave up


def test_hourly_sampling_correction_uses_interior_daily_peaks() -> None:
    # Two local days; only interior maxima of each day contribute.
    times = pd.to_datetime(
        [
            "2026-01-01 10:00",
            "2026-01-01 11:00",
            "2026-01-01 12:00",
            "2026-01-01 13:00",
            "2026-01-02 10:00",
            "2026-01-02 11:00",
            "2026-01-02 12:00",
            "2026-01-02 13:00",
        ]
    )
    # Day 1: peak at 12:00 with neighbours 20, 22, 20 → parabola peak = 22.
    # Day 2: peak at 12:00 with neighbours 20, 24, 20 → peak = 24.
    values = [20.0, 21.0, 22.0, 21.0, 20.0, 22.0, 24.0, 22.0]
    frame = pd.DataFrame({"time": times, "value": values})
    correction = hourly_sampling_correction(frame)
    # peak − hourly max is 0 for both perfect parabolas.
    assert correction == pytest.approx(0.0)


def test_hourly_sampling_correction_positive_when_peak_above_samples() -> None:
    # Samples undershoot a continuous peak: 20, 21, 21 around true peak ~21.5
    times = pd.to_datetime(
        ["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 12:00", "2026-01-01 13:00"]
    )
    values = [18.0, 21.0, 21.0, 18.0]
    # At i=1 (11:00): neighbours 18,21,21 → denom = 18-42+21 = -3, delta = 0.5*(18-21)/(-3)=0.5
    # peak = 21 - 0.25*(18-21)*0.5 = 21 + 0.375 = 21.375 → correction 0.375
    # At i=2 (12:00): neighbours 21,21,18 → not a local max (21 >= 21 and 21 >= 18 ok),
    # denom = 21-42+18 = -3, delta = 0.5*(21-18)/(-3) = -0.5
    # peak = 21 - 0.25*(21-18)*(-0.5) = 21 + 0.375 = 21.375 → correction 0.375
    correction = hourly_sampling_correction(pd.DataFrame({"time": times, "value": values}))
    assert correction == pytest.approx(0.375)


def test_hourly_sampling_correction_empty_returns_none() -> None:
    frame = pd.DataFrame({"time": pd.to_datetime([]), "value": pd.Series([], dtype=float)})
    assert hourly_sampling_correction(frame) is None


def test_best_day_lag_detects_one_day_offset() -> None:
    index = pd.date_range("2026-01-01", periods=10, freq="D")
    era5 = pd.Series(range(10), index=index, dtype=float)
    # Station is one day behind ERA5: station[t] = era5[t-1] for t>=1
    station = pd.Series([0.0] + list(range(9)), index=index)
    lag, mae = best_day_lag(era5, station, lags=(-1, 0, 1))
    # station.shift(-1) aligns station[t+1] with era5[t]; station[t+1]=t, era5[t]=t → perfect
    assert lag == 1
    assert mae == pytest.approx(0.0)


def test_bias_after_shift_none_when_empty() -> None:
    index = pd.date_range("2026-01-01", periods=2, freq="D")
    era5 = pd.Series([1.0, 2.0], index=index)
    station = pd.Series([math.nan, math.nan], index=index)
    assert bias_after_shift(era5, station, 0) is None


def test_decompose_location_reports_residual_after_each_step() -> None:
    index = pd.date_range("2026-01-01", periods=5, freq="D")
    # Station always 1 °C warmer than raw ERA5.
    station = pd.Series([30.0, 31.0, 32.0, 33.0, 34.0], index=index)
    era5 = station - 1.0

    record = decompose_location(
        era5,
        station,
        grid_elevation_m=1000.0,
        station_elevation_m=1000.0,
        sampling_correction_c=0.0,
    )
    assert record["n_days"] == 5
    assert record["bias_raw"] == pytest.approx(-1.0)
    assert record["bias_after_elevation"] == pytest.approx(-1.0)  # no elev gap
    assert record["bias_after_sampling"] == pytest.approx(-1.0)  # zero correction
    assert record["best_day_lag"] in (-1, 0, 1)
    assert record["bias_after_day_convention"] is not None


def test_decompose_location_elevation_adjustment_reduces_bias() -> None:
    index = pd.date_range("2026-01-01", periods=4, freq="D")
    station = pd.Series([20.0, 21.0, 22.0, 23.0], index=index)
    # Grid is 1000 m higher and reads 6.5 °C colder than the station-adjusted value.
    # Raw ERA5 = station - 6.5 (elevation-only bias). After lapse correction → 0.
    era5 = station - 6.5
    record = decompose_location(
        era5,
        station,
        grid_elevation_m=2000.0,
        station_elevation_m=1000.0,
        sampling_correction_c=None,
    )
    assert record["bias_raw"] == pytest.approx(-6.5)
    assert record["bias_after_elevation"] == pytest.approx(0.0, abs=1e-12)
    assert record["bias_after_sampling"] == pytest.approx(0.0, abs=1e-12)


def test_decompose_location_rejects_no_overlap() -> None:
    with pytest.raises(ValueError, match="no overlapping"):
        decompose_location(
            pd.Series(dtype=float),
            pd.Series(dtype=float),
            grid_elevation_m=None,
            station_elevation_m=None,
            sampling_correction_c=None,
        )


def test_precip_orography_record_notes() -> None:
    wet = precip_orography_record(ratio=2.3, grid_elevation_m=1500.0, station_elevation_m=1200.0)
    assert wet["elevation_diff_m"] == 300.0
    assert "orographic enhancement" in wet["note"]

    flat = precip_orography_record(ratio=2.3, grid_elevation_m=100.0, station_elevation_m=120.0)
    assert "does not explain" in flat["note"]

    unknown = precip_orography_record(ratio=None, grid_elevation_m=None, station_elevation_m=None)
    assert unknown["note"] == ""


def test_missing_ranges_reports_only_gaps() -> None:
    full = pd.date_range("2026-01-01", "2026-01-10", freq="D")
    assert missing_ranges(full, "2026-01-01", "2026-01-10") == []
    assert missing_ranges([], "2026-01-01", "2026-01-03") == [
        ("2026-01-01", "2026-01-03")
    ]
    gapped = full.delete([3, 4])  # 2026-01-04 and 2026-01-05 missing
    assert missing_ranges(gapped, "2026-01-01", "2026-01-10") == [
        ("2026-01-04", "2026-01-05")
    ]
    edge = pd.DatetimeIndex(["2026-01-02"])
    assert missing_ranges(edge, "2026-01-01", "2026-01-03") == [
        ("2026-01-01", "2026-01-01"),
        ("2026-01-03", "2026-01-03"),
    ]


def test_fetch_raw_grid_cached_is_resumable(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def fake_fetch(
        lat: float,
        lon: float,
        start: str,
        end: str,
        *,
        timezone: str,
        pause_seconds: float = 0.0,
    ) -> tuple[pd.Series, float | None]:
        calls.append((start, end))
        index = pd.date_range(start, end, freq="D")
        return pd.Series(range(len(index)), index=index, dtype=float), 123.0

    cache = tmp_path / "openmeteo-era5-rawgrid.parquet"
    kwargs = {
        "cache_path": cache,
        "location": "Test Station",
        "lat": 0.0,
        "lon": 0.0,
        "timezone": "UTC",
        "pause_seconds": 0.0,
    }

    first, first_el = fetch_raw_grid_cached(
        fake_fetch, start="2026-01-01", end="2026-01-10", **kwargs
    )
    assert calls == [("2026-01-01", "2026-01-10")]
    assert len(first) == 10
    assert first_el == 123.0
    assert cache.exists()

    # Fully cached: no network call, same values and elevation.
    second, second_el = fetch_raw_grid_cached(
        fake_fetch, start="2026-01-01", end="2026-01-10", **kwargs
    )
    assert len(calls) == 1
    assert len(second) == 10
    assert second_el == 123.0

    # Extended range: only the new tail is fetched.
    third, _ = fetch_raw_grid_cached(
        fake_fetch, start="2026-01-01", end="2026-01-12", **kwargs
    )
    assert calls[-1] == ("2026-01-11", "2026-01-12")
    assert len(third) == 12

    # A hole inside the cached range is refetched, not the whole history.
    frame = pd.read_parquet(cache)
    hole_days = pd.to_datetime(["2026-01-05", "2026-01-06"])
    hole = frame.loc[~pd.to_datetime(frame["time"]).isin(hole_days)]
    hole.to_parquet(cache, index=False)
    fourth, _ = fetch_raw_grid_cached(
        fake_fetch, start="2026-01-01", end="2026-01-12", **kwargs
    )
    assert calls[-1] == ("2026-01-05", "2026-01-06")
    assert len(fourth) == 12

    # The default downscaled archive is never written by this path.
    assert not (tmp_path / "openmeteo-era5.parquet").exists()
