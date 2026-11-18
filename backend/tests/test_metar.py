"""Unit tests for the METAR observation connector."""

from __future__ import annotations

from unittest.mock import MagicMock

from prisma.ingest.base import COLUMNS
from prisma.ingest.metar import (
    MetarAfrica,
    MetarAsia,
    MetarEurope,
    MetarGlobal,
    MetarMiddleEast,
    MetarNorthAmerica,
    MetarOceania,
    MetarSouthAmerica,
    aggregate_daily_records,
    fetch_awc_batch,
    parse_iem_csv,
    parse_metar_precip,
    parse_metar_temperature,
)


def test_parse_metar_temperature_precision() -> None:
    # Decimal precision from RMK T group
    raw_santiago = "SCEL 170355Z 18005KT 9999 FEW030 14/11 Q1015 RMK AO2 SLP209 T01420108"
    assert parse_metar_temperature(raw_santiago, 14.0) == 14.2

    # Negative temperature in Patagonia
    raw_punta_arenas = "SCCI 170400Z 27015KT 9999 -SN 01/M03 Q1002 RMK T10341050"
    assert parse_metar_temperature(raw_punta_arenas, -3.0) == -3.4

    # Fallback to integer when no T group in RMK
    raw_aeroparque = "SABE 170400Z 09008KT 9999 CLR 18/12 Q1018"
    assert parse_metar_temperature(raw_aeroparque, 18.0) == 18.0

    # International body regex fallback when numeric_temp is None
    raw_london = "EGLL 181200Z 24012KT 9999 FEW025 09/04 Q1013"
    assert parse_metar_temperature(raw_london, None) == 9.0

    # Subzero international body fallback
    raw_moscow = "UUEE 181200Z 30010KT 5000 -SN OVC020 M08/M12 Q1020"
    assert parse_metar_temperature(raw_moscow, None) == -8.0

    # Physical bounds filtering (-40 to 55)
    assert parse_metar_temperature(None, 60.0) is None
    assert parse_metar_temperature(None, -45.0) is None


def test_parse_metar_precip() -> None:
    # Rain reported in weather code and accumulation in mm
    raw_rain = "SKBO 171800Z 30005KT 4000 +RA FEW015CB BKN030 15/14 Q1025"
    p_mm, has_rain = parse_metar_precip(raw_rain, 5.2)
    assert p_mm == 5.2
    assert has_rain is True

    # Rain reported in weather code but accumulation missing (false-zero guard)
    p_mm_none, has_rain = parse_metar_precip(raw_rain, None)
    assert p_mm_none is None
    assert has_rain is True

    # Clear weather, zero rain
    raw_clear = "SUMU 171200Z 12010KT 9999 SKC 20/12 Q1016"
    p_mm_zero, has_rain = parse_metar_precip(raw_clear, 0.0)
    assert p_mm_zero == 0.0
    assert has_rain is False


def test_fetch_awc_batch_and_204_handling() -> None:
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    mock_resp_200.json.return_value = [{"icaoId": "SCEL", "obsTime": 1700000000, "temp": 20}]

    mock_resp_204 = MagicMock()
    mock_resp_204.status_code = 204

    def mock_get(url: str, params: dict, headers: dict, timeout: int) -> MagicMock:
        ids = params.get("ids", "")
        if "SCEL" in ids:
            return mock_resp_200
        return mock_resp_204

    icaos = ["SCEL", "SUMU", "SBSP", "SKBO", "SPJC", "SEQM", "SLLP"]
    reports = fetch_awc_batch(icaos, hours=24, get_fn=mock_get)
    assert len(reports) == 1
    assert reports[0]["icaoId"] == "SCEL"


def test_parse_iem_csv() -> None:
    csv_sample = (
        "station,valid,tmpc,dwpc,p01m,metar\n"
        "SCEL,2026-11-17 12:00,18.5,10.2,0.0,SCEL 171200Z 18.5/10.2\n"
        "SCEL,2026-11-17 13:00,null,null,null,SCEL 171300Z\n"
    )
    reports = parse_iem_csv(csv_sample)
    assert len(reports) == 2
    assert reports[0]["icaoId"] == "SCEL"
    assert reports[0]["temp"] == 18.5
    assert reports[0]["precip"] == 0.0
    assert reports[1]["temp"] is None


