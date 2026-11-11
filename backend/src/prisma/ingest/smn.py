"""SMN Argentina open-data connector.

``ssl.smn.gob.ar/dpd/zipopendata.php?dato=...`` serves ZIP payloads that each
contain a single fixed-width text file:

- ``estaciones``: station catalogue (name, province, lat/lon in degrees and
  minutes, elevation, NRO, OACI). Two station names overflow the 30-char name
  column and leave orphan fragment lines (``ERO``, ``RO``), and two rows run
  name and province together with a single space, so the numeric tail is
  matched from the end of each line.
- ``observaciones``: TMAX/TMIN for the latest completed local day only (the
  ``fecha`` query parameter is ignored by the endpoint) in fixed column
  windows — FECHA 1-8, TMAX 10-15, TMIN 16-21, NOMBRE from 22. Blank value
  fields are common, so columns are read by position, never by splitting.

Each configured station is resolved through the deterministic GHCN id → NRO
reading (NOAA readme section IV, shared with the station cross-check), then
NRO → catalogue name, then name → observaciones row. Because the endpoint
never serves history, every run merges the new day into the existing Parquet
the same way the ERA5 archive connector does.

Licence: CC BY 2.5 AR with attribution to SMN — PAD_legales.pdf licenses "todos
sus contenidos"; Infoleg disp25.pdf (Política de Datos del SMN) puts raw
observational data in category A "Datos Abiertos" under that licence.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .base import Connector, utc_now

OBS_URL = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=observaciones"
CATALOGUE_URL = "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones"
TIMEOUT = 60

# Numeric tail of a catalogue data row: lat gr/min, lon gr/min, elevation,
# NRO, OACI. Anchored at the end so rows whose name and province run together
# with a single space still parse.
_TAIL_RE = re.compile(
    r"(?P<lat_gr>-?\d+)\s+(?P<lat_min>\d+)\s+"
    r"(?P<lon_gr>-?\d+)\s+(?P<lon_min>\d+)\s+"
    r"(?P<elev>-?\d+)\s+(?P<nro>\d+)(?:\s+(?P<oaci>\S+))?\s*$"
)

# Fixed windows in an observaciones data line (header: FECHA TMAX TMIN NOMBRE).
_FECHA_SLICE = slice(1, 9)
_TMAX_SLICE = slice(10, 15)
_TMIN_SLICE = slice(16, 21)
_NOMBRE_SLICE = slice(22, None)


def candidate_nros(ghcn_id: Any) -> list[int]:
    """Deterministic WMO readings of a GHCN-Daily id (readme section IV).

    The id is ``FIPS(2) + network(1) + station(8)``. Network ``M`` stores the
    WMO number in the last five characters (``ARM00087938`` → 87938). Network
    ``0`` pads it either as ``000`` + WMO (``AR000087007`` → 87007) or as two
    leading zeros + WMO + trailing zero (``AR000870470`` → 87047). Only these
    three readings are tried — no sliding 5-digit window scan.
    """
    ghcn_id = str(ghcn_id or "")
    if len(ghcn_id) != 11:
        return []
    network, station = ghcn_id[2], ghcn_id[3:]
    readings: list[str] = []
    if network == "M":
        readings.append(station[-5:])
    elif network == "0":
        if station.startswith("000"):
            readings.append(station[3:])
        elif station.endswith("0"):
            readings.append(station[2:7])
    candidates: list[int] = []
    for reading in readings:
        if len(reading) == 5 and reading.isdigit():
            value = int(reading)
            if value not in candidates:
                candidates.append(value)
    return candidates


def parse_estaciones(text: str) -> pd.DataFrame:
    """Parse the estaciones catalogue text into per-station metadata rows."""
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        match = _TAIL_RE.search(line)
        if match is None:
            continue  # header / units / orphan fragment lines
        head_parts = re.split(r"\s{2,}", line[: match.start()].strip())
        lat = (1 if int(match["lat_gr"]) >= 0 else -1) * (
            abs(int(match["lat_gr"])) + int(match["lat_min"]) / 60.0
        )
        lon = (1 if int(match["lon_gr"]) >= 0 else -1) * (
            abs(int(match["lon_gr"])) + int(match["lon_min"]) / 60.0
        )
        records.append(
            {
                "smn_name": head_parts[0] if head_parts else "",
                "smn_province": head_parts[1] if len(head_parts) > 1 else "",
                "smn_lat": lat,
                "smn_lon": lon,
                "smn_elevation_m": float(match["elev"]),
                "smn_nro": int(match["nro"]),
            }
        )
    if not records:
        raise ValueError("no stations parsed from SMN catalogue text")
    return pd.DataFrame.from_records(records)


def _value(window: str) -> float:
    text = window.strip()
    if not text:
        return float("nan")
    try:
        return float(text)
    except ValueError:
        return float("nan")


def parse_observaciones(text: str) -> pd.DataFrame:
    """Parse the observaciones text (latest local day, fixed columns).

    Returns one row per station with ``time``, ``smn_name``, ``t2m_max`` and
    ``t2m_min``; blank fields become NaN. Header, separator and short lines
    are skipped by the FECHA digit check.
    """
    records: list[dict[str, Any]] = []
    for line in text.splitlines():
        if len(line) < 22:
            continue
        fecha = line[_FECHA_SLICE]
        if not fecha.isdigit():
            continue  # header / separator
        nombre = line[_NOMBRE_SLICE].strip()
        if not nombre:
            continue
        records.append(
            {
                "time": pd.to_datetime(fecha, format="%d%m%Y"),
                "smn_name": nombre,
                "t2m_max": _value(line[_TMAX_SLICE]),
                "t2m_min": _value(line[_TMIN_SLICE]),
            }
        )
    if not records:
        raise ValueError("no observations parsed from SMN payload")
    return pd.DataFrame.from_records(records)


def match_region(
    region: dict[str, Any],
    catalogue: pd.DataFrame,
    observations: pd.DataFrame,
    retrieved_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Common-schema rows for region stations present in catalogue and payload."""
    name_by_nro = dict(
        zip(catalogue["smn_nro"], catalogue["smn_name"], strict=False)
    )
    obs_by_name: dict[str, pd.Series] = {}
    for _, row in observations.iterrows():
        obs_by_name.setdefault(str(row["smn_name"]), row)

    retrieved = retrieved_at if retrieved_at is not None else utc_now()
    records: list[dict[str, Any]] = []
    for station in region["stations"]:
        nro = next(
            (
                candidate
                for candidate in candidate_nros(station.get("ghcn_id"))
                if candidate in name_by_nro
            ),
            None,
        )
        if nro is None:
            continue
        row = obs_by_name.get(name_by_nro[nro])
        if row is None:
            continue
        for variable in ("t2m_max", "t2m_min"):
            value = row[variable]
            if pd.isna(value):
                continue
            records.append(
                {
                    "variable": variable,
                    "location": station["name"],
                    "lat": station["lat"],
                    "lon": station["lon"],
                    "time": row["time"],
                    "value": float(value),
                    "quality_flag": "ok",
                    "retrieved_at": retrieved,
                }
            )
    return pd.DataFrame.from_records(records)


