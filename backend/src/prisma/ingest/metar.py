"""METAR observation connector for PRISMA Climate.

Provides near-real-time and historical observation bridging across aerodromes in
South America (and globally) using ICAO airport identifiers.

Sources:
- Primary operational (<= 30 days): NOAA Aviation Weather Center (AWC) API v4.
  https://aviationweather.gov/api/data/metar
- Secondary / Backfill (> 30 days & fallback): Iowa State Environmental Mesonet (IEM).
  https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py
"""

from __future__ import annotations

import csv
import io
import re
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import requests

from .base import Connector

AWC_BASE_URL = "https://aviationweather.gov/api/data/metar"
IEM_BASE_URL = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

USER_AGENT = "PRISMA-Climate/0.2.0 (+https://github.com/Akunimal/prisma-climate)"
AWC_MAX_BATCH = 5
DEFAULT_TIMEOUT = 30

_RMK_T_RE = re.compile(r"\bT([01])(\d{3})(?:[01]\d{3})?\b")
_BODY_TEMP_RE = re.compile(r"\b(M?\d{2})/(?:M?\d{2}|//)\b")
_PRECIP_WX_RE = re.compile(r"\b(?:\+|-)?(?:RA|DZ|SN|SG|IC|PL|GR|GS|UP|TSRA|SHRA|VCSH|FZRA)\b")


def parse_metar_temperature(raw_ob: str | None, numeric_temp: float | None) -> float | None:
    """Extract temperature in Celsius with priority for 0.1 degC decimal RMK T group."""
    if raw_ob:
        match = _RMK_T_RE.search(raw_ob)
        if match:
            sign_char, val_str = match.groups()
            val = float(val_str) / 10.0
            temp = -val if sign_char == "1" else val
            if -40.0 <= temp <= 55.0:
                return round(temp, 1)

    if numeric_temp is not None:
        try:
            val = float(numeric_temp)
            if -40.0 <= val <= 55.0:
                return round(val, 1)
        except (ValueError, TypeError):
            pass

    if raw_ob:
        match_body = _BODY_TEMP_RE.search(raw_ob)
        if match_body:
            val_str = match_body.group(1)
            temp = -float(val_str[1:]) if val_str.startswith("M") else float(val_str)
            if -40.0 <= temp <= 55.0:
                return round(temp, 1)

    return None


def parse_metar_precip(
    raw_ob: str | None, numeric_p01: float | None
) -> tuple[float | None, bool]:
    """Parse 1-hour precip in mm and check if precipitation was indicated in present weather.

    Returns:
        (precip_mm, is_precip_weather_observed)
    """
    has_precip_wx = bool(raw_ob and _PRECIP_WX_RE.search(raw_ob))

    if numeric_p01 is not None:
        try:
            val = float(numeric_p01)
            # Numeric p01 is expected in mm
            if val >= 0.0:
                return round(val, 1), has_precip_wx
        except (ValueError, TypeError):
            pass

    return None, has_precip_wx


def fetch_awc_batch(
    icaos: list[str],
    hours: int = 48,
    session: requests.Session | None = None,
    get_fn: Callable[..., requests.Response] = requests.get,
) -> list[dict[str, Any]]:
    """Fetch raw METAR JSON reports from NOAA AWC in safe batches."""
    if not icaos:
        return []

    headers = {"User-Agent": USER_AGENT}
    all_reports: list[dict[str, Any]] = []

    for i in range(0, len(icaos), AWC_MAX_BATCH):
        batch = icaos[i : i + AWC_MAX_BATCH]
        params = {
            "ids": ",".join(batch),
            "format": "json",
            "hours": str(hours),
        }
        getter = session.get if session else get_fn
        resp = getter(AWC_BASE_URL, params=params, headers=headers, timeout=DEFAULT_TIMEOUT)
        if resp.status_code == 204:  # No Content
            continue
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            all_reports.extend(data)

    return all_reports


