"""Discrepancy report tests — no network access."""

from __future__ import annotations

import pandas as pd
import pytest

from prisma.report.discrepancies import (
    collect_precip_orography,
    collect_t2m_max_decomposition,
    compare,
    render_decomposition_section,
    render_honest_reading,
    render_markdown,
)


def _frame(rows: list[dict], source: str) -> pd.DataFrame:
    base = {
        "source": source,
        "quality_flag": "ok",
        "unit": "degC",
        "day_convention": "local_calendar",
    }
    return pd.DataFrame([{**base, **row} for row in rows])


def test_compare_computes_bias_and_filters_non_ok_rows() -> None:
    times = ["2026-01-01", "2026-01-02", "2026-01-03"]
    era5 = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": t, "value": v}
            for t, v in zip(times, [31.0, 32.0, 33.0], strict=True)
        ]
        + [
            {
                "location": "x",
                "variable": "t2m_max",
                "time": "2026-01-04",
                "value": 99.0,
                "quality_flag": "fail",
            }
        ],
        source="era5",
    )
    ghcn = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": t, "value": v}
            for t, v in zip(times, [30.0, 30.0, 30.0], strict=True)
        ],
        source="ghcn",
    )

    table = compare(era5, ghcn, source_a="era5", source_b="ghcn")
    row = table.iloc[0]
    assert row["n_days"] == 3  # the fail row never joins
    assert row["bias"] == 2.0
    assert row["mae"] == 2.0
    assert row["rmse"] == pytest.approx((14 / 3) ** 0.5)
    assert row["mean_era5"] == 32.0
    assert row["mean_ghcn"] == 30.0


def test_compare_flags_large_temperature_bias() -> None:
    times = ["2026-01-01", "2026-01-02", "2026-01-03"]
    era5 = _frame(
        [{"location": "x", "variable": "t2m_max", "time": t, "value": 40.0} for t in times],
        source="era5",
    )
    ghcn = _frame(
        [{"location": "x", "variable": "t2m_max", "time": t, "value": 30.0} for t in times],
        source="ghcn",
    )
    table = compare(era5, ghcn, source_a="era5", source_b="ghcn")
    assert "|bias| >= 3 C" in table.iloc[0]["flags"]


def test_compare_reports_precip_total_ratio() -> None:
    times = ["2026-01-01", "2026-01-02"]
    era5 = _frame(
        [
            {"location": "x", "variable": "precip", "time": t, "value": v, "unit": "mm"}
            for t, v in zip(times, [10.0, 10.0], strict=True)
        ],
        source="era5",
    )
    ghcn = _frame(
        [
            {"location": "x", "variable": "precip", "time": t, "value": v, "unit": "mm"}
            for t, v in zip(times, [1.0, 1.0], strict=True)
        ],
        source="ghcn",
    )
    table = compare(era5, ghcn, source_a="era5", source_b="ghcn")
    row = table.iloc[0]
    assert row["ratio_era5_over_ghcn"] == 10.0
    assert "total ratio outside" in row["flags"]


def test_compare_rejects_disjoint_frames() -> None:
    era5 = _frame(
        [{"location": "x", "variable": "t2m_max", "time": "2026-01-01", "value": 30.0}],
        source="era5",
    )
    ghcn = _frame(
        [{"location": "y", "variable": "t2m_max", "time": "2026-01-01", "value": 30.0}],
        source="ghcn",
    )
    try:
        compare(era5, ghcn, source_a="era5", source_b="ghcn")
    except ValueError as exc:
        assert "no overlapping rows" in str(exc)
    else:  # pragma: no cover - the raise is the expected path
        raise AssertionError("expected ValueError")


def test_render_markdown_contains_table_and_flags() -> None:
    era5 = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": t, "value": 35.0}
            for t in ["2026-01-01", "2026-01-02", "2026-01-03"]
        ],
        source="era5",
    )
    ghcn = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": t, "value": 30.0}
            for t in ["2026-01-01", "2026-01-02", "2026-01-03"]
        ],
        source="ghcn",
    )
    table = compare(era5, ghcn, source_a="era5", source_b="ghcn")
    report = render_markdown(
        table,
        source_a="era5",
        source_b="ghcn",
        period_start=pd.Timestamp("2026-01-01"),
        period_end=pd.Timestamp("2026-01-03"),
        generated_at=pd.Timestamp("2026-11-11"),
    )
    assert "# Source discrepancy report — era5 vs ghcn" in report
    assert "| location |" in report
    assert "What this does not show" in report
    assert "**x / t2m_max**" in report
    assert "15-day maturity gate" in report


