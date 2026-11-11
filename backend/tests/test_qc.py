"""QC rule tests — no network access."""

from __future__ import annotations

import pandas as pd

from prisma.qc.rules import apply_qc, station_status, summary


def _frame(rows: list[dict]) -> pd.DataFrame:
    base = {
        "source": "test",
        "member": pd.NA,
        "lead_day": pd.NA,
        "model": pd.NA,
        "quality_flag": "ok",
    }
    return pd.DataFrame([{**base, **row} for row in rows])


def test_physical_limits_flag_out_of_range_values() -> None:
    frame = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": "2026-01-01", "value": 30.0},
            {"location": "x", "variable": "t2m_max", "time": "2026-01-02", "value": 99.0},
            {"location": "x", "variable": "precip", "time": "2026-01-01", "value": -5.0},
            {"location": "x", "variable": "precip", "time": "2026-01-02", "value": 12.0},
        ]
    )
    out = apply_qc(frame)
    assert out.loc[out["time"] == "2026-01-01", "quality_flag"].iloc[0] == "ok"
    assert out.loc[out["value"] == 99.0, "quality_flag"].item() == "fail"
    assert out.loc[out["value"] == -5.0, "quality_flag"].item() == "fail"
    assert out.loc[out["value"] == 12.0, "quality_flag"].item() == "ok"


def test_duplicates_keep_last_row() -> None:
    frame = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": "2026-01-01", "value": 1.0},
            {"location": "x", "variable": "t2m_max", "time": "2026-01-01", "value": 2.0},
        ]
    )
    out = apply_qc(frame)
    assert len(out) == 1
    assert out["value"].item() == 2.0


def test_spike_against_centred_median_is_suspect() -> None:
    # Spike stays inside the physical limit for t2m_max (-45..55) so the
    # spike rule, not the limit rule, is what flags the row.
    times = pd.date_range("2026-01-01", periods=9, freq="D")
    values = [30.0] * 4 + [50.0] + [30.0] * 4
    frame = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": t, "value": v}
            for t, v in zip(times, values, strict=True)
        ]
    )
    out = apply_qc(frame).sort_values("time")
    assert out["quality_flag"].tolist()[4] == "suspect"
    assert out["quality_flag"].tolist().count("suspect") == 1


def test_station_status_flags_stale_stations() -> None:
    frame = pd.DataFrame(
        {
            "source": ["ghcn-daily", "ghcn-daily"],
            "location": ["fresh", "stale"],
            "time": pd.to_datetime(["2026-10-15", "2026-01-01"]),
            "quality_flag": ["ok", "ok"],
        }
    )
    status = station_status(frame, as_of="2026-11-11").set_index("location")
    assert bool(status.loc["fresh", "stale"]) is False
    assert bool(status.loc["stale", "stale"]) is True


def test_summary_counts_flags_per_source_variable() -> None:
    frame = _frame(
        [
            {"location": "x", "variable": "t2m_max", "time": "2026-01-01", "value": 30.0},
            {"location": "x", "variable": "t2m_max", "time": "2026-01-02", "value": 99.0},
        ]
    )
    out = apply_qc(frame)
    table = summary(out)
    row = table.loc[table["variable"] == "t2m_max"].iloc[0]
    assert row["ok"] == 1
    assert row["fail"] == 1
    assert row["total"] == 2
