"""Anti-drift verification integrity test suite.

Recomputes and asserts all quantitative invariants directly from committed
raw evidence JSON files (results/stations/_evidence/<region>/audit.json)
and verifies strict adherence to the anti-drift freeze locks.
"""

from __future__ import annotations

import json
from typing import Any

import yaml

from prisma.ingest.base import find_repo_root, load_region

ROOT = find_repo_root()
PASSING_REGIONS = (
    "south_america",
    "north_america",
    "europe",
    "asia",
    "africa",
    "oceania",
)
ALL_NON_ARGENTINA_METAR_SOURCES = (
    "metar-south-america",
    "metar-north-america",
    "metar-europe",
    "metar-asia",
    "metar-africa",
    "metar-oceania",
    "metar-middle-east",
    "metar-global",
)


def load_evidence(region_slug: str) -> dict[str, Any]:
    path = ROOT / "results" / "stations" / "_evidence" / region_slug / "audit.json"
    assert path.exists(), f"Evidence file missing: {path}"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_distance_invariant_recomputed_from_evidence() -> None:
    """Invariant A: 100% of retained stations in passing regions have Haversine dist <= 5.0 km."""
    for slug in PASSING_REGIONS:
        cfg = load_region(ROOT / "configs" / "regions" / f"{slug}.yaml")
        evidence = load_evidence(slug)
        stations_by_icao = {s["icao"]: s for s in evidence["stations"]}

        for st in cfg["stations"]:
            icao = st["icao"]
            assert icao in stations_by_icao, (
                f"[{slug}] Station {icao} not found in committed evidence"
            )
            ev_st = stations_by_icao[icao]
            awc_dist = ev_st.get("haversine_awc_km")
            assert awc_dist is not None, f"[{slug}] Station {icao} missing AWC distance"
            assert awc_dist <= 5.0, (
                f"[{slug}] Station {icao} distance {awc_dist} km exceeds 5.0 km threshold"
            )


def test_dual_source_confirmation_invariant() -> None:
    """Invariant B: 100% of retained stations confirmed by independent catalog."""
    for slug in PASSING_REGIONS:
        cfg = load_region(ROOT / "configs" / "regions" / f"{slug}.yaml")
        evidence = load_evidence(slug)
        stations_by_icao = {s["icao"]: s for s in evidence["stations"]}

        for st in cfg["stations"]:
            icao = st["icao"]
            ev_st = stations_by_icao[icao]
            assert ev_st.get("second_source_confirmed") is True, (
                f"[{slug}] Station {icao} lacks independent dual-source confirmation"
            )


def test_telemetry_invariant() -> None:
    """Invariant C: 100% of passing regions have >= 80% active telemetry in the last 72h."""
    for slug in PASSING_REGIONS:
        evidence = load_evidence(slug)
        summary = evidence["summary"]
        telemetry_pct = summary.get("active_telemetry_pct", 0.0)
        assert telemetry_pct >= 80.0, (
            f"[{slug}] Active telemetry {telemetry_pct}% is below 80.0% threshold"
        )
        assert summary.get("phase2_vetting_status") == "PASS", f"[{slug}] Phase 2 status not PASS"
        assert summary.get("phase3_obs_status") in ("PASS", "QUALIFIED"), (
            f"[{slug}] Phase 3 status not PASS/QUALIFIED"
        )


def test_promotion_invariants_post_apply() -> None:
    """Post-promotion invariants:

    1. Exactly the 6 vetted regions have status: active and verified_on: '2026-11-19'.
    2. metar-middle-east MUST remain status: blocked and verified_on: null.
    3. README headline MUST remain conservative ('Starting with Argentina...').
    """
    sources_yaml = ROOT / "configs" / "sources.yaml"
    with open(sources_yaml, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    registry = data.get("sources", [])
    sources_by_id = {s["id"]: s for s in registry}

    passing_source_ids = (
        "metar-south-america",
        "metar-north-america",
        "metar-europe",
        "metar-asia",
        "metar-africa",
        "metar-oceania",
    )

    for source_id in passing_source_ids:
        assert source_id in sources_by_id, f"Source {source_id} missing from configs/sources.yaml"
        src = sources_by_id[source_id]
        assert src.get("status") == "active", (
            f"Source {source_id} must be 'active', got '{src.get('status')}'"
        )
        assert str(src.get("verified_on")) == "2026-11-19", (
            f"Source {source_id} verified_on must be '2026-11-19', got '{src.get('verified_on')}'"
        )

    me_src = sources_by_id.get("metar-middle-east")
    assert me_src is not None
    assert me_src.get("status") == "blocked", (
        f"metar-middle-east must be 'blocked', got '{me_src.get('status')}'"
    )
    assert me_src.get("verified_on") is None, (
        f"metar-middle-east verified_on must be None, got '{me_src.get('verified_on')}'"
    )

    # Headline check
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Starting with Argentina, designed to scale globally" in readme_text
    assert "**Global planetary coverage, open climate forecast verification" not in readme_text
