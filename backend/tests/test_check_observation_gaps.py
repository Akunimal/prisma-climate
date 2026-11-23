"""Tests for scripts/check_observation_gaps.py: visibility-only gap report."""

from __future__ import annotations

import importlib.util
import json
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


def test_latest_completed_utc_day_is_yesterday_in_utc(gaps) -> None:
    now = datetime(2026, 11, 13, 23, 59, tzinfo=UTC)
    assert gaps.latest_completed_utc_day(now) == date(2026, 11, 12)
    just_after_midnight = datetime(2026, 11, 14, 0, 1, tzinfo=UTC)
    assert gaps.latest_completed_utc_day(just_after_midnight) == date(2026, 11, 13)


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


def test_load_active_metar_regions_reads_active_sources(gaps, tmp_path: Path) -> None:
    dummy_yaml = tmp_path / "sources.yaml"
    dummy_yaml.write_text(
        """\
version: 1
sources:
  - id: metar-south-america
    status: active
  - id: metar-europe
    status: active
  - id: metar-global
    status: ready_for_review
  - id: smn
    status: active
""",
        encoding="utf-8",
    )
    regions = gaps.load_active_metar_regions(dummy_yaml)
    assert regions == ["europe", "south_america"]


def test_dates_from_metar_tree_paths(gaps) -> None:
    paths = [
        "observations/metar/south_america/2026-11-18/data.parquet",
        "observations/metar/south_america/2026-11-19.parquet",
        "observations/metar/europe/2026-11-20/payload.zip",
        "observations/metar/2026-11-21.parquet",  # global snapshot format
        "observations/smn/observaciones/2026-11-20/observaciones.zip",  # unrelated
    ]
    sa_dates = gaps.dates_from_metar_tree_paths("south_america", paths)
    assert sa_dates == {date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 21)}

    eu_dates = gaps.dates_from_metar_tree_paths("europe", paths)
    assert eu_dates == {date(2026, 11, 20), date(2026, 11, 21)}


def test_dates_on_disk_metar(gaps, tmp_path: Path) -> None:
    metar_root = tmp_path / "metar"
    (metar_root / "africa" / "2026-11-18").mkdir(parents=True)
    (metar_root / "africa" / "2026-11-19.parquet").touch()
    (metar_root / "2026-11-20.parquet").touch()

    dates = gaps.dates_on_disk_metar(tmp_path, "africa")
    assert dates == {date(2026, 11, 18), date(2026, 11, 19), date(2026, 11, 20)}


def test_audit_metar_observations_healthy_vs_gap(gaps) -> None:
    paths = [
        "observations/metar/europe/2026-11-18.parquet",
        "observations/metar/europe/2026-11-19.parquet",
        "observations/metar/europe/2026-11-20.parquet",
        # south_america has gap: 11-18 and 11-20, missing 11-19
        "observations/metar/south_america/2026-11-18.parquet",
        "observations/metar/south_america/2026-11-20.parquet",
    ]
    active_regions = ["europe", "south_america", "asia"]  # asia is empty
    last_day = date(2026, 11, 20)

    res = gaps.audit_metar_observations(paths, active_regions, last_day)

    assert res["status"] == "gaps_detected"
    assert res["total_gaps"] == 1
    assert res["total_active_regions"] == 3
    assert res["regions_with_data"] == 2

    # Europe is healthy
    assert res["regions"]["europe"]["status"] == "ok"
    assert res["regions"]["europe"]["missing_dates"] == []

    # South America has 1 gap
    assert res["regions"]["south_america"]["status"] == "gap"
    assert res["regions"]["south_america"]["missing_dates"] == ["2026-11-19"]

    # Asia is empty
    assert res["regions"]["asia"]["status"] == "empty"
    assert res["regions"]["asia"]["missing_dates"] == []


def test_update_ingest_status_preserves_existing_keys_and_writes_valid_json(
    gaps, tmp_path: Path
) -> None:
    status_file = tmp_path / "ingest_status.json"
    initial_data = {
        "last_run": "2026-11-19T13:00:23",
        "region": "global",
        "rows": {"openmeteo-ensemble": 551040},
        "archive_watchdog": {"archived_issue_dates": 12},
    }
    status_file.write_text(json.dumps(initial_data), encoding="utf-8")

    metar_audit = {
        "as_of": "2026-11-23",
        "total_active_regions": 7,
        "regions_with_data": 7,
        "total_gaps": 0,
        "status": "ok",
        "regions": {
            "south_america": {
                "status": "ok",
                "archived_dates_count": 5,
                "first_archived": "2026-11-18",
                "latest_archived": "2026-11-22",
                "missing_dates": [],
            }
        },
    }

    gaps.update_ingest_status(status_file, metar_audit, stamp_iso="2026-11-23T20:00:00Z")

    updated = json.loads(status_file.read_text(encoding="utf-8"))
    assert updated["last_run"] == "2026-11-19T13:00:23"
    assert updated["rows"]["openmeteo-ensemble"] == 551040
    assert updated["archive_watchdog"]["archived_issue_dates"] == 12

    watchdog = updated["metar_watchdog"]
    assert watchdog["checked_at"] == "2026-11-23T20:00:00Z"
    assert watchdog["as_of"] == "2026-11-23"
    assert watchdog["total_active_regions"] == 7
    assert watchdog["status"] == "ok"
    assert "south_america" in watchdog["regions"]


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
    code = gaps.main(["--out", str(tmp_path), "--now", "2026-11-13T18:55:00Z", "--skip-metar"])
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
    code = gaps.main(["--out", str(tmp_path), "--now", "2026-11-13T18:55:00Z", "--skip-metar"])
    assert code == 1


def test_main_metar_offline_with_injected_tree(tmp_path: Path, gaps) -> None:
    listing = {
        "observations/metar": [
            "observations/metar/south_america/2026-11-21.parquet",
            "observations/metar/south_america/2026-11-22.parquet",
        ],
    }
    status_file = tmp_path / "status.json"
    code = gaps.main(
        [
            "--skip-smn",
            "--now",
            "2026-11-23T12:00:00Z",
            "--status-file",
            str(status_file),
        ],
        list_tree=lambda repo, path: listing.get(path, []),
    )
    assert code == 0
    assert status_file.is_file()
    status_data = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_data["metar_watchdog"]["status"] == "ok"


def test_main_requires_the_repo_variable(monkeypatch, gaps) -> None:
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    assert gaps.main([]) == 2
