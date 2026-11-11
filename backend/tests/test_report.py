"""Discrepancy report tests — no network access."""

from __future__ import annotations

import pandas as pd
import pytest

from prisma.report.discrepancies import compare, render_markdown


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