def parse_iem_csv(csv_text: str) -> list[dict[str, Any]]:
    """Convert IEM ASOS CSV text into standardized observation dictionaries."""
    reports: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # IEM valid timestamp is ISO format in UTC
        valid_str = row.get("valid")
        if not valid_str:
            continue
        try:
            dt = datetime.fromisoformat(valid_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        station = row.get("station", "").strip()
        raw_ob = row.get("metar", "")

        tmpc_raw = row.get("tmpc")
        numeric_temp = float(tmpc_raw) if tmpc_raw and tmpc_raw != "null" else None

        p01m_raw = row.get("p01m")
        numeric_p01 = float(p01m_raw) if p01m_raw and p01m_raw != "null" else None

        reports.append(
            {
                "icaoId": station,
                "obsTime": int(dt.timestamp()),
                "rawOb": raw_ob,
                "temp": numeric_temp,
                "precip": numeric_p01,
            }
        )
    return reports


def aggregate_daily_records(
    reports: list[dict[str, Any]],
    station: dict[str, Any],
    day_convention: str = "local_calendar",
) -> list[dict[str, Any]]:
    """Aggregate hourly/sub-hourly METAR reports into daily t2m_max, t2m_min, precip."""
    icao = station.get("icao", station.get("id"))
    station_reports = [r for r in reports if r.get("icaoId") == icao]
    if not station_reports:
        return []

    tz_str = station.get("timezone", "UTC")
    tz = ZoneInfo(tz_str) if day_convention == "local_calendar" else UTC

    # Group by (date_str, hour_int) to deduplicate multiple SPECI within same hour
    # structure: day_date -> hour -> list of parsed records
    daily_hourly: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for r in station_reports:
        obs_time = r.get("obsTime")
        if not obs_time:
            continue
        dt_utc = datetime.fromtimestamp(int(obs_time), tz=UTC)
        dt_local = dt_utc.astimezone(tz)
        date_key = dt_local.strftime("%Y-%m-%d")
        hour_key = dt_local.hour

        temp = parse_metar_temperature(r.get("rawOb"), r.get("temp"))
        precip_mm, has_precip_wx = parse_metar_precip(r.get("rawOb"), r.get("precip"))

        daily_hourly[date_key][hour_key].append(
            {
                "dt": dt_local,
                "temp": temp,
                "precip_mm": precip_mm,
                "has_precip_wx": has_precip_wx,
            }
        )

    out_rows: list[dict[str, Any]] = []

    for date_str, hours_dict in sorted(daily_hourly.items()):
        # Evaluate distinct hours with temperature
        hours_with_temp = [
            h for h, recs in hours_dict.items() if any(rec["temp"] is not None for rec in recs)
        ]
        n_hours = len(hours_with_temp)

        # QC threshold: discard day if < 18 distinct hours
        if n_hours < 18:
            continue

        # Check critical temperature windows in local time
        # min window: 04:00 - 09:00, max window: 12:00 - 18:00
        min_window_count = sum(1 for h in hours_with_temp if 4 <= h <= 9)
        max_window_count = sum(1 for h in hours_with_temp if 12 <= h <= 18)

        if n_hours >= 20 and min_window_count >= 3 and max_window_count >= 3:
            qc_flag = "ok"
        else:
            qc_flag = "suspect"

        all_temps = [
            rec["temp"]
            for recs in hours_dict.values()
            for rec in recs
            if rec["temp"] is not None
        ]
        if not all_temps:
            continue

        t_max = max(all_temps)
        t_min = min(all_temps)
        if t_min > t_max:
            continue

        base_row = {
            "location": station["name"],
            "lat": station["lat"],
            "lon": station["lon"],
            "time": date_str,
            "quality_flag": qc_flag,
        }

        # Temperature Max
        out_rows.append(
            {
                **base_row,
                "variable": "t2m_max",
                "value": t_max,
            }
        )

        # Temperature Min
        out_rows.append(
            {
                **base_row,
                "variable": "t2m_min",
                "value": t_min,
            }
        )

        # Precipitation sum (only if reported and no false-zero conflict)
        hourly_precips = []
        any_conflict = False
        for recs in hours_dict.values():
            p_vals = [rec["precip_mm"] for rec in recs if rec["precip_mm"] is not None]
            has_rain_wx = any(rec["has_precip_wx"] for rec in recs)
            if p_vals:
                hourly_precips.append(max(p_vals))
            elif has_rain_wx:
                # Weather code indicated precipitation but no accumulation was reported
                any_conflict = True

        if not any_conflict and len(hourly_precips) >= 20:
            out_rows.append(
                {
                    **base_row,
                    "variable": "precip",
                    "value": round(sum(hourly_precips), 1),
                }
            )

    return out_rows


class MetarConnector(Connector):
    """Base observation connector for aerodromes via METAR."""

    source = "metar"
    tier = 2
    day_convention = "local_calendar"

    def __init__(
        self,
        hours: int = 48,
        day_conventions: tuple[str, ...] = ("local_calendar", "utc"),
    ) -> None:
        self.hours = hours
        self.day_conventions = day_conventions

    def fetch(self, region: dict[str, Any], **options: Any) -> pd.DataFrame:
        """Fetch and aggregate METAR observations across stations declaring an ICAO code."""
        stations = [s for s in region.get("stations", []) if "icao" in s]
        if not stations:
            raise ValueError(f"{self.source}: no station in region declares an 'icao' code")

        icaos = [s["icao"] for s in stations]
        get_fn = options.get("get_fn", requests.get)
        hours = options.get("hours", self.hours)
        convention = options.get("day_convention", self.day_convention)

        raw_reports = fetch_awc_batch(icaos, hours=hours, get_fn=get_fn)

        all_rows: list[dict[str, Any]] = []
        for station in stations:
            rows = aggregate_daily_records(
                raw_reports,
                station,
                day_convention=convention,
            )
            all_rows.extend(rows)

        if not all_rows:
            return pd.DataFrame(
                columns=["variable", "location", "lat", "lon", "time", "value", "quality_flag"]
            )

        return pd.DataFrame(all_rows)


class MetarSouthAmerica(MetarConnector):
    """Bridge observation connector for South American aerodromes via METAR."""

    source = "metar-south-america"


class MetarNorthAmerica(MetarConnector):
    """Bridge observation connector for North American aerodromes via METAR."""

    source = "metar-north-america"


class MetarEurope(MetarConnector):
    """Bridge observation connector for European aerodromes via METAR."""

    source = "metar-europe"


class MetarAsia(MetarConnector):
    """Bridge observation connector for Asian aerodromes via METAR."""

    source = "metar-asia"


class MetarAfrica(MetarConnector):
    """Bridge observation connector for African aerodromes via METAR."""

    source = "metar-africa"


class MetarOceania(MetarConnector):
    """Bridge observation connector for Oceania & Pacific aerodromes via METAR."""

    source = "metar-oceania"


class MetarMiddleEast(MetarConnector):
    """Bridge observation connector for Middle Eastern aerodromes via METAR."""

    source = "metar-middle-east"


class MetarGlobal(MetarConnector):
    """Global bridge observation connector for all worldwide aerodromes via METAR."""

    source = "metar-global"
