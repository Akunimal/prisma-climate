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
    assert "15-issue-date gate" in report
    assert "diagnostics, not skill metrics" in report


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
    assert "Correction (" not in reading  # legacy call: no reattribution passed
    section = render_decomposition_section(
        t2m, pd.DataFrame(columns=["location"]), None, freshness=freshness
    )
    assert "Data freshness" in section


def _reattribution_fixture() -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "location": "Salta Aero",
                "variable": "t2m_max",
                "n_days_ghcn": 5659,
                "first_day_ghcn": "1996-01-01",
                "last_day_ghcn": "2025-08-24",
                "bias_era5_minus_ghcn": -3.4,
                "corr_ghcn": 0.95,
                "mean_era5_ghcn": 20.0,
                "mean_ghcn": 23.4,
                "flags_ghcn": "|bias| >= 3 C",
                "n_days_smn": 360,
                "first_day_smn": "2025-11-11",
                "last_day_smn": "2026-11-05",
                "bias_era5_minus_smn": -1.0,
                "corr_smn": 0.99,
                "mean_era5_smn": 21.0,
                "mean_smn": 22.0,
                "flags_smn": "",
            },
            {
                "location": "Salta Aero",
                "variable": "t2m_min",
                "n_days_ghcn": 7853,
                "first_day_ghcn": "1996-01-01",
                "last_day_ghcn": "2025-08-24",
                "bias_era5_minus_ghcn": 1.2,
                "corr_ghcn": 0.97,
                "mean_era5_ghcn": 12.0,
                "mean_ghcn": 10.8,
                "flags_ghcn": "",
                "n_days_smn": 360,
                "first_day_smn": "2025-11-11",
                "last_day_smn": "2026-11-05",
                "bias_era5_minus_smn": 0.7,
                "corr_smn": 0.98,
                "mean_era5_smn": 12.5,
                "mean_smn": 11.8,
                "flags_smn": "",
            },
        ]
    )


def test_honest_reading_leg_dependence_correction() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())  # finals mean < -0.5 → cold-bias branch
    reading = render_honest_reading(
        t2m, None, reattribution=_reattribution_fixture(), shared_days=0
    )
    assert "The residual cold bias persists" in reading  # original finding kept
    assert "**Correction (2026-11-13):**" in reading
    assert "leg-dependent" in reading
    assert "1996-01-01 → 2025-08-24" in reading
    assert "2025-11-11 → 2026-11-05" in reading
    assert "averages -3.40 °C on t2m_max with 1/1 stations" in reading
    assert "averages -1.00 °C with 0/1" in reading
    assert "share **0** station-days" in reading
    assert "period-confounded" in reading
    assert "none is asserted here as the cause" in reading
    assert "bias_matched_calendar.csv" in reading


def test_honest_reading_correction_skipped_without_smn_leg() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())
    table = _reattribution_fixture()
    table["bias_era5_minus_smn"] = float("nan")
    reading = render_honest_reading(t2m, None, reattribution=table, shared_days=0)
    assert "Correction (" not in reading
    # No SMN leg → correction omitted, but original finding still present.
    assert "The residual cold bias persists" in reading


def test_decomposition_section_passes_correction_through() -> None:
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
    section = render_decomposition_section(
        t2m,
        precip,
        None,
        reattribution=_reattribution_fixture(),
        shared_days=0,
    )
    assert "**Correction (2026-11-13):**" in section
    without = render_decomposition_section(t2m, precip, None)
    assert "Correction (" not in without


def _per_year_fixture() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in range(1996, 2004):
        rows.append(
            {
                "location": "Salta Aero",
                "year": year,
                "n_days": 300,
                "bias_era5_minus_ghcn": -2.0,
                "first_day": f"{year}-01-01",
                "last_day": f"{year}-12-31",
            }
        )
    for year in range(2005, 2026):
        rows.append(
            {
                "location": "Salta Aero",
                "year": year,
                "n_days": 114 if year == 2025 else 180,
                "bias_era5_minus_ghcn": -3.5,
                "first_day": f"{year}-01-01",
                "last_day": f"{year}-12-31",
            }
        )
    return pd.DataFrame(rows)


def _matched_fixture() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for location, n_ghcn in (("Salta Aero", 120), ("Rosario", 150)):
        for variable in ("t2m_max", "t2m_min"):
            rows.append(
                {
                    "location": location,
                    "variable": variable,
                    "n_days_ghcn": n_ghcn,
                    "bias_era5_minus_ghcn": -3.5,
                    "corr_ghcn": 0.95,
                    "flags_ghcn": "|bias| >= 3 C",
                    "n_days_smn": 287,
                    "bias_era5_minus_smn": -1.0,
                    "corr_smn": 0.99,
                    "flags_smn": "",
                    "bias_diff_ghcn_minus_smn": -2.5,
                    "ghcn_window": "2024-11-11..2025-08-24",
                    "smn_window": "2025-11-11..2026-08-24",
                }
            )
    return pd.DataFrame(rows)


