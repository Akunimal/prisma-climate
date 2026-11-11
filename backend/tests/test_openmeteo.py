"""Open-Meteo parsing tests — no network access."""

from __future__ import annotations

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
