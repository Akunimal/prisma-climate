"""Tests for scripts/smn_era5_climatology_adjustment.py (frozen table)."""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "smn_era5_climatology_adjustment.py"
)


@pytest.fixture(scope="module")
def adj():
    spec = importlib.util.spec_from_file_location("smn_era5_climatology_adjustment", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["smn_era5_climatology_adjustment"] = module
    spec.loader.exec_module(module)
    return module


def _frame(rows: list[tuple[str, str, str, float, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        rows, columns=["location", "variable", "time", "value", "quality_flag"]
    )


def test_pair_respects_window_and_quality_flag(adj) -> None:
    smn = _frame(
        [
            ("A", "t2m_max", "2025-11-10", 30.0, "ok"),  # before the window
            ("A", "t2m_max", "2025-11-11", 31.0, "ok"),
            ("A", "t2m_max", "2026-11-10", 29.0, "ok"),  # window edge
            ("A", "t2m_max", "2026-11-11", 28.0, "ok"),  # after the window
            ("A", "t2m_max", "2025-12-01", 33.0, "suspect"),  # not ok
        ]
    )
    era5 = _frame(
        [
            ("A", "t2m_max", "2025-11-11", 32.0, "ok"),
            ("A", "t2m_max", "2026-11-10", 30.0, "ok"),
            ("A", "t2m_max", "2025-12-01", 34.0, "ok"),
        ]
    )
    paired = adj.pair_smn_era5(smn, era5)
    assert len(paired) == 2
    days = paired["time"].dt.strftime("%Y-%m-%d")
    values = dict(zip(days, paired["diff_smn_minus_era5"], strict=True))
    assert values == {"2025-11-11": -1.0, "2026-11-10": -1.0}


def test_table_full_grid_fallback_and_basis(adj) -> None:
    rows: list[tuple[str, str, str, float]] = []
    for day in range(1, 26):  # 25 paired days, diff = +1
        rows.append(("A", "t2m_max", f"2026-01-{day:02d}", 1.0))
    for day in range(1, 6):  # 5 paired days, diff = +3 -> fallback
        rows.append(("A", "t2m_max", f"2026-02-{day:02d}", 3.0))
    paired = pd.DataFrame(
        rows, columns=["location", "variable", "time", "diff_smn_minus_era5"]
    )
    paired["time"] = pd.to_datetime(paired["time"])
    table = adj.adjustment_table(paired)

    jan = table.loc[
        table["variable"].eq("t2m_max") & table["calendar_month"].eq(1)
    ].iloc[0]
    assert int(jan["n_paired_days"]) == 25
    assert not bool(jan["used_fallback"])
    assert jan["basis"] == "station_calendar_month"
    assert jan["mean_diff_smn_minus_era5"] == pytest.approx(1.0)

    pooled = (25 * 1.0 + 5 * 3.0) / 30
    feb = table.loc[
        table["variable"].eq("t2m_max") & table["calendar_month"].eq(2)
    ].iloc[0]
    assert int(feb["n_paired_days"]) == 5
    assert bool(feb["used_fallback"])
    assert feb["basis"] == "station_all_months"
    assert feb["mean_diff_smn_minus_era5"] == pytest.approx(pooled)

    # A month with zero paired days is a visible fallback row, not missing.
    assert len(table) == 12
    mar = table.loc[table["calendar_month"].eq(3)].iloc[0]
    assert int(mar["n_paired_days"]) == 0
    assert bool(mar["used_fallback"])
    assert mar["mean_diff_smn_minus_era5"] == pytest.approx(pooled)


def test_table_requires_some_pairs_per_station_variable(adj) -> None:
    paired = pd.DataFrame(
        columns=["location", "variable", "time", "diff_smn_minus_era5"]
    )
    with pytest.raises(ValueError, match="no paired"):
        adj.adjustment_table(paired)


def test_markdown_lists_provenance_fallback_and_freeze(adj) -> None:
    paired = pd.DataFrame(
        {
            "location": ["A"] * 25,
            "variable": ["t2m_max"] * 25,
            "time": pd.to_datetime([f"2026-01-{d:02d}" for d in range(1, 26)]),
            "diff_smn_minus_era5": [1.0] * 25,
        }
    )
    table = adj.adjustment_table(paired)
    text = adj.render_markdown(
        table,
        paired,
        {"data/x.txt": "abc123"},
        (adj.WINDOW_START, adj.WINDOW_END),
        datetime(2026, 11, 13, 22, 0, 0),
    )
    assert "Frozen by the 2026-11-13 amendment" in text
    assert "| `data/x.txt` | `abc123` |" in text
    assert "Cells using the fallback" in text
    # 11 of 12 months are fallbacks for this one-month station.
    assert text.count("station_all_months |") >= 11 or "| A | t2m_max | 2 |" in text
    assert "about 30 days" in text


def test_main_refuses_to_overwrite_frozen_table(adj, tmp_path: Path) -> None:
    frozen = tmp_path / "smn_era5_adjustment.csv"
    frozen.write_text("location,variable,calendar_month\n", encoding="utf-8")
    assert adj.main(["--out-dir", str(tmp_path)]) == 1
    assert frozen.read_text(encoding="utf-8") == (
        "location,variable,calendar_month\n"
    )
