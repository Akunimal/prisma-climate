"""Tests for scripts/check_observation_gaps.py: visibility-only gap report."""

from __future__ import annotations

import importlib.util
import sys
import types
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_observation_gaps.py"


@pytest.fixture(scope="module")
def gaps():
    spec = importlib.util.spec_from_file_location("check_observation_gaps", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_observation_gaps"] = module
    spec.loader.exec_module(module)
    return module


def test_latest_completed_local_day_is_yesterday_in_argentina(gaps) -> None:
    # 2026-11-13 18:55 UTC = 15:55 in Buenos Aires -> the completed day is 11-12.
    now = datetime(2026, 11, 13, 18, 55, tzinfo=UTC)
    assert gaps.latest_completed_local_day(now) == date(2026, 11, 12)
    # Just after local midnight the previous day is still the last completed one.
    just_after_local_midnight = datetime(2026, 11, 14, 3, 0, tzinfo=UTC)  # 00:00 ART
    assert gaps.latest_completed_local_day(just_after_local_midnight) == date(2026, 11, 13)


def test_dates_from_tree_paths_reads_only_the_payload_prefix(gaps) -> None:
    paths = [
        "observations/smn/datohorario/2026-11-12/datohorario.zip",
        "observations/smn/datohorario/2026-11-12/manifest.json",
        "observations/smn/datohorario/2026-11-13",
        "observations/smn/observaciones/2026-11-13/observaciones.zip",  # other dato
        "forecasts/2026-11-13/openmeteo-ensemble_2026-11-13.parquet",  # unrelated
    ]
    assert gaps.dates_from_tree_paths("datohorario", paths) == {
        date(2026, 11, 12),
        date(2026, 11, 13),
    }
    assert gaps.dates_from_tree_paths("observaciones", paths) == {date(2026, 11, 13)}


def test_dates_on_disk_reads_the_staged_folders(gaps, tmp_path: Path) -> None:
    (tmp_path / "datohorario" / "2026-11-12").mkdir(parents=True)
    (tmp_path / "datohorario" / "2026-11-13").mkdir(parents=True)
    (tmp_path / "datohorario" / "not-a-date").mkdir()
    assert gaps.dates_on_disk(tmp_path, "datohorario") == {
        date(2026, 11, 12),
        date(2026, 11, 13),
    }
    assert gaps.dates_on_disk(tmp_path, "observaciones") == set()


def test_missing_days_finds_the_gap_between_first_and_last(gaps) -> None:
    archived = {date(2026, 11, 12), date(2026, 11, 14)}
    assert gaps.missing_days(archived, date(2026, 11, 15)) == [
        date(2026, 11, 13),
        date(2026, 11, 15),
    ]


def test_missing_days_is_empty_for_a_contiguous_archive(gaps) -> None:
    archived = {date(2026, 11, 12), date(2026, 11, 13)}
    assert gaps.missing_days(archived, date(2026, 11, 13)) == []


def test_missing_days_without_any_archived_day_is_empty(gaps) -> None:
    assert gaps.missing_days(set(), date(2026, 11, 13)) == []


def _fake_hub(monkeypatch, listing: list[str]) -> None:
    class FakeHfApi:
        def __init__(self, token: str | None = None) -> None:
            self.token = token

        def list_repo_tree(
            self, repo_id: str, path_in_repo: str, repo_type: str | None = None
        ):
            prefix = path_in_repo.rstrip("/")
            entries = [
                types.SimpleNamespace(path=path)
                for path in listing
                if path.startswith(prefix + "/")
            ]
            return entries

    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.HfApi = FakeHfApi  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)


def test_main_reports_no_gap_when_the_archive_is_contiguous(
    tmp_path: Path, monkeypatch, gaps
) -> None:
    monkeypatch.setenv("HF_DATASET_REPO", "Akunimal/prisma-climate")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    _fake_hub(
        monkeypatch,
        [
            "observations/smn/datohorario/2026-11-11/datohorario.zip",
            "observations/smn/datohorario/2026-11-12/datohorario.zip",
            "observations/smn/observaciones/2026-11-11/observaciones.zip",
            "observations/smn/observaciones/2026-11-12/observaciones.zip",
        ],
    )
    code = gaps.main(["--out", str(tmp_path), "--now", "2026-11-13T18:55:00Z"])
    assert code == 0


def test_main_fails_when_a_day_inside_the_range_is_missing(
    tmp_path: Path, monkeypatch, gaps
) -> None:
    monkeypatch.setenv("HF_DATASET_REPO", "Akunimal/prisma-climate")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    _fake_hub(
        monkeypatch,
        [
            "observations/smn/datohorario/2026-11-11/datohorario.zip",
            "observations/smn/datohorario/2026-11-13/datohorario.zip",
            "observations/smn/observaciones/2026-11-11/observaciones.zip",
            "observations/smn/observaciones/2026-11-13/observaciones.zip",
        ],
    )
    code = gaps.main(["--out", str(tmp_path), "--now", "2026-11-13T18:55:00Z"])
    assert code == 1


def test_main_requires_the_repo_variable(monkeypatch, gaps) -> None:
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    assert gaps.main([]) == 2
