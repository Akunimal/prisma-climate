"""Tests for scripts/issue_hour_distribution.py: bands, validation, outputs."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "issue_hour_distribution.py"


@pytest.fixture(scope="module")
def hours():
    spec = importlib.util.spec_from_file_location("issue_hour_distribution", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["issue_hour_distribution"] = module
    spec.loader.exec_module(module)
    return module


def _write_parquet(path: Path, issue_times: list[str], rows: int = 3) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "issue_time": pd.to_datetime(issue_times, utc=True),
            "value": [1.0] * len(issue_times),
        }
    ).head(rows)
    frame.to_parquet(path, index=False)
    return path


def test_band_boundaries(hours) -> None:
    assert hours.band_for_hour(0) == "00:00-11:59"
    assert hours.band_for_hour(11) == "00:00-11:59"
    assert hours.band_for_hour(12) == "12:00-23:59"
    assert hours.band_for_hour(23) == "12:00-23:59"


def test_band_rejects_out_of_range(hours) -> None:
    with pytest.raises(ValueError, match="out of range"):
        hours.band_for_hour(24)


def test_issue_stamp_reads_the_column_not_the_clock(hours, tmp_path: Path) -> None:
    path = _write_parquet(
        tmp_path / "openmeteo-ensemble_2026-11-11.parquet",
        ["2026-11-11 16:27:24"] * 3,
    )
    stamp, n_rows = hours.load_issue_stamp(path)
    assert stamp.strftime("%Y-%m-%d %H:%M:%S%z").startswith("2026-11-11 16:27:24")
    assert stamp.utcoffset().total_seconds() == 0
    assert n_rows == 3


def test_issue_stamp_rejects_mixed_cycles(hours, tmp_path: Path) -> None:
    path = _write_parquet(
        tmp_path / "a.parquet",
        ["2026-11-11 16:27:24", "2026-11-12 06:47:00", "2026-11-12 06:47:00"],
    )
    with pytest.raises(ValueError, match="single issue_time"):
        hours.load_issue_stamp(path)


def test_issue_stamp_requires_the_column(hours, tmp_path: Path) -> None:
    path = tmp_path / "a.parquet"
    pd.DataFrame({"value": [1.0]}).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="issue_time"):
        hours.load_issue_stamp(path)


def test_issue_stamp_rejects_nulls(hours, tmp_path: Path) -> None:
    path = tmp_path / "a.parquet"
    pd.DataFrame({"issue_time": [pd.NaT]}).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="nulls"):
        hours.load_issue_stamp(path)


def test_collect_covers_nested_forecasts_layout(hours, tmp_path: Path) -> None:
    _write_parquet(
        tmp_path / "forecasts" / "2026-11-11" / "openmeteo-ensemble_2026-11-11.parquet",
        ["2026-11-11 16:27:24"] * 2,
    )
    _write_parquet(
        tmp_path / "forecasts" / "2026-11-12" / "openmeteo-ensemble_2026-11-12.parquet",
        ["2026-11-12 08:31:23"] * 2,
    )
    rows = hours.collect(tmp_path / "forecasts")
    assert [row["issue_date"] for row in rows] == ["2026-11-11", "2026-11-12"]
    assert [row["band"] for row in rows] == ["12:00-23:59", "00:00-11:59"]
    assert [row["hour_utc"] for row in rows] == [16, 8]
    assert [row["rows"] for row in rows] == [2, 2]


def test_collect_rejects_duplicate_issue_dates(hours, tmp_path: Path) -> None:
    stamp = ["2026-11-11 16:27:24"]
    _write_parquet(tmp_path / "a" / "openmeteo-ensemble_2026-11-11.parquet", stamp)
    _write_parquet(tmp_path / "b" / "openmeteo-ensemble_2026-11-11.parquet", stamp)
    with pytest.raises(ValueError, match="share one issue date"):
        hours.collect(tmp_path)


def test_collect_missing_dir_and_empty_dir(hours, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        hours.collect(tmp_path / "nope")
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError, match="no "):
        hours.collect(tmp_path / "empty")


def test_main_writes_csv_and_markdown(hours, tmp_path: Path, capsys) -> None:
    archive = tmp_path / "forecasts"
    _write_parquet(
        archive / "2026-11-11" / "openmeteo-ensemble_2026-11-11.parquet",
        ["2026-11-11 16:27:24"] * 4,
        rows=4,
    )
    _write_parquet(
        archive / "2026-11-12" / "openmeteo-ensemble_2026-11-12.parquet",
        ["2026-11-12 08:31:23"] * 5,
        rows=5,
    )
    out = tmp_path / "out"
    assert hours.main(["--archive-dir", str(archive), "--out-dir", str(out)]) == 0

    csv_text = (out / "issue_hours.csv").read_text(encoding="utf-8")
    assert "issue_date,issue_time_utc,hour_utc,band,rows,file" in csv_text
    assert "2026-11-11,2026-11-11 16:27:24,16,12:00-23:59,4" in csv_text
    assert "2026-11-12,2026-11-12 08:31:23,8,00:00-11:59,5" in csv_text

    md = (out / "issue_hours.md").read_text(encoding="utf-8")
    assert "Sample metadata only" in md
    assert "no CRPS, Brier or reliability" in md
    assert "| 00:00-11:59 | 1 |" in md
    assert "| 12:00-23:59 | 1 |" in md
    assert "| **total** | **2** |" in md
    assert "summary: 2 issue dates" in capsys.readouterr().out


def test_main_reports_a_missing_archive_dir(hours, tmp_path: Path, capsys) -> None:
    assert hours.main(["--archive-dir", str(tmp_path / "nope")]) == 1
    assert "not found" in capsys.readouterr().err
