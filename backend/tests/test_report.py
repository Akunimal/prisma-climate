"""Discrepancy report tests — no network access."""

from __future__ import annotations

import pandas as pd
import pytest

from prisma.report.discrepancies import (
    collect_precip_orography,
    collect_t2m_max_decomposition,
    compare,
    render_decomposition_section,
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


def test_collect_t2m_max_decomposition_uses_injected_fetchers() -> None:
    era5, ghcn = _pair_frames()
    calls = {"elev": 0, "hourly": 0}

    def fake_elevation(lat: float, lon: float, *, timezone: str) -> float:
        calls["elev"] += 1
        return 1000.0

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
        # Local max undersampled by hourly values → positive correction.
        times = pd.to_datetime(
            ["2026-01-01 10:00", "2026-01-01 11:00", "2026-01-01 12:00", "2026-01-01 13:00"]
        )
        return pd.DataFrame({"time": times, "value": [18.0, 21.0, 21.0, 18.0]})

    table = collect_t2m_max_decomposition(
        era5,
        ghcn,
        REGION,
        fetch_elevation=fake_elevation,
        fetch_hourly=fake_hourly,
        pause_seconds=0.0,
    )
    assert len(table) == 2
    assert calls["elev"] == 2
    assert calls["hourly"] == 2
    salta = table.loc[table["location"] == "Salta Aero"].iloc[0]
    assert salta["bias_raw"] == pytest.approx(3.0)
    # Grid and station elevations both 1000 in this toy region… station is 1246.
    # elevation_diff = 1000 - 1246 = -246 → +6.5 * 0.246 = +1.6 → bias_after_elev ≈ 4.6
    assert salta["bias_after_elevation"] == pytest.approx(3.0 + 6.5 * (1000 - 1246) / 1000.0)
    assert salta["sampling_correction_c"] == pytest.approx(0.375)
    assert salta["bias_after_sampling"] == pytest.approx(
        3.0 + 6.5 * (1000 - 1246) / 1000.0 + 0.375
    )
    assert salta["bias_after_day_convention"] is not None


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
                "location": "Salta Aero",
                "n_days": 5,
                "bias_raw": 3.0,
                "bias_after_elevation": 4.6,
                "bias_after_sampling": 4.98,
                "bias_after_day_convention": 4.9,
                "best_day_lag": 0,
                "grid_elevation_m": 1000.0,
                "station_elevation_m": 1246.0,
                "elevation_diff_m": -246.0,
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
    section = render_decomposition_section(t2m, precip)
    assert "Bias decomposition — t2m_max" in section
    assert "bias_after_elevation" in section
    assert "Orography check — precip" in section
    assert "orographic enhancement" in section


def test_render_decomposition_section_empty_tables() -> None:
    section = render_decomposition_section(
        pd.DataFrame(columns=["location"]),
        pd.DataFrame(columns=["location"]),
    )
    assert "decomposition skipped" in section
    assert "No overlapping precip" in section

