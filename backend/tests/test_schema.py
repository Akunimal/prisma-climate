"""Schema, registry and status-file tests — no network access."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from prisma.ingest.base import (
    COLUMNS,
    find_repo_root,
    is_valid_day_convention,
    load_region,
    normalize,
)
from prisma.ingest.registry import CONNECTORS, build, load_registry, select_sources
from prisma.ingest.runner import write_ingest_status

ROOT = find_repo_root()


@pytest.mark.parametrize(
    "value,valid",
    [
        ("utc", True),
        ("local_calendar", True),
        ("obs_hour_12", True),
        ("obs_hour_3", True),
        ("unknown", True),
        ("local-day", False),
        ("LOCAL_CALENDAR", False),
        ("", False),
        (None, False),
    ],
)
def test_day_convention_validation(value: object, valid: bool) -> None:
    assert is_valid_day_convention(value) is valid


def test_normalize_rejects_invalid_day_convention() -> None:
    frame = pd.DataFrame(
        {
            "variable": ["t2m_max"],
            "location": ["x"],
            "lat": [-31.0],
            "lon": [-64.0],
            "time": ["2026-01-01"],
            "value": [30.0],
        }
    )
    with pytest.raises(ValueError, match="invalid day_convention"):
        normalize(frame, "test-source", day_convention="not-a-convention")


def test_normalize_fills_optional_columns_and_units() -> None:
    frame = pd.DataFrame(
        {
            "variable": ["t2m_max", "precip"],
            "location": ["x", "x"],
            "lat": [-31.0, -31.0],
            "lon": [-64.0, -64.0],
            "time": ["2026-01-01", "2026-01-02"],
            "value": [30.0, 1.5],
        }
    )
    out = normalize(frame, "test-source", day_convention="utc")
    assert list(out.columns) == COLUMNS
    assert out["unit"].tolist() == ["degC", "mm"]
    assert out["quality_flag"].unique().tolist() == ["ok"]
    assert out["day_convention"].unique().tolist() == ["utc"]
    assert out["issue_time"].isna().all()


def test_registry_loads_and_every_active_connector_resolves() -> None:
    registry = load_registry(ROOT / "configs" / "sources.yaml")
    active = [entry for entry in registry if entry.get("status") == "active"]
    assert active, "expected at least one active source"
    for entry in active:
        assert is_valid_day_convention(entry["day_convention"])
        assert entry["day_convention"] != "unknown", entry["id"]
        assert entry.get("connector") in CONNECTORS, entry["id"]
        connector = build(entry)
        assert connector.source == entry["id"]


def test_select_sources_filters_by_status_and_tier() -> None:
    registry = load_registry(ROOT / "configs" / "sources.yaml")
    active_tier1 = select_sources(registry, tier=1)
    assert active_tier1
    assert all(entry["status"] == "active" and entry["tier"] == 1 for entry in active_tier1)
    assert select_sources(registry, ids=["ghcn-daily"])[0]["id"] == "ghcn-daily"
    with pytest.raises(ValueError, match="unknown source ids"):
        select_sources(registry, ids=["does-not-exist"])


def test_load_region_validates_argentina() -> None:
    region = load_region(ROOT / "configs" / "regions" / "argentina.yaml")
    assert region["id"] == "argentina"
    assert len(region["stations"]) >= 15
    ghcn_ids = [s["ghcn_id"] for s in region["stations"] if s.get("ghcn_id")]
    assert len(ghcn_ids) == len(region["stations"])
    assert len(set(ghcn_ids)) == len(ghcn_ids)


def test_load_region_rejects_missing_station_fields(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        "id: bad\ntimezone: UTC\nstations:\n  - id: s1\n    name: S1\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing"):
        load_region(bad)


def test_write_ingest_status_ok_and_partial(tmp_path: Path) -> None:
    ok_manifest = {
        "generated_at": "2026-11-11T06:47:00",
        "region": "argentina",
        "sources": {"a": {"status": "ok", "rows": 10}},
    }
    path = write_ingest_status(ok_manifest, path=tmp_path / "ok.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "ok"
    assert payload["rows"] == {"a": 10}
    assert payload["failures"] == []

    partial = {
        "generated_at": "2026-11-11T06:48:00",
        "region": "argentina",
        "sources": {
            "a": {"status": "ok", "rows": 5},
            "b": {"status": "error", "error": "boom"},
        },
    }
    path = write_ingest_status(partial, path=tmp_path / "partial.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["status"] == "partial"
    assert payload["failures"][0]["source"] == "b"