REGION = {
    "id": "toy",
    "timezone": "America/Argentina/Cordoba",
    "stations": [
        {
            "id": "salta",
            "name": "Salta Aero",
            "lat": -24.85,
            "lon": -65.483,
            "elevation_m": 1246,
        },
        {
            "id": "ushuaia",
            "name": "Ushuaia Malvinas Argentinas",
            "lat": -54.843,
            "lon": -68.296,
            "elevation_m": 22,
        },
    ],
}


def _pair_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    times = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
    era5 = _frame(
        [
            {
                "location": "Salta Aero",
                "variable": variable,
                "time": t,
                "value": value,
                "unit": unit,
            }
            for variable, unit, values in (
                ("t2m_max", "degC", [33.0, 34.0, 35.0, 36.0, 37.0]),
                ("precip", "mm", [5.0, 5.0, 5.0, 5.0, 5.0]),
            )
            for t, value in zip(times, values, strict=True)
        ]
        + [
            {
                "location": "Ushuaia Malvinas Argentinas",
                "variable": variable,
                "time": t,
                "value": value,
                "unit": unit,
            }
            for variable, unit, values in (
                ("t2m_max", "degC", [10.0, 11.0, 12.0, 13.0, 14.0]),
                ("precip", "mm", [2.0, 2.0, 2.0, 2.0, 2.0]),
            )
            for t, value in zip(times, values, strict=True)
        ],
        source="era5",
    )
    ghcn = _frame(
        [
            {
                "location": "Salta Aero",
                "variable": variable,
                "time": t,
                "value": value,
                "unit": unit,
            }
            for variable, unit, values in (
                ("t2m_max", "degC", [30.0, 31.0, 32.0, 33.0, 34.0]),
                ("precip", "mm", [2.0, 2.0, 2.0, 2.0, 2.0]),
            )
            for t, value in zip(times, values, strict=True)
        ]
        + [
            {
                "location": "Ushuaia Malvinas Argentinas",
                "variable": variable,
                "time": t,
                "value": value,
                "unit": unit,
            }
            for variable, unit, values in (
                ("t2m_max", "degC", [12.0, 13.0, 14.0, 15.0, 16.0]),
                ("precip", "mm", [1.0, 1.0, 1.0, 1.0, 1.0]),
            )
            for t, value in zip(times, values, strict=True)
        ],
        source="ghcn",
    )
    return era5, ghcn


def test_collect_t2m_max_decomposition_runs_both_tracks() -> None:
    era5, ghcn = _pair_frames()
    calls = {"dem": 0, "raw": 0, "hourly": 0}

    def fake_dem_elev(lat: float, lon: float, *, timezone: str) -> float:
        calls["dem"] += 1
        return 1240.0 if lat > -30 else 30.0

    def fake_raw_grid(
        lat: float,
        lon: float,
        start: str,
        end: str,
        *,
        timezone: str,
        pause_seconds: float = 0.0,
    ) -> tuple[pd.Series, float | None]:
        calls["raw"] += 1
        # Raw grid is 1 °C colder than the stored (downscaled) series.
        offset = -1.0 if lat > -30 else -2.0
        base = [33.0, 34.0, 35.0, 36.0, 37.0] if lat > -30 else [10.0, 11.0, 12.0, 13.0, 14.0]
        index = pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
        )
        series = pd.Series([v + offset for v in base], index=index)
        grid = 1500.0 if lat > -30 else 400.0
        return series, grid

    def fake_hourly(
        lat: float,
        lon: float,
        start: str,
        end: str,
        *,
        timezone: str,
        pause_seconds: float = 0.0,
    ) -> pd.DataFrame:
        calls["hourly"] += 1
        times = pd.to_datetime(
            ["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 12:00", "2026-01-01 13:00"]
        )
        return pd.DataFrame({"time": times, "value": [18.0, 21.0, 21.0, 18.0]})

    table = collect_t2m_max_decomposition(
        era5,
        ghcn,
        {"id": "toy", "history_start": "2026-01-01", **REGION},
        fetch_dem_elev=fake_dem_elev,
        fetch_raw_grid=fake_raw_grid,
        fetch_hourly=fake_hourly,
        pause_seconds=0.0,
    )
    # 2 stations × 2 tracks (downscaled + raw_grid).
    assert len(table) == 4
    assert set(table["series"]) == {"downscaled", "raw_grid"}
    assert calls == {"dem": 2, "raw": 2, "hourly": 2}

    salta_ds = table.loc[
        table["location"].eq("Salta Aero") & table["series"].eq("downscaled")
    ].iloc[0]
    # Stored bias 3 °C; DEM 1240 vs station 1246 → −0.039 °C lapse correction.
    assert salta_ds["bias_raw"] == pytest.approx(3.0)
    assert salta_ds["source_elevation_m"] == pytest.approx(1240.0)
    assert salta_ds["bias_after_elevation"] == pytest.approx(3.0 + 6.5 * (1240 - 1246) / 1000.0)

    salta_raw = table.loc[
        table["location"].eq("Salta Aero") & table["series"].eq("raw_grid")
    ].iloc[0]
    # Raw grid series 1 °C colder → bias 2 °C; grid 1500 vs station 1246 → +1.651.
    assert salta_raw["bias_raw"] == pytest.approx(2.0)
    assert salta_raw["source_elevation_m"] == pytest.approx(1500.0)
    assert salta_raw["grid_elevation_m"] == pytest.approx(1500.0)
    assert salta_raw["dem_elevation_m"] == pytest.approx(1240.0)
    assert salta_raw["bias_after_elevation"] == pytest.approx(2.0 + 6.5 * (1500 - 1246) / 1000.0)
    assert salta_raw["sampling_correction_c"] == pytest.approx(0.375)
    assert set(table["status"]) == {"ok"}
    assert (table["exclusion_reason"] == "").all()


