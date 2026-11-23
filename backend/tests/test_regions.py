"""Tests for regional configurations and multi-region compatibility."""

from __future__ import annotations

from zoneinfo import ZoneInfo

from prisma.ingest.base import (
    find_repo_root,
    is_valid_day_convention,
    load_all_regions,
    load_region,
)
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
    expected = (
        "metar-south-america",
        "metar-north-america",
        "metar-europe",
        "metar-asia",
        "metar-africa",
        "metar-oceania",
        "metar-middle-east",
        "metar-global",
    )
    for source_id in expected:
        metar = next((s for s in registry if s["id"] == source_id), None)
        assert metar is not None
        assert metar["tier"] == 2
        assert metar["status"] in (
            "verification_in_progress",
            "ready_for_review",
            "blocked",
            "active",
        )
        assert is_valid_day_convention(metar["day_convention"])


def test_global_regions_validate() -> None:
    region_stems = ("europe", "asia", "africa", "oceania", "middle_east")
    for stem in region_stems:
        path = ROOT / "configs" / "regions" / f"{stem}.yaml"
        region = load_region(path)
        assert region["id"] == stem
        assert len(region["stations"]) >= 12
        station_ids = [s["id"] for s in region["stations"]]
        assert len(station_ids) == len(set(station_ids)), f"{stem}: ids must be unique"
        icaos = [s["icao"] for s in region["stations"] if "icao" in s]
        assert len(icaos) == len(region["stations"]), f"{stem}: icaos required"
        assert len(icaos) == len(set(icaos)), f"{stem}: icaos must be unique"
        for station in region["stations"]:
            assert -90.0 <= station["lat"] <= 90.0
            assert -180.0 <= station["lon"] <= 180.0
            tz_name = station.get("timezone", region["timezone"])
            assert ZoneInfo(tz_name) is not None


def test_load_all_regions_returns_all_global_stations() -> None:
    global_region = load_all_regions(ROOT)
    assert global_region["id"] == "global"
    assert len(global_region["stations"]) == 132
    ids = [s["id"] for s in global_region["stations"]]
    assert len(ids) == len(set(ids))


def test_station_vetting_invariants_hold_against_raw_evidence() -> None:
    """Decision C invariants: <=5.0 km AWC dist, dual-source, 0 dups within 10 km."""
    import json
    import math

    def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
        a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return 2 * r * math.asin(math.sqrt(a))

    regions = (
        "south_america",
        "north_america",
        "europe",
        "asia",
        "africa",
        "oceania",
        "middle_east",
    )
    for slug in regions:
        cfg = load_region(ROOT / "configs" / "regions" / f"{slug}.yaml")
        ev_file = ROOT / "results" / "stations" / "_evidence" / slug / "audit.json"
        assert ev_file.exists(), f"missing audit evidence for {slug}"
        with open(ev_file, encoding="utf-8") as f:
            evidence = json.load(f)

        st_by_icao = {s["icao"]: s for s in evidence["stations"]}
        retained = cfg["stations"]
        assert len(retained) >= 12, f"{slug}: minimum 12 retained stations required"

        for st in retained:
            icao = st["icao"]
            assert icao in st_by_icao, f"{slug}: station {icao} missing in evidence"
            aud = st_by_icao[icao]
            assert aud["second_source_confirmed"], (
                f"{slug} {icao}: dual-catalog confirmation missing"
            )
            assert aud["haversine_awc_km"] is not None and aud["haversine_awc_km"] <= 5.0, (
                f"{slug} {icao}: AWC distance {aud['haversine_awc_km']} km exceeds 5.0 km threshold"
            )

        # Duplicate check: no station pairs within 10 km
        for i in range(len(retained)):
            for j in range(i + 1, len(retained)):
                dist = haversine(
                    retained[i]["lat"],
                    retained[i]["lon"],
                    retained[j]["lat"],
                    retained[j]["lon"],
                )
                assert dist >= 10.0, (
                    f"{slug}: duplicate stations within 10 km: "
                    f"{retained[i]['id']} vs {retained[j]['id']}"
                )


def test_north_america_region_validates() -> None:
    path = ROOT / "configs" / "regions" / "north_america.yaml"
    region = load_region(path)

    assert region["id"] == "north_america"
    assert region["name"] == "North America"
    assert len(region["stations"]) >= 15

    station_ids = [s["id"] for s in region["stations"]]
    assert len(station_ids) == len(set(station_ids)), "station ids must be unique"

    icaos = [s["icao"] for s in region["stations"] if "icao" in s]
    assert len(icaos) == len(region["stations"]), "all stations must declare an icao code"
    assert len(icaos) == len(set(icaos)), "icao codes must be unique"

    for station in region["stations"]:
        # North America bounding box check
        assert 15.0 <= station["lat"] <= 75.0, f"station {station['id']} lat out of bounds"
        assert -170.0 <= station["lon"] <= -50.0, f"station {station['id']} lon out of bounds"

        # Timezone check
        tz_name = station.get("timezone", region["timezone"])
        assert ZoneInfo(tz_name) is not None


def test_openmeteo_parses_north_america_station() -> None:
    region = load_region(ROOT / "configs" / "regions" / "north_america.yaml")
    st = region["stations"][0]  # New York JFK

    payload = {
        "daily": {
            "time": ["2026-11-01"],
            "temperature_2m_max": [15.0],
            "temperature_2m_max_member1": [14.8],
            "temperature_2m_min": [8.0],
            "precipitation_sum": [1.2],
        }
    }
    frame = parse_daily(payload, st, "gfs_seamless")
    assert not frame.empty
    assert frame["location"].iloc[0] == st["name"]
    assert frame["lat"].iloc[0] == st["lat"]
    assert frame["lon"].iloc[0] == st["lon"]
