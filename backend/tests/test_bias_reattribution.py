"""Bias re-attribution tests (T26a 1.1–1.3) — fixture-based, no network."""

from __future__ import annotations

import pandas as pd
import pytest

from prisma.report.bias_reattribution import (
    build_reattribution,
    leg_table,
    matched_calendar_table,
    overlap_days,
    pair_era5_station,
    per_year_bias,
    render_markdown,
)


def _rows(*entries: tuple[str, str, str, str, float]) -> pd.DataFrame:
    """(location, variable, time, source_key, value) with quality ok."""
    return pd.DataFrame.from_records(
        [
            {
                "location": location,
                "variable": variable,
                "time": pd.Timestamp(day),
                "value": value,
                "quality_flag": "ok",
            }
            for location, variable, day, _source, value in entries
        ]
    )


ERA5 = _rows(
    ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "era5", 28.0),
    ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "era5", 30.0),
    ("Buenos Aires Observatorio", "t2m_min", "2026-01-01", "era5", 19.0),
    ("Buenos Aires Observatorio", "t2m_min", "2026-01-02", "era5", 21.0),
    ("Buenos Aires Observatorio", "t2m_max", "2025-01-01", "era5", 32.0),
    ("Buenos Aires Observatorio", "t2m_max", "2024-12-01", "era5", 30.0),
)


def test_leg_bias_sign_is_era5_minus_station() -> None:
    station = _rows(
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "s", 30.0),
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "s", 34.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-01", "s", 18.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-02", "s", 22.0),
    )
    leg = leg_table(pair_era5_station(ERA5, station, "x"))
    tmax = leg.loc[leg["variable"].eq("t2m_max")].iloc[0]
    # ERA5 mean 29 vs station 32 → ERA5 − station = −3.
    assert tmax["bias_era5_minus_station"] == pytest.approx(-3.0)
    assert tmax["n_days"] == 2
    assert tmax["first_day"] == "2026-01-01"
    assert tmax["last_day"] == "2026-01-02"
    assert "|bias| >= 3 C" in tmax["flags"]


def test_reattribution_flips_smn_sign_and_computes_diff() -> None:
    # Committed smn_vs_era5 stores SMN − ERA5 = +2 (SMN warmer); here the
    # inputs are already paired frames, so feed ERA5 − station directly and
    # check the diff column.
    ghcn_leg = leg_table(
        pair_era5_station(
            ERA5,
            _rows(
                ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "g", 27.0),
                ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "g", 29.0),
            ),
            "ghcn",
        )
    )
    smn_leg = leg_table(
        pair_era5_station(
            ERA5,
            _rows(
                ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "s", 30.0),
                ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "s", 34.0),
            ),
            "smn",
        )
    )
    table = build_reattribution(ghcn_leg, smn_leg)
    row = table.loc[table["variable"].eq("t2m_max")].iloc[0]
    assert row["bias_era5_minus_ghcn"] == pytest.approx(1.0)  # 29 − 28... mean
    assert row["bias_era5_minus_smn"] == pytest.approx(-3.0)
    assert row["bias_diff_ghcn_minus_smn"] == pytest.approx(4.0)


def test_per_year_bias_groups_by_calendar_year() -> None:
    paired = pair_era5_station(
        ERA5,
        _rows(
            ("Buenos Aires Observatorio", "t2m_max", "2024-12-01", "g", 26.0),
            ("Buenos Aires Observatorio", "t2m_max", "2025-01-01", "g", 28.0),
        ),
        "ghcn",
    )
    table = per_year_bias(paired)
    assert list(table["year"]) == [2024, 2025]
    assert table.loc[table["year"].eq(2024), "bias_era5_minus_ghcn"].iloc[0] == pytest.approx(4.0)
    assert table.loc[table["year"].eq(2025), "bias_era5_minus_ghcn"].iloc[0] == pytest.approx(4.0)
    assert int(table["n_days"].sum()) == 2  # t2m_min rows excluded


def test_matched_calendar_filters_each_leg_to_its_window() -> None:
    paired_ghcn = pair_era5_station(
        ERA5,
        _rows(
            ("Buenos Aires Observatorio", "t2m_max", "2024-12-01", "g", 26.0),  # in
            ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "g", 20.0),  # out
        ),
        "ghcn",
    )
    paired_smn = pair_era5_station(
        ERA5,
        _rows(
            ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "s", 26.0),  # in
            ("Buenos Aires Observatorio", "t2m_max", "2024-12-01", "s", 10.0),  # out
        ),
        "smn",
    )
    table = matched_calendar_table(
        paired_ghcn,
        paired_smn,
        ghcn_window=("2024-11-11", "2025-08-24"),
        smn_window=("2025-11-11", "2026-08-24"),
    )
    row = table.loc[table["variable"].eq("t2m_max")].iloc[0]
    assert row["n_days_ghcn"] == 1  # 2024-12-01 only; 2026-01-01 excluded
    assert row["n_days_smn"] == 1  # 2026-01-01 only; 2024-12-01 excluded
    assert row["bias_era5_minus_ghcn"] == pytest.approx(4.0)  # 30 − 26
    assert row["bias_era5_minus_smn"] == pytest.approx(2.0)  # 28 − 26
    assert row["bias_diff_ghcn_minus_smn"] == pytest.approx(2.0)
    assert row["ghcn_window"] == "2024-11-11..2025-08-24"
    assert row["smn_window"] == "2025-11-11..2026-08-24"


def test_overlap_days_zero_when_windows_disjoint() -> None:
    paired_ghcn = pair_era5_station(
        ERA5,
        _rows(("Buenos Aires Observatorio", "t2m_max", "2025-01-01", "g", 30.0)),
        "ghcn",
    )
    paired_smn = pair_era5_station(
        ERA5,
        _rows(("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "s", 30.0)),
        "smn",
    )
    assert overlap_days(paired_ghcn, paired_smn) == 0
    overlapping = pair_era5_station(
        ERA5,
        _rows(("Buenos Aires Observatorio", "t2m_max", "2025-01-01", "s", 30.0)),
        "smn",
    )
    assert overlap_days(paired_ghcn, overlapping) == 1


def test_markdown_declares_confounder_and_sign_convention() -> None:
    station = _rows(
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "g", 27.0),
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "g", 29.0),
    )
    paired_ghcn = pair_era5_station(ERA5, station, "ghcn")
    paired_smn = pair_era5_station(
        ERA5,
        _rows(
            ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", "s", 30.0),
            ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", "s", 34.0),
        ),
        "smn",
    )
    ghcn_leg = leg_table(paired_ghcn)
    smn_leg = leg_table(paired_smn)
    table = build_reattribution(ghcn_leg, smn_leg)
    years = per_year_bias(paired_ghcn)
    matched = matched_calendar_table(paired_ghcn, paired_smn)
    md = render_markdown(
        table,
        years,
        matched,
        shared_days=0,
        generated_at=pd.Timestamp("2026-11-13 15:00:00"),
    )
    assert "ERA5 − station" in md
    assert "period confounder" in md
    assert "Station-days present in **both** legs: **0**" in md
    assert "matched-calendar adjacent" in md
    assert "bias_era5_minus_ghcn" in md  # sign columns visible


def test_leg_table_empty_returns_schema() -> None:
    empty = leg_table(pd.DataFrame(columns=["location", "variable", "time", "era5", "station"]))
    assert "bias_era5_minus_station" in empty.columns
    assert len(empty) == 0
