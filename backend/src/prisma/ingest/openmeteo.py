"""Open-Meteo connectors: ERA5 history and the multi-model ensemble forecast.

Open-Meteo is the access layer here. The gridded values are not station
measurements, which is why observations come from GHCN-Daily instead.
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd
import requests

from .base import Connector, utc_now

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

DAILY_VARIABLES = {
    "temperature_2m_max": "t2m_max",
    "temperature_2m_min": "t2m_min",
    "precipitation_sum": "precip",
}

RETRIES = 5
TIMEOUT = 120
PAUSE_SECONDS = 0.2
RATE_LIMIT_PAUSE_SECONDS = 65


def _request(url: str, params: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(url, params=params, timeout=TIMEOUT)
            if response.status_code == 429:
                # Open-Meteo free tier enforces a per-minute budget; waiting out
                # the window is cheaper than burning the remaining retries.
                last_error = RuntimeError("429 Too Many Requests")
                time.sleep(RATE_LIMIT_PAUSE_SECONDS)
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"GET {url} failed after {RETRIES} attempts: {last_error}")


def parse_daily(payload: dict[str, Any], station: dict[str, Any], model: str) -> pd.DataFrame:
    """Convert an Open-Meteo daily payload (wide, with members) into long rows."""
    daily = payload.get("daily") or {}
    if "time" not in daily:
        raise ValueError(f"no daily data returned for {station['name']}")

    times = pd.to_datetime(daily["time"])
    chunks: list[pd.DataFrame] = []
    for raw, canonical in DAILY_VARIABLES.items():
        for key, values in daily.items():
            if key != raw and not key.startswith(f"{raw}_member"):
                continue
            member = 0 if key == raw else int(key.rsplit("_member", 1)[1])
            chunks.append(
                pd.DataFrame(
                    {
                        "variable": canonical,
                        "time": times,
                        "value": pd.to_numeric(pd.Series(values), errors="coerce"),
                        "member": member,
                    }
                )
            )

    if not chunks:
        raise ValueError(f"no known variables returned for {station['name']}")

    frame = pd.concat(chunks, ignore_index=True)
    frame["location"] = station["name"]
    frame["lat"] = station["lat"]
    frame["lon"] = station["lon"]
    frame["model"] = model
    return frame


class OpenMeteoEra5(Connector):
    """Daily ERA5 aggregates from the Open-Meteo archive API."""

    source = "openmeteo-era5"
    tier = 1
    day_convention = "local_calendar"

    def fetch(
        self,
        region: dict[str, Any],
        start: str | None = None,
        end: str | None = None,
        models: tuple[str, ...] | list[str] = ("era5",),
        pause_seconds: float = PAUSE_SECONDS,
        **_options: Any,
    ) -> pd.DataFrame:
        retrieved = utc_now()
        start = start or region.get("history_start", "1996-01-01")
        if end is None:
            # ERA5 through Open-Meteo lags real time by about five days.
            end = (utc_now().normalize() - pd.Timedelta(days=6)).date().isoformat()

        frames: list[pd.DataFrame] = []
        for station in region["stations"]:
            for model in models:
                payload = _request(
                    ARCHIVE_URL,
                    {
                        "latitude": station["lat"],
                        "longitude": station["lon"],
                        "start_date": start,
                        "end_date": end,
                        "daily": ",".join(DAILY_VARIABLES),
                        "timezone": station.get("timezone", region["timezone"]),
                        "models": model,
                    },
                )
                frames.append(parse_daily(payload, station, model))
                time.sleep(pause_seconds)

        out = pd.concat(frames, ignore_index=True)
        out["retrieved_at"] = retrieved
        return out


class OpenMeteoEnsemble(Connector):
    """Current ensemble forecast for each configured model."""

    source = "openmeteo-ensemble"
    tier = 1
    day_convention = "local_calendar"

    def fetch(
        self,
        region: dict[str, Any],
        models: tuple[str, ...] | list[str] = ("gfs_seamless",),
        forecast_days: int = 15,
        **_options: Any,
    ) -> pd.DataFrame:
        retrieved = utc_now()
        frames: list[pd.DataFrame] = []
        for station in region["stations"]:
            for model in models:
                payload = _request(
                    ENSEMBLE_URL,
                    {
                        "latitude": station["lat"],
                        "longitude": station["lon"],
                        "daily": ",".join(DAILY_VARIABLES),
                        "models": model,
                        "forecast_days": forecast_days,
                        "timezone": station.get("timezone", region["timezone"]),
                    },
                )
                frame = parse_daily(payload, station, model)
                issue = frame["time"].min()
                frame["lead_day"] = (frame["time"] - issue).dt.days
                frames.append(frame)
                time.sleep(PAUSE_SECONDS)

        out = pd.concat(frames, ignore_index=True)
        out["retrieved_at"] = retrieved
        # Open-Meteo does not expose the model cycle, so the UTC fetch time is
        # recorded as the issue proxy. Verification groups forecasts by it.
        out["issue_time"] = retrieved
        return out