def test_honest_reading_controls_sentence() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())
    reading = render_honest_reading(
        t2m,
        None,
        reattribution=_reattribution_fixture(),
        shared_days=0,
        per_year=_per_year_fixture(),
        matched=_matched_fixture(),
    )
    assert "**Controls (2026-11-13):**" in reading
    assert "gap of -2.50 °C" in reading
    assert "-3.50 °C GHCN vs -1.00 °C SMN" in reading
    assert "GHCN more negative at 2/2 stations" in reading
    assert "120–150 of 287" in reading
    assert "from -2.00 °C (1996–2003) to -3.50 °C (2005–2025)" in reading
    assert "300.0 days in 2003 to 180.0 days in 2005" in reading
    assert "coincides with that coverage drop" in reading
    assert "114.0 days in 2025" in reading
    assert "pure daily-window shift cannot produce a ~2 °C mean bias" in reading
    assert "model-splice candidate is ruled out by the two-request check" in reading
    # The controls line reads as separate sentences, not one chained clause.
    controls_line = next(
        line for line in reading.splitlines() if line.startswith("- **Controls (")
    )
    assert controls_line.count("Independent") == 1
    assert controls_line.rstrip().endswith("stored series).")
    # Original correction bullet is still present and unchanged in substance.
    assert "**Correction (2026-11-13):**" in reading
    # Controls sentence needs both tables; without them it is omitted.
    reading_without = render_honest_reading(
        t2m, None, reattribution=_reattribution_fixture(), shared_days=0
    )
    assert "Controls (" not in reading_without


def _flag_bias_fixture() -> pd.DataFrame:
    rows = [
        ("all years", "G", 32477, -1.37603842719463),
        ("all years", "I", 51, -3.9549019607843134),
        ("all years", "S", 80821, -3.4457331634104995),
        ("1996-2003", "G", 30947, -1.3705948880343815),
        ("1996-2003", "I", 51, -3.9549019607843134),
        ("1996-2003", "S", 10882, -3.404429332843227),
        ("2004", "G", 1530, -1.4861437908496733),
        ("2004", "S", 2371, -3.4755377477857445),
        ("2005-2025", "S", 67568, -3.451339391427895),
    ]
    return pd.DataFrame(
        rows, columns=["period", "source_flag", "n_pairs", "mean_bias_era5_minus_ghcn"]
    )


def _flag_counts_fixture() -> pd.DataFrame:
    rows: list[tuple[str, int, str, str, int]] = []
    for year in range(1996, 2004):
        rows.append(("Station A", year, "1996-2003", "G", 74))
        rows.append(("Station A", year, "1996-2003", "S", 26))
    rows.append(("Station A", 2004, "2004", "G", 40))
    rows.append(("Station A", 2004, "2004", "S", 60))
    for year in range(2005, 2026):
        rows.append(("Station A", year, "2005-2025", "S", 100))
    return pd.DataFrame(
        rows, columns=["location", "year", "period", "source_flag", "n"]
    )


def test_honest_reading_source_flag_sentence() -> None:
    t2m = pd.DataFrame(_t2m_pair_rows())
    reading = render_honest_reading(
        t2m,
        None,
        reattribution=_reattribution_fixture(),
        shared_days=0,
        per_year=_per_year_fixture(),
        matched=_matched_fixture(),
        flag_bias=_flag_bias_fixture(),
        flag_counts=_flag_counts_fixture(),
    )
    assert "**Source-flag association (2026-11-13):**" in reading
    assert "113,349 paired TMAX days" in reading
    assert "averages -1.38 °C on G-flag values (n=32,477)" in reading
    assert "-3.45 °C on S-flag (GSOD-derived) values (n=80,821)" in reading
    assert "(n=32,477) and -3.45 °C" in reading, "the G-to-S join must be 'and', never 'y'"
    assert "G -1.49 to -1.37 °C; S -3.48 to -3.40 °C" in reading
    assert "100.0% S-flag from 2005 onward (G share 74.0% in 1996–2003" in reading
    assert "40.0% in 2004)" in reading
    assert "coincides with this G→S switch" in reading
    assert "SMN leg averages -1.00 °C" in reading
    assert "read as an association: the excess against GHCN is tied to GSOD-derived" in reading
    assert "mechanism not established" in reading
    # Without the audit tables the sentence is omitted, correction stays.
    reading_without = render_honest_reading(
        t2m, None, reattribution=_reattribution_fixture(), shared_days=0
    )
    assert "Source-flag association" not in reading_without
    assert "**Correction (2026-11-13):**" in reading_without