def test_collect_excludes_water_masked_raw_grid_track() -> None:
    era5, ghcn = _pair_frames()

    def fake_dem_elev(lat: float, lon: float, *, timezone: str) -> float:
        return 1240.0 if lat > -30 else 30.0

    def fake_raw_grid(
        lat: float,
        lon: float,
        start: str,
        end: str,
        *,
        timezone: str,
        pause_seconds: float = 0.0,
    ) -> tuple[pd.Series, float | None]:
        # Ushuaia's cell comes back water-masked at 0.0 m.
        grid = 1500.0 if lat > -30 else 0.0
        base = [33.0, 34.0, 35.0, 36.0, 37.0] if lat > -30 else [10.0, 11.0, 12.0, 13.0, 14.0]
        index = pd.to_datetime(
            ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]
        )
        return pd.Series(base, index=index), grid

    def fake_hourly(
        lat: float,
        lon: float,
        start: str,
        end: str,
        *,
        timezone: str,
        pause_seconds: float = 0.0,
    ) -> pd.DataFrame:
        times = pd.to_datetime(
            ["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 12:00", "2026-01-01 13:00"]
        )
        return pd.DataFrame({"time": times, "value": [18.0, 21.0, 21.0, 18.0]})

    table = collect_t2m_max_decomposition(
        era5,
        ghcn,
        {"id": "toy", "history_start": "2026-01-01", **REGION},
        fetch_dem_elev=fake_dem_elev,
        fetch_raw_grid=fake_raw_grid,
        fetch_hourly=fake_hourly,
        pause_seconds=0.0,
    )
    excluded = table.loc[table["status"].eq("excluded")]
    assert len(excluded) == 1
    row = excluded.iloc[0]
    assert row["series"] == "raw_grid"
    assert row["location"] == "Ushuaia Malvinas Argentinas"
    assert "water-masked" in row["exclusion_reason"]
    assert "0.0 m" in row["exclusion_reason"]
    included = table.loc[table["status"].eq("ok")]
    assert len(included) == 3


def _t2m_pair_rows() -> list[dict]:
    def rows(location: str, ds_raw: float, raw_final: float) -> list[dict]:
        raw_status = "excluded" if raw_final != ds_raw else "ok"
        common = {
            "location": location,
            "n_days": 5,
            "best_day_lag": 0,
            "dem_elevation_m": 1240.0,
            "station_elevation_m": 22.0,
            "sampling_correction_c": 0.05,
            "sample_window": "2026-01-01..2026-01-21",
            "lag_mae": 0.1,
        }
        downscaled = {
            **common,
            "series": "downscaled",
            "status": "ok",
            "bias_raw": ds_raw,
            "bias_after_elevation": ds_raw,
            "bias_after_sampling": ds_raw,
            "bias_after_day_convention": ds_raw,
            "source_elevation_m": 1240.0,
            "grid_elevation_m": 1500.0,
            "elevation_diff_m": -6.0,
            "exclusion_reason": "",
        }
        raw_grid = {
            **common,
            "series": "raw_grid",
            "status": raw_status,
            "bias_raw": ds_raw + 0.1,
            "bias_after_elevation": ds_raw + 0.1,
            "bias_after_sampling": ds_raw + 0.1,
            "bias_after_day_convention": raw_final,
            "source_elevation_m": 0.0 if raw_status == "excluded" else 1240.0,
            "grid_elevation_m": 0.0 if raw_status == "excluded" else 1500.0,
            "elevation_diff_m": -22.0 if raw_status == "excluded" else -6.0,
            "exclusion_reason": (
                "elevation=nan returned grid-cell elevation 0.0 m: water-masked cell"
                if raw_status == "excluded"
                else ""
            ),
        }
        return [downscaled, raw_grid]

    return rows("Salta Aero", -2.9, -2.9) + rows("Mar del Plata Aero", -1.97, -3.66)