def _fetch_zip_text(url: str) -> str:
    """Plain GET (default headers) → ZIP → latin-1 text of the single member."""
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        members = archive.namelist()
        if not members:
            raise ValueError(f"empty ZIP payload from {url}")
        return archive.read(members[0]).decode("latin-1")


class SmnObservations(Connector):
    """Latest SMN daily TMAX/TMIN for every station that resolves by NRO."""

    source = "smn-argentina"
    tier = 1
    day_convention = "local_calendar"

    def fetch(
        self,
        region: dict[str, Any],
        catalogue_text: str | None = None,
        observations_text: str | None = None,
        **_options: Any,
    ) -> pd.DataFrame:
        retrieved = utc_now()
        catalogue = parse_estaciones(
            catalogue_text if catalogue_text is not None else _fetch_zip_text(CATALOGUE_URL)
        )
        observations = parse_observaciones(
            observations_text
            if observations_text is not None
            else _fetch_zip_text(OBS_URL)
        )
        return match_region(region, catalogue, observations, retrieved_at=retrieved)

    def run(
        self,
        region: dict[str, Any],
        out_dir: Path,
        day_convention: str | None = None,
        **options: Any,
    ) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.source}.parquet"

        incremental = bool(options.pop("incremental", True))
        existing: pd.DataFrame | None = None
        if incremental and path.exists():
            existing = pd.read_parquet(path)

        frame = self.fetch_normalized(region, day_convention=day_convention, **options)

        if existing is not None and not frame.empty:
            keys = ["source", "location", "variable", "time", "member", "model"]
            merged = pd.concat([existing, frame], ignore_index=True)
            merged = merged.drop_duplicates(subset=keys, keep="last")
            merged = merged.sort_values(
                ["location", "variable", "time"]
            ).reset_index(drop=True)
            frame = merged
        elif existing is not None and frame.empty:
            frame = existing

        frame.to_parquet(path, index=False)
        return path


__all__ = [
    "SmnObservations",
    "candidate_nros",
    "match_region",
    "parse_estaciones",
    "parse_observaciones",
]
