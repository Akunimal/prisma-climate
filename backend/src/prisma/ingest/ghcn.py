"""NOAA GHCN-Daily connector.

GHCN-Daily is the global observation backbone of the project. Files are
fixed-width ``.dly`` records; values are stored in tenths of the reported unit.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .base import Connector, find_repo_root, utc_now

DLY_URL = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station_id}.dly"
ELEMENTS = {"TMAX": "t2m_max", "TMIN": "t2m_min", "PRCP": "precip"}
CACHE_MAX_AGE_SECONDS = 24 * 3600
TIMEOUT = 180


def parse_dly(text: str, station: dict[str, Any], min_year: int = 1900) -> pd.DataFrame:
    """Parse a GHCN-Daily .dly file into the common schema columns."""
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if len(line) < 21:
            continue
        try:
            year = int(line[11:15])
            month = int(line[15:17])
        except ValueError:
            continue

        canonical = ELEMENTS.get(line[17:21])
        if canonical is None or year < min_year:
            continue

        for day in range(31):
            offset = 21 + day * 8
            chunk = line[offset : offset + 8]
            if len(chunk) < 8:
                break
            raw = chunk[0:5].strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value == -9999:
                continue
            try:
                when = pd.Timestamp(year=year, month=month, day=day + 1)
            except ValueError:
                continue
            rows.append(
                {
                    "variable": canonical,
                    "location": station["name"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "time": when,
                    "value": value / 10.0,
                    "quality_flag": "ok" if chunk[6] == " " else "suspect",
                }
            )

    return pd.DataFrame(rows)


def _download(station_id: str, cache_dir: Path) -> str:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{station_id}.dly"
    fresh = (
        path.exists() and (time.time() - path.stat().st_mtime) < CACHE_MAX_AGE_SECONDS
    )
    if not fresh:
        response = requests.get(DLY_URL.format(station_id=station_id), timeout=TIMEOUT)
        response.raise_for_status()
        path.write_bytes(response.content)
    return path.read_text(encoding="ascii", errors="replace")


class GhcnDaily(Connector):
    """Station observations for every station that declares a ``ghcn_id``."""

    source = "ghcn-daily"
    tier = 1
    day_convention = "local_calendar"

    def fetch(
        self,
        region: dict[str, Any],
        min_year: int = 1900,
        cache_dir: str | Path | None = None,
        **_options: Any,
    ) -> pd.DataFrame:
        cache = Path(cache_dir) if cache_dir else find_repo_root() / "data" / "cache" / "ghcn"
        retrieved = utc_now()
        frames: list[pd.DataFrame] = []

        for station in region["stations"]:
            station_id = station.get("ghcn_id")
            if not station_id:
                continue
            text = _download(station_id, cache)
            frames.append(parse_dly(text, station, int(min_year)))

        if not frames:
            raise ValueError("no station in this region declares a ghcn_id")

        out = pd.concat(frames, ignore_index=True)
        out["retrieved_at"] = retrieved
        return out
