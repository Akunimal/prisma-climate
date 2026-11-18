"""Tests for regional configurations and multi-region compatibility."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from prisma.ingest.base import find_repo_root, is_valid_day_convention, load_region
from prisma.ingest.openmeteo import parse_daily
from prisma.ingest.registry import load_registry

ROOT = find_repo_root()


def test_south_america_region_validates() -> None:
    path = ROOT / "configs" / "regions" / "south_america.yaml"
    region = load_region(path)

    assert region["id"] == "south_america"
    assert region["name"] == "South America"
    assert len(region["stations"]) >= 10

    station_ids = [s["id"] for s in region["stations"]]
    assert len(station_ids) == len(set(station_ids)), "station ids must be unique"

    icaos = [s["icao"] for s in region["stations"] if "icao" in s]
    assert len(icaos) == len(region["stations"]), "all stations must declare an icao code"
    assert len(icaos) == len(set(icaos)), "icao codes must be unique"

    for station in region["stations"]:
        # South America bounding box check
        assert -60.0 <= station["lat"] <= 15.0, f"station {station['id']} lat out of bounds"
        assert -90.0 <= station["lon"] <= -30.0, f"station {station['id']} lon out of bounds"

        # Timezone check
        tz_name = station.get("timezone", region["timezone"])
        assert ZoneInfo(tz_name) is not None


def test_openmeteo_parses_south_america_station() -> None:
    region = load_region(ROOT / "configs" / "regions" / "south_america.yaml")
    st = region["stations"][0]  # Santiago Pudahuel

    payload = {
        "daily": {
            "time": ["2026-11-01"],
            "temperature_2m_max": [25.0],
            "temperature_2m_max_member1": [24.5],
            "temperature_2m_min": [10.0],
            "precipitation_sum": [0.0],
        }
    }
    frame = parse_daily(payload, st, "gfs_seamless")
    assert not frame.empty
    assert frame["location"].iloc[0] == st["name"]
    assert frame["lat"].iloc[0] == st["lat"]
    assert frame["lon"].iloc[0] == st["lon"]


def test_metar_source_registered_under_tier2() -> None:
    registry = load_registry(ROOT / "configs" / "sources.yaml")
    metar = next((s for s in registry if s["id"] == "metar-south-america"), None)
    assert metar is not None
    assert metar["tier"] == 2
    assert metar["status"] == "active"
    assert is_valid_day_convention(metar["day_convention"])
