"""Slow climate indices from NOAA CPC: ONI (ENSO) and SAM.

These are monthly indices, not point observations. They are stored with a
representative coordinate so the common schema can carry them unchanged.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import requests

from .base import Connector

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
SAM_URL = (
    "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/aao/"
    "monthly.aao.index.b79.current.ascii.table"
)
TIMEOUT = 120

SEASON_CENTER_MONTH = {
    "DJF": 1,
    "JFM": 2,
    "FMA": 3,
    "MAM": 4,
    "AMJ": 5,
    "MJJ": 6,
    "JJA": 7,
    "JAS": 8,
    "ASO": 9,
    "SON": 10,
    "OND": 11,
    "NDJ": 12,
}


def _text(url: str) -> str:
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def parse_oni(text: str) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) != 4:
            continue
        season, year, _total, anomaly = parts
        month = SEASON_CENTER_MONTH.get(season.upper())
        if month is None:
            continue
        try:
            rows.append(
                {
                    "variable": "oni",
                    "location": "Nino 3.4",
                    "lat": -5.0,
                    "lon": -150.0,
                    "time": pd.Timestamp(year=int(year), month=month, day=1),
                    "value": float(anomaly),
                }
            )
        except ValueError:
            continue
    return pd.DataFrame(rows)


def parse_sam(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    if not lines:
        return pd.DataFrame()
    header = lines[0].split()
    if len(header) < 12:
        raise ValueError("unexpected SAM table header")

    rows: list[dict[str, Any]] = []
    for line in lines[1:]:
        parts = line.split()
        if len(parts) < 13:
            continue
        try:
            year = int(parts[0])
        except ValueError:
            continue
        for month, token in enumerate(parts[1:13], start=1):
            try:
                value = float(token)
            except ValueError:
                continue
            rows.append(
                {
                    "variable": "sam",
                    "location": "Southern Annular Mode",
                    "lat": -60.0,
                    "lon": 0.0,
                    "time": pd.Timestamp(year=year, month=month, day=1),
                    "value": value,
                }
            )
    return pd.DataFrame(rows)


class NoaaOni(Connector):
    source = "noaa-oni"
    tier = 1
    day_convention = "utc"

    def fetch(self, region: dict[str, Any], **_options: Any) -> pd.DataFrame:
        return parse_oni(_text(ONI_URL))


class NoaaSam(Connector):
    source = "noaa-sam"
    tier = 1
    day_convention = "utc"

    def fetch(self, region: dict[str, Any], **_options: Any) -> pd.DataFrame:
        return parse_sam(_text(SAM_URL))
