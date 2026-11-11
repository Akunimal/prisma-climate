"""Common connector interface and canonical data schema.

Every connector returns a tidy DataFrame with the columns in ``COLUMNS``.
Optional columns (``member``, ``lead_day``, ``model``) are carried through so
ensembles and multi-model forecasts keep their identity without inventing new
schemas per source.

``day_convention`` says how a source aggregates a value into a day (see
docs/DATA_SOURCES.md). ``issue_time`` is only meaningful for forecast sources:
it records when the forecast was issued (or, when the provider does not expose
the model cycle, the UTC fetch time used as the issue proxy).
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

COLUMNS = [
    "source",
    "variable",
    "unit",
    "location",
    "lat",
    "lon",
    "time",
    "value",
    "quality_flag",
    "member",
    "lead_day",
    "model",
    "day_convention",
    "issue_time",
    "retrieved_at",
]

REQUIRED = {"variable", "location", "lat", "lon", "time", "value"}

DAY_CONVENTION_RE = re.compile(r"^(utc|local_calendar|unknown|obs_hour_\d{1,2})$")


def is_valid_day_convention(value: str) -> bool:
    return bool(DAY_CONVENTION_RE.match(str(value)))

UNITS = {
    "t2m": "degC",
    "t2m_max": "degC",
    "t2m_min": "degC",
    "precip": "mm",
    "soil_moisture": "m3 m-3",
    "oni": "degC",
    "sam": "1",
}

QUALITY_FLAGS = ("ok", "suspect", "fail")


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").tz_localize(None).floor("s")


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the repository root by looking for configs/sources.yaml."""
    candidates: list[Path] = []
    if start is not None:
        candidates.append(Path(start).resolve())
    candidates.append(Path.cwd().resolve())
    candidates.extend(Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "configs" / "sources.yaml").exists():
            return candidate
    raise FileNotFoundError(
        "could not locate the repository root: configs/sources.yaml not found in any parent"
    )


def load_yaml(path: Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_region(path: Path) -> dict[str, Any]:
    region = load_yaml(path)
    for key in ("id", "timezone", "stations"):
        if key not in region:
            raise ValueError(f"region file {path} is missing '{key}'")
    for station in region["stations"]:
        missing = {"id", "name", "lat", "lon"} - set(station)
        if missing:
            raise ValueError(f"station {station.get('id')!r} is missing {sorted(missing)}")
    return region


def normalize(
    frame: pd.DataFrame,
    source: str,
    day_convention: str = "utc",
) -> pd.DataFrame:
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError(f"{source}: connector output is missing {sorted(missing)}")
    if not is_valid_day_convention(day_convention):
        raise ValueError(f"{source}: invalid day_convention {day_convention!r}")

    out = frame.copy()
    out["source"] = source
    out["day_convention"] = day_convention

    if "unit" not in out:
        out["unit"] = pd.NA
    out["unit"] = out["unit"].fillna(out["variable"].map(UNITS))

    if "quality_flag" not in out:
        out["quality_flag"] = "ok"
    out["quality_flag"] = out["quality_flag"].fillna("ok")

    for column, default in (("member", pd.NA), ("lead_day", pd.NA), ("model", pd.NA)):
        if column not in out:
            out[column] = default

    if "issue_time" not in out:
        out["issue_time"] = pd.NaT

    if "retrieved_at" not in out:
        out["retrieved_at"] = utc_now()

    out["time"] = pd.to_datetime(out["time"]).dt.tz_localize(None)
    out["issue_time"] = pd.to_datetime(out["issue_time"], errors="coerce").dt.tz_localize(
        None
    )
    out["retrieved_at"] = pd.to_datetime(out["retrieved_at"]).dt.tz_localize(None)
    for column in ("lat", "lon", "value"):
        out[column] = pd.to_numeric(out[column], errors="coerce")

    out["member"] = out["member"].astype("Int64")
    out["lead_day"] = out["lead_day"].astype("Int64")
    out["model"] = out["model"].astype("string")
    return out[COLUMNS].reset_index(drop=True)


class Connector(ABC):
    """Base class for every source connector."""

    source: str
    tier: int = 99
    day_convention: str = "utc"

    @abstractmethod
    def fetch(self, region: dict[str, Any], **options: Any) -> pd.DataFrame:
        """Download and parse the source. Must return the REQUIRED columns."""

    def fetch_normalized(
        self,
        region: dict[str, Any],
        day_convention: str | None = None,
        **options: Any,
    ) -> pd.DataFrame:
        convention = day_convention or self.day_convention
        return normalize(self.fetch(region, **options), self.source, convention)

    def run(
        self,
        region: dict[str, Any],
        out_dir: Path,
        day_convention: str | None = None,
        **options: Any,
    ) -> Path:
        frame = self.fetch_normalized(region, day_convention=day_convention, **options)
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{self.source}.parquet"
        frame.to_parquet(path, index=False)
        return path