def test_render_excluded_track_and_exception_lines() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())
    precip = pd.DataFrame(
        columns=[
            "location",
            "n_days",
            "precip_ratio_era5_over_station",
            "grid_elevation_m",
            "station_elevation_m",
            "elevation_diff_m",
            "note",
        ]
    )
    section = render_decomposition_section(t2m, precip, None)
    assert "Excluded from track means" in section
    assert "water-masked cell" in section
    assert "Track convergence: at all 1 location(s)" in section
    assert "Exception: raw_grid at Mar del Plata Aero" in section
    assert "Δ -1.69 °C" in section
    assert "not averaged in" in section
    # Means must be computed without the excluded row: raw_grid n=1, not 2.
    assert "**raw_grid** (n=1 stations; 1 excluded)" in section
    assert "**downscaled** (n=2 stations)" in section


def test_collect_precip_orography_salta_and_ushuaia() -> None:
    era5, ghcn = _pair_frames()

    def fake_elevation(lat: float, lon: float, *, timezone: str) -> float:
        return 1500.0 if lat > -30 else 50.0

    table = collect_precip_orography(
        era5,
        ghcn,
        REGION,
        fetch_elevation=fake_elevation,
        pause_seconds=0.0,
    )
    assert list(table["location"]) == ["Salta Aero", "Ushuaia Malvinas Argentinas"]
    salta = table.loc[table["location"] == "Salta Aero"].iloc[0]
    assert salta["precip_ratio_era5_over_station"] == pytest.approx(2.5)
    assert salta["elevation_diff_m"] == pytest.approx(1500.0 - 1246.0)
    assert "orographic enhancement" in salta["note"]
    ushuaia = table.loc[table["location"] == "Ushuaia Malvinas Argentinas"].iloc[0]
    assert ushuaia["precip_ratio_era5_over_station"] == pytest.approx(2.0)
    assert ushuaia["elevation_diff_m"] == pytest.approx(50.0 - 22.0)


def test_render_decomposition_section_lists_residuals() -> None:
    t2m = pd.DataFrame(
        [
            {
                "series": "raw_grid",
                "location": "Salta Aero",
                "n_days": 5,
                "bias_raw": 3.0,
                "bias_after_elevation": 4.6,
                "bias_after_sampling": 4.98,
                "bias_after_day_convention": -4.9,
                "best_day_lag": 0,
                "source_elevation_m": 1500.0,
                "dem_elevation_m": 1240.0,
                "grid_elevation_m": 1500.0,
                "station_elevation_m": 1246.0,
                "elevation_diff_m": 254.0,
                "sampling_correction_c": 0.38,
                "sample_window": "2026-01-01..2026-01-21",
                "lag_mae": 1.2,
            }
        ]
    )
    precip = pd.DataFrame(
        [
            {
                "location": "Salta Aero",
                "n_days": 5,
                "precip_ratio_era5_over_station": 2.5,
                "grid_elevation_m": 1500.0,
                "station_elevation_m": 1246.0,
                "elevation_diff_m": 254.0,
                "note": "grid higher and wetter — orographic enhancement plausible",
            }
        ]
    )
    crosscheck = pd.DataFrame(
        [
            {
                "location": "Salta Aero",
                "flags": "",
                "matched_by": "nro",
                "smn_name": "SALTA AERO",
            }
        ]
    )
    section = render_decomposition_section(t2m, precip, crosscheck)
    assert "Bias decomposition — t2m_max" in section
    assert "bias_after_elevation" in section
    assert "raw_grid" in section
    assert "downscaled" in section
    assert "elevation=nan" in section
    assert "Limitation of step 3" in section
    assert "not re-estimated per season" in section
    assert "Orography check — precip" in section
    assert "orographic enhancement" in section
    assert "Station cross-check" in section
    assert "Honest reading" in section
    assert "observed ERA5 bias" in section
    assert "no causal claim" in section


def test_render_decomposition_section_empty_tables() -> None:
    section = render_decomposition_section(
        pd.DataFrame(columns=["location"]),
        pd.DataFrame(columns=["location"]),
    )
    assert "decomposition skipped" in section
    assert "No overlapping precip" in section


def test_render_honest_reading_freshness_line() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())
    freshness = {
        "era5_last": pd.Timestamp("2026-11-05"),
        "ghcn_last": pd.Timestamp("2025-08-24"),
        "refreshed": pd.Timestamp("2026-11-11 09:44"),
        "as_of": pd.Timestamp("2026-11-11 19:00"),
    }
    reading = render_honest_reading(t2m, None, freshness=freshness)
    assert "Data freshness" in reading
    assert "ERA5 through 2026-11-05" in reading
    assert "GHCN through 2025-08-24" in reading
    assert "refreshed 2026-11-11" in reading
    assert "gap is on the GHCN side" in reading
    section = render_decomposition_section(
        t2m, pd.DataFrame(columns=["location"]), None, freshness=freshness
    )
    assert "Data freshness" in section

