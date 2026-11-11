"""Open-Meteo parsing tests — no network access."""

from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from prisma.ingest.base import normalize
from prisma.ingest.openmeteo import DAILY_VARIABLES, OpenMeteoEnsemble, OpenMeteoEra5, parse_daily

STATION = {"name": "Cordoba Aero", "lat": -31.317, "lon": -64.217}


def test_parse_daily_maps_variables_and_members() -> None:
    payload = {
        "daily": {
            "time": ["2026-11-01", "2026-11-02"],
            "temperature_2m_max": [30.0, 31.0],
            "temperature_2m_max_member1": [29.0, 30.5],
            "temperature_2m_min_member2": [15.0, 16.0],
            "precipitation_sum": [0.0, 2.5],
        }
    }
    frame = parse_daily(payload, STATION, "gfs_seamless")

    assert set(frame["variable"]) <= set(DAILY_VARIABLES.values())
    assert frame.loc[frame["variable"] == "t2m_max", "member"].tolist() == [0, 0, 1, 1]
    assert frame.loc[frame["variable"] == "t2m_min", "member"].tolist() == [2, 2]
    assert frame["location"].unique().tolist() == ["Cordoba Aero"]
    assert frame["model"].unique().tolist() == ["gfs_seamless"]
    assert frame["lat"].unique().tolist() == [-31.317]


def test_parse_daily_rejects_payload_without_time() -> None:
    try:
        parse_daily({"daily": {}}, STATION, "gfs_seamless")
    except ValueError as exc:
        assert "no daily data" in str(exc)
    else:  # pragma: no cover - the raise is the expected path
        raise AssertionError("expected ValueError")


def test_connectors_declare_local_calendar_and_tier() -> None:
    for connector in (OpenMeteoEra5, OpenMeteoEnsemble):
        instance = connector()
        assert instance.day_convention == "local_calendar"
        assert instance.tier == 1
        assert instance.source.startswith("openmeteo-")


REGION = {
    "id": "toy",
    "timezone": "America/Argentina/Cordoba",
    "history_start": "2026-01-01",
    "stations": [
        {"id": "a", "name": "Alpha", "lat": -31.0, "lon": -64.0},
        {"id": "b", "name": "Beta", "lat": -32.0, "lon": -65.0},
    ],
}


def _existing_frame(location: str, last_day: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "variable": ["t2m_max"],
            "time": [pd.Timestamp(last_day)],
            "value": [25.0],
            "member": [0],
            "location": [location],
            "lat": [-31.0],
            "lon": [-64.0],
            "model": ["era5"],
            "retrieved_at": [pd.Timestamp("2026-01-01")],
        }
    )
    return normalize(frame, "openmeteo-era5", "local_calendar")


def test_era5_incremental_requests_only_missing_days(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(url: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(params)
        times = pd.date_range(params["start_date"], params["end_date"], freq="D")
        return {
            "daily": {
                "time": [d.strftime("%Y-%m-%d") for d in times],
                "temperature_2m_max": [20.0] * len(times),
                "temperature_2m_min": [10.0] * len(times),
                "precipitation_sum": [0.0] * len(times),
            }
        }

    import prisma.ingest.openmeteo as openmeteo_mod

    monkeypatch.setattr(openmeteo_mod, "_request", fake_request)

    # Alpha already covered through 2026-01-10; Beta has no data yet.
    existing = _existing_frame("Alpha", "2026-01-10")
    connector = OpenMeteoEra5()
    region = {
        **REGION,
        "stations": [
            {"id": "a", "name": "Alpha", "lat": -31.0, "lon": -64.0},
            {"id": "b", "name": "Beta", "lat": -32.0, "lon": -65.0},
        ],
    }

    out = connector.fetch(
        region,
        end="2026-01-12",
        pause_seconds=0,
        incremental=True,
        existing=existing,
    )

    assert len(calls) == 2
    by_lat = {c["latitude"]: c for c in calls}
    # Alpha resumes the day after its last stored observation.
    assert by_lat[-31.0]["start_date"] == "2026-01-11"
    assert by_lat[-31.0]["end_date"] == "2026-01-12"
    # Beta fetches from the region history_start.
    assert by_lat[-32.0]["start_date"] == "2026-01-01"
    assert set(out["location"]) == {"Alpha", "Beta"}


def test_era5_incremental_skips_station_already_covered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(url: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(params)
        return {
            "daily": {
                "time": ["2026-01-12"],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [10.0],
                "precipitation_sum": [0.0],
            }
        }

    import prisma.ingest.openmeteo as openmeteo_mod

    monkeypatch.setattr(openmeteo_mod, "_request", fake_request)

    existing = pd.concat(
        [
            _existing_frame("Alpha", "2026-01-15"),
            _existing_frame("Beta", "2026-01-15"),
        ],
        ignore_index=True,
    )
    connector = OpenMeteoEra5()
    out = connector.fetch(REGION, end="2026-01-12", pause_seconds=0, existing=existing)

    assert calls == []
    assert out.empty


def test_era5_non_incremental_fetches_full_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_request(url: str, params: dict[str, Any]) -> dict[str, Any]:
        calls.append(params)
        times = pd.date_range(params["start_date"], params["end_date"], freq="D")
        return {
            "daily": {
                "time": [d.strftime("%Y-%m-%d") for d in times],
                "temperature_2m_max": [20.0] * len(times),
                "temperature_2m_min": [10.0] * len(times),
                "precipitation_sum": [0.0] * len(times),
            }
        }

    import prisma.ingest.openmeteo as openmeteo_mod

    monkeypatch.setattr(openmeteo_mod, "_request", fake_request)

    existing = _existing_frame("Alpha", "2026-01-10")
    connector = OpenMeteoEra5()
    out = connector.fetch(
        REGION,
        end="2026-01-12",
        pause_seconds=0,
        incremental=False,
        existing=existing,
    )

    assert len(calls) == 2
    assert all(c["start_date"] == "2026-01-01" for c in calls)
    assert len(out) > 0
