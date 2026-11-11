"""Tests for scripts/upload_forecast.py: issue-date derivation and idempotency."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "upload_forecast.py"
TARGET = "forecasts/2026-11-11/openmeteo-ensemble_2026-11-11.parquet"


@pytest.fixture(scope="module")
def upload():
    spec = importlib.util.spec_from_file_location("upload_forecast", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["upload_forecast"] = module
    spec.loader.exec_module(module)
    return module


def _write_parquet(path: Path, issue_times: list[str]) -> Path:
    pd.DataFrame({"issue_time": pd.to_datetime(issue_times)}).to_parquet(path, index=False)
    return path


def test_issue_date_comes_from_issue_time(tmp_path: Path, upload) -> None:
    path = _write_parquet(
        tmp_path / "openmeteo-ensemble_2026-11-11.parquet",
        ["2026-11-11 16:27:24", "2026-11-11 16:27:24"],
    )
    assert upload.issue_date_from_parquet(path) == "2026-11-11"


def test_issue_date_ignores_the_download_date(tmp_path: Path, upload) -> None:
    # Fetched the next day, still the 2026-11-11 cycle: the key must follow the
    # issue_time so a re-run cannot mint a second archive for the same cycle.
    path = _write_parquet(tmp_path / "a.parquet", ["2026-11-11 23:59:59"])
    assert upload.issue_date_from_parquet(path) != "2026-11-12"
    assert upload.issue_date_from_parquet(path) == "2026-11-11"


def test_issue_date_rejects_mixed_cycles(tmp_path: Path, upload) -> None:
    path = _write_parquet(tmp_path / "a.parquet", ["2026-11-11 16:27:24", "2026-11-12 06:47:00"])
    with pytest.raises(ValueError, match="issue dates"):
        upload.issue_date_from_parquet(path)


def test_issue_date_requires_the_column(tmp_path: Path, upload) -> None:
    path = tmp_path / "a.parquet"
    pd.DataFrame({"value": [1.0]}).to_parquet(path, index=False)
    with pytest.raises(ValueError, match="issue_time"):
        upload.issue_date_from_parquet(path)


def test_existing_target_is_skipped(tmp_path: Path, upload) -> None:
    path = tmp_path / "openmeteo-ensemble_2026-11-11.parquet"
    path.write_bytes(b"parquet")
    planned, skipped = upload.plan_uploads([path], "2026-11-11", lambda _target: True)
    assert planned == []
    assert skipped == [TARGET]


def test_missing_target_is_uploaded(tmp_path: Path, upload) -> None:
    path = tmp_path / "openmeteo-ensemble_2026-11-11.parquet"
    path.write_bytes(b"parquet")
    planned, skipped = upload.plan_uploads([path], "2026-11-11", lambda _target: False)
    assert [(str(p), target) for p, target in planned] == [(str(path), TARGET)]
    assert skipped == []


def test_replace_is_the_only_way_to_clobber(tmp_path: Path, upload) -> None:
    path = tmp_path / "openmeteo-ensemble_2026-11-11.parquet"
    path.write_bytes(b"parquet")
    planned, skipped = upload.plan_uploads(
        [path], "2026-11-11", lambda _target: True, replace=True
    )
    assert [target for _path, target in planned] == [TARGET]
    assert skipped == []


def test_main_requires_the_token(tmp_path: Path, monkeypatch, upload) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    assert upload.main(["--archive-dir", str(tmp_path), "--issue-date", "2026-11-11"]) == 2


def test_main_rejects_a_date_that_disagrees_with_the_parquet(
    tmp_path: Path, monkeypatch, upload
) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("HF_DATASET_REPO", "Akunimal/prisma-climate")
    _write_parquet(tmp_path / "openmeteo-ensemble_2026-11-11.parquet", ["2026-11-11 16:27:24"])
    assert (
        upload.main(["--archive-dir", str(tmp_path), "--issue-date", "2026-11-12"]) == 1
    )


def test_print_issue_date_round_trip(tmp_path: Path, capsys, upload) -> None:
    path = _write_parquet(tmp_path / "a.parquet", ["2026-11-11 19:46:14"])
    assert upload.main(["--print-issue-date", str(path)]) == 0
    assert capsys.readouterr().out.strip() == "2026-11-11"