def test_daily_aggregation_local_vs_utc() -> None:
    station = {
        "id": "santiago_pudahuel",
        "name": "Santiago Pudahuel",
        "icao": "SCEL",
        "lat": -33.393,
        "lon": -70.786,
        "timezone": "America/Santiago",
    }

    # Generate 24 hourly reports on 2026-11-17 local time
    # America/Santiago is UTC-3 in November
    base_ts_utc = 1794884400  # 2026-11-17 03:00 UTC = 2026-11-17 00:00 local
    reports = []
    for h in range(24):
        reports.append(
            {
                "icaoId": "SCEL",
                "obsTime": base_ts_utc + h * 3600,
                "rawOb": f"SCEL T0{150 + h}0100",
                "temp": 15.0 + h * 0.1,
                "precip": 0.0,
            }
        )

    # Local calendar day aggregation
    local_rows = aggregate_daily_records(reports, station, day_convention="local_calendar")
    assert any(r["variable"] == "t2m_max" and r["time"] == "2026-11-17" for r in local_rows)
    assert any(r["variable"] == "t2m_min" and r["time"] == "2026-11-17" for r in local_rows)


def test_qc_coverage_thresholds() -> None:
    station = {
        "id": "montevideo_carrasco",
        "name": "Montevideo Carrasco",
        "icao": "SUMU",
        "lat": -34.838,
        "lon": -56.031,
        "timezone": "America/Montevideo",
    }

    # Case A: 21 hours reported with full windows -> 'ok'
    base_ts = 1794884400
    reports_ok = [
        {"icaoId": "SUMU", "obsTime": base_ts + h * 3600, "rawOb": None, "temp": 20.0}
        for h in range(21)
    ]
    rows_ok = aggregate_daily_records(reports_ok, station)
    assert len(rows_ok) >= 2
    assert rows_ok[0]["quality_flag"] == "ok"

    # Case B: 18 hours reported -> 'suspect'
    reports_suspect = [
        {"icaoId": "SUMU", "obsTime": base_ts + h * 3600, "rawOb": None, "temp": 20.0}
        for h in range(18)
    ]
    rows_suspect = aggregate_daily_records(reports_suspect, station)
    assert len(rows_suspect) >= 2
    assert rows_suspect[0]["quality_flag"] == "suspect"

    # Case C: 12 hours reported -> insufficient (discarded)
    reports_short = [
        {"icaoId": "SUMU", "obsTime": base_ts + h * 3600, "rawOb": None, "temp": 20.0}
        for h in range(12)
    ]
    rows_short = aggregate_daily_records(reports_short, station)
    assert len(rows_short) == 0


def test_metar_connector_fetch_normalized() -> None:
    connector = MetarSouthAmerica()
    region = {
        "id": "south_america",
        "timezone": "America/Sao_Paulo",
        "stations": [
            {
                "id": "sao_paulo_congonhas",
                "name": "São Paulo Congonhas",
                "icao": "SBSP",
                "lat": -23.626,
                "lon": -46.656,
                "timezone": "America/Sao_Paulo",
            }
        ],
    }

    base_ts = 1794884400
    mock_reports = [
        {
            "icaoId": "SBSP",
            "obsTime": base_ts + h * 3600,
            "rawOb": "SBSP T02000100",
            "temp": 20.0,
            "precip": 0.0,
        }
        for h in range(22)
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_reports

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        return mock_resp

    frame = connector.fetch_normalized(region, get_fn=mock_get)
    assert not frame.empty
    assert list(frame.columns) == COLUMNS
    assert frame["source"].iloc[0] == "metar-south-america"
    assert frame["location"].iloc[0] == "São Paulo Congonhas"
    assert set(frame["variable"].unique()) == {"t2m_max", "t2m_min", "precip"}


def test_metar_north_america_fetch_normalized() -> None:
    connector = MetarNorthAmerica()
    region = {
        "id": "north_america",
        "timezone": "America/New_York",
        "stations": [
            {
                "id": "new_york_jfk",
                "name": "New York JFK International",
                "icao": "KJFK",
                "lat": 40.640,
                "lon": -73.779,
                "timezone": "America/New_York",
            }
        ],
    }

    base_ts = 1794884400
    mock_reports = [
        {
            "icaoId": "KJFK",
            "obsTime": base_ts + h * 3600,
            "rawOb": "KJFK T01500080",
            "temp": 15.0,
            "precip": 0.0,
        }
        for h in range(22)
    ]

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_reports

    def mock_get(*args: object, **kwargs: object) -> MagicMock:
        return mock_resp

    frame = connector.fetch_normalized(region, get_fn=mock_get)
    assert not frame.empty
    assert list(frame.columns) == COLUMNS
    assert frame["source"].iloc[0] == "metar-north-america"
    assert frame["location"].iloc[0] == "New York JFK International"
    assert set(frame["variable"].unique()) == {"t2m_max", "t2m_min", "precip"}


def test_metar_regional_subclasses_sources() -> None:
    assert MetarEurope.source == "metar-europe"
    assert MetarAsia.source == "metar-asia"
    assert MetarAfrica.source == "metar-africa"
    assert MetarOceania.source == "metar-oceania"
    assert MetarMiddleEast.source == "metar-middle-east"
    assert MetarGlobal.source == "metar-global"
    assert MetarSouthAmerica.source == "metar-south-america"
    assert MetarNorthAmerica.source == "metar-north-america"
