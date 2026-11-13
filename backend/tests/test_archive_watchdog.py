"""Tests for scripts/archive_watchdog.py: date diff, status merge, main."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "archive_watchdog.py"
CHECKED_AT = datetime(2026, 11, 13, 11, 0, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def watchdog():
    spec = importlib.util.spec_from_file_location("archive_watchdog", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["archive_watchdog"] = module
    spec.loader.exec_module(module)
    return module


def test_issue_dates_from_repo_files(watchdog) -> None:
    files = [
        "README.md",
        "forecasts/2026-11-11/openmeteo-ensemble_2026-11-11.parquet",
        "forecasts/2026-11-12/openmeteo-ensemble_2026-11-12.parquet",
        "forecasts/2026-13-45/openmeteo-ensemble_bad.parquet",
        "other/2026-11-13/file.parquet",
    ]
    assert watchdog.issue_dates_from_repo_files(files) == {
        "2026-11-11",
        "2026-11-12",
    }


def test_missing_days_full_window(watchdog) -> None:
    archived = {"2026-11-11", "2026-11-12"}
    missing = watchdog.missing_days(archived, date(2026, 11, 11), date(2026, 11, 14))
    assert missing == ["2026-11-13", "2026-11-14"]


def test_missing_days_empty_when_fully_archived(watchdog) -> None:
    archived = {"2026-11-11", "2026-11-12"}
    assert watchdog.missing_days(archived, date(2026, 11, 11), date(2026, 11, 12)) == []


def test_missing_days_rejects_reversed_window(watchdog) -> None:
    with pytest.raises(ValueError, match="before"):
        watchdog.missing_days(set(), date(2026, 11, 12), date(2026, 11, 11))


def test_merge_status_preserves_ingest_keys(watchdog, tmp_path: Path) -> None:
    status = tmp_path / "ingest_status.json"
    status.write_text(
        json.dumps(
            {
                "last_run": "2026-11-12T23:44:41",
                "region": "argentina",
                "rows": {"openmeteo-ensemble": 74784},
                "failures": [],
                "status": "ok",
            }
        ),
        encoding="utf-8",
    )
    payload = watchdog.merge_status(
        status,
        missing=["2026-11-13"],
        archived={"2026-11-11", "2026-11-12"},
        since=date(2026, 11, 11),
        as_of=date(2026, 11, 13),
        checked_at=CHECKED_AT,
    )
    assert payload["last_run"] == "2026-11-12T23:44:41"
    assert payload["status"] == "ok"
    block = payload["archive_watchdog"]
    assert block["checked_at"] == "2026-11-13T11:00:00Z"
    assert block["missing_issue_dates"] == ["2026-11-13"]
    assert block["archived_issue_dates"] == 2
    assert "visibility only" in block["note"]


def test_merge_status_is_idempotent(watchdog, tmp_path: Path) -> None:
    status = tmp_path / "ingest_status.json"
    status.write_text(json.dumps({"last_run": "x"}), encoding="utf-8")
    kwargs = {
        "missing": ["2026-11-13"],
        "archived": {"2026-11-11"},
        "since": date(2026, 11, 11),
        "as_of": date(2026, 11, 13),
        "checked_at": CHECKED_AT,
    }
    payload = watchdog.merge_status(status, **kwargs)
    payload = watchdog.merge_status(status, **{**kwargs, "missing": []})
    assert "archive_watchdog" in payload
    assert payload["archive_watchdog"]["missing_issue_dates"] == []


def test_merge_status_requires_the_file(watchdog, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        watchdog.merge_status(
            tmp_path / "nope.json",
            missing=[],
            archived=set(),
            since=date(2026, 11, 11),
            as_of=date(2026, 11, 11),
            checked_at=CHECKED_AT,
        )


def _fake_hub(monkeypatch, files: list[str]) -> None:
    module = types.ModuleType("huggingface_hub")

    def list_repo_files(repo_id: str, repo_type: str | None = None) -> list[str]:
        return files

    module.list_repo_files = list_repo_files  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)


def test_main_writes_missing_days(watchdog, tmp_path: Path, monkeypatch, capsys) -> None:
    _fake_hub(
        monkeypatch,
        [
            "README.md",
            "forecasts/2026-11-11/openmeteo-ensemble_2026-11-11.parquet",
            "forecasts/2026-11-12/openmeteo-ensemble_2026-11-12.parquet",
        ],
    )
    status = tmp_path / "ingest_status.json"
    status.write_text(
        json.dumps({"last_run": "2026-11-12T23:44:41", "status": "ok"}),
        encoding="utf-8",
    )

    code = watchdog.main(
        [
            "--status",
            str(status),
            "--since",
            "2026-11-11",
            "--as-of",
            "2026-11-13",
            "--hf-repo",
            "Akunimal/prisma-climate",
        ]
    )
    assert code == 0
    payload = json.loads(status.read_text(encoding="utf-8"))
    assert payload["last_run"] == "2026-11-12T23:44:41"
    assert payload["archive_watchdog"]["missing_issue_dates"] == ["2026-11-13"]
    out = capsys.readouterr().out
    assert "1 missing" in out
    assert "2026-11-13" in out


def test_main_reports_hf_failure_without_touching_status(
    watchdog, tmp_path: Path, monkeypatch, capsys
) -> None:
    module = types.ModuleType("huggingface_hub")

    def list_repo_files(repo_id: str, repo_type: str | None = None) -> list[str]:
        raise RuntimeError("boom")

    module.list_repo_files = list_repo_files  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", module)

    status = tmp_path / "ingest_status.json"
    original = json.dumps({"last_run": "keep", "status": "ok"})
    status.write_text(original, encoding="utf-8")

    code = watchdog.main(["--status", str(status), "--as-of", "2026-11-13"])
    assert code == 1
    assert status.read_text(encoding="utf-8") == original
    assert "boom" in capsys.readouterr().err
