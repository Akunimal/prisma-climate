"""Global ERA5 historical batch ingestion module (Priority 2).

Provides chunked, rate-paced, resilient batch ingestion of historical ERA5 reanalysis
from Open-Meteo for the 113 global ICAO aerodrome stations (and optional catch-up
for the 19 Argentina stations):
- Station & date chunking to respect Open-Meteo request limits.
- Inter-request rate pacing with configurable sleep.
- HTTP 429/5xx exponential backoff with Retry-After header parsing.
- Resumable checkpointing via staged chunk parquets and atomic manifest updates.
- 100% schema parity with data/raw/openmeteo-era5.parquet.
- Inner-join compatibility with backend/src/prisma/report/metar_discrepancies.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import random
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from .base import find_repo_root, load_all_regions

logger = logging.getLogger(__name__)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_STATION_BATCH_SIZE = 10
DEFAULT_CHUNK_DAYS = 365
DEFAULT_SLEEP_SECONDS = 2.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_BACKOFF_FACTOR = 1.0
DEFAULT_MAX_BACKOFF_SECONDS = 60.0

VARIABLES_MAP = {
    "temperature_2m_max": ("t2m_max", "degC"),
    "temperature_2m_min": ("t2m_min", "degC"),
    "precipitation_sum": ("precip", "mm"),
}

EXPECTED_COLUMNS = [
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


@dataclass(frozen=True)
class Era5Chunk:
    """A single batch slice of stations and date range."""

    chunk_id: str
    stations: tuple[dict[str, Any], ...]
    start_date: str
    end_date: str


def parse_retry_after(header_val: str | None) -> float | None:
    """Parse integer seconds or HTTP-date from Retry-After response header."""
    if not header_val:
        return None
    val_str = header_val.strip()
    try:
        val = float(val_str)
        return max(0.0, val)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(val_str)
        now_dt = datetime.now(UTC)
        diff = (dt - now_dt).total_seconds()
        return max(0.0, diff)
    except Exception:
        return None


def plan_chunks(
    stations: Sequence[dict[str, Any]],
    start_date: str,
    end_date: str,
    *,
    station_batch_size: int = DEFAULT_STATION_BATCH_SIZE,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
) -> list[Era5Chunk]:
    """Partition stations and dates into deterministic, bounded chunk slices."""
    if not stations:
        return []
    if station_batch_size <= 0:
        raise ValueError(f"station_batch_size must be positive, got {station_batch_size}")
    if chunk_days <= 0:
        raise ValueError(f"chunk_days must be positive, got {chunk_days}")

    # Deterministic station sorting
    sorted_stations = sorted(stations, key=lambda s: str(s.get("id", s.get("name", ""))))

    # Station batching
    n_batches = math.ceil(len(sorted_stations) / station_batch_size)
    station_batches: list[tuple[dict[str, Any], ...]] = []
    for b_idx in range(n_batches):
        batch = tuple(
            sorted_stations[b_idx * station_batch_size : (b_idx + 1) * station_batch_size]
        )
        station_batches.append(batch)

    # Date slicing
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    if start_ts > end_ts:
        raise ValueError(f"start_date ({start_date}) cannot be after end_date ({end_date})")

    date_ranges: list[tuple[str, str]] = []
    curr = start_ts
    while curr <= end_ts:
        nxt = min(end_ts, curr + pd.Timedelta(days=chunk_days - 1))
        date_ranges.append((curr.strftime("%Y-%m-%d"), nxt.strftime("%Y-%m-%d")))
        curr = nxt + pd.Timedelta(days=1)

    # Generate chunk list
    chunks: list[Era5Chunk] = []
    for b_idx, s_batch in enumerate(station_batches):
        for d_idx, (d_start, d_end) in enumerate(date_ranges):
            chunk_id = f"chunk_b{b_idx:03d}_d{d_idx:03d}_{d_start}_{d_end}"
            chunks.append(
                Era5Chunk(
                    chunk_id=chunk_id,
                    stations=s_batch,
                    start_date=d_start,
                    end_date=d_end,
                )
            )
    return chunks


def parse_era5_payload(
    payload: Any,
    stations: Sequence[dict[str, Any]],
    *,
    retrieved_at: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Convert Open-Meteo archive JSON response into schema-conforming long frame."""
    retrieved = pd.Timestamp(
        retrieved_at if retrieved_at is not None else datetime.now(UTC)
    ).tz_localize(None)

    # Handle multi-coordinate (list of dicts) vs single-coordinate (dict)
    station_payloads: list[dict[str, Any]]
    if isinstance(payload, list):
        station_payloads = payload
    elif isinstance(payload, dict):
        station_payloads = [payload]
    else:
        raise ValueError(f"unexpected payload type: {type(payload)}")

    if len(station_payloads) != len(stations):
        raise ValueError(
            f"payload length ({len(station_payloads)}) != station count ({len(stations)})"
        )

    rows: list[dict[str, Any]] = []
    for st, p in zip(stations, station_payloads, strict=True):
        st_name = str(st["name"])
        st_lat = float(st["lat"])
        st_lon = float(st["lon"])
        daily = p.get("daily") or {}
        if "time" not in daily:
            continue
        times = daily["time"]
        for raw_var, (canonical_var, unit) in VARIABLES_MAP.items():
            if raw_var not in daily:
                continue
            vals = daily[raw_var]
            for t_str, v in zip(times, vals, strict=False):
                if v is None:
                    num_val = float("nan")
                else:
                    try:
                        num_val = float(v)
                    except (ValueError, TypeError):
                        num_val = float("nan")

                rows.append(
                    {
                        "source": "openmeteo-era5",
                        "variable": canonical_var,
                        "unit": unit,
                        "location": st_name,
                        "lat": st_lat,
                        "lon": st_lon,
                        "time": pd.Timestamp(t_str).normalize(),
                        "value": num_val,
                        "quality_flag": "ok",
                        "member": 0,
                        "lead_day": pd.NA,
                        "model": "era5",
                        "day_convention": "local_calendar",
                        "issue_time": pd.NaT,
                        "retrieved_at": retrieved,
                    }
                )

    if not rows:
        return _empty_era5_frame()

    df = pd.DataFrame(rows)
    return _coerce_era5_dtypes(df)


def _empty_era5_frame() -> pd.DataFrame:
    df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    return _coerce_era5_dtypes(df)


def _coerce_era5_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce DataFrame to exact types of data/raw/openmeteo-era5.parquet."""
    out = df[EXPECTED_COLUMNS].copy()
    out["source"] = out["source"].astype("string")
    out["variable"] = out["variable"].astype("string")
    out["unit"] = out["unit"].astype("string")
    out["location"] = out["location"].astype("string")
    out["lat"] = out["lat"].astype("float64")
    out["lon"] = out["lon"].astype("float64")
    out["time"] = pd.to_datetime(out["time"]).astype("datetime64[us]")
    out["value"] = out["value"].astype("float64")
    out["quality_flag"] = out["quality_flag"].astype("string")
    out["member"] = out["member"].astype("Int64")
    out["lead_day"] = out["lead_day"].astype("Int64")
    out["model"] = out["model"].astype("string")
    out["day_convention"] = out["day_convention"].astype("string")
    out["issue_time"] = pd.to_datetime(out["issue_time"]).astype("datetime64[ns]")
    out["retrieved_at"] = pd.to_datetime(out["retrieved_at"]).astype("datetime64[us]")
    return out


def validate_era5_schema(df: pd.DataFrame) -> None:
    """Validate DataFrame against strict schema requirements."""
    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"ERA5 frame missing required columns: {missing}")

    if not pd.api.types.is_datetime64_any_dtype(df["time"]):
        raise TypeError(f"expected datetime64 for 'time', got {df['time'].dtype}")
    if not pd.api.types.is_float_dtype(df["value"]):
        raise TypeError(f"expected float for 'value', got {df['value'].dtype}")
    if not pd.api.types.is_string_dtype(df["location"]):
        raise TypeError(f"expected string for 'location', got {df['location'].dtype}")


class CheckpointManager:
    """Manages staged chunk parquets and persistent manifest for resumable runs."""

    def __init__(self, checkpoint_dir: Path) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.chunks_dir = self.checkpoint_dir / "chunks"
        self.manifest_file = self.checkpoint_dir / "manifest.json"
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        self._completed: set[str] = set()
        self._load_manifest()

    def _load_manifest(self) -> None:
        if self.manifest_file.is_file():
            try:
                data = json.loads(self.manifest_file.read_text(encoding="utf-8"))
                chunks = data.get("completed_chunks", [])
                self._completed = set(chunks)
            except Exception as exc:
                logger.warning("failed to read checkpoint manifest (%s), resetting", exc)
                self._completed = set()

    def is_completed(self, chunk_id: str) -> bool:
        if chunk_id not in self._completed:
            return False
        chunk_file = self.chunks_dir / f"{chunk_id}.parquet"
        return chunk_file.is_file() and chunk_file.stat().st_size > 0

    def record_completed_chunk(self, chunk_id: str, df: pd.DataFrame) -> Path:
        chunk_file = self.chunks_dir / f"{chunk_id}.parquet"
        tmp_file = self.chunks_dir / f"{chunk_id}.tmp.{os.getpid()}"
        df.to_parquet(tmp_file, index=False)
        tmp_file.replace(chunk_file)

        self._completed.add(chunk_id)
        manifest_tmp = self.checkpoint_dir / f"manifest.tmp.{os.getpid()}"
        manifest_data = {
            "completed_chunks": sorted(self._completed),
            "last_updated": datetime.now(UTC).isoformat(),
        }
        manifest_tmp.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        manifest_tmp.replace(self.manifest_file)
        return chunk_file

    def get_staged_files(self) -> list[Path]:
        return sorted(self.chunks_dir.glob("*.parquet"))


def fetch_chunk_with_retry(
    chunk: Era5Chunk,
    *,
    http_get: Callable[[str, dict[str, Any]], Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
    max_backoff_seconds: float = DEFAULT_MAX_BACKOFF_SECONDS,
) -> Any:
    """Fetch chunk payload from Open-Meteo archive API with resilient backoff."""
    params: dict[str, Any] = {
        "latitude": [st["lat"] for st in chunk.stations],
        "longitude": [st["lon"] for st in chunk.stations],
        "start_date": chunk.start_date,
        "end_date": chunk.end_date,
        "daily": ",".join(VARIABLES_MAP),
        "timezone": "UTC",
        "temperature_unit": "celsius",
        "models": "era5",
    }

    # If single station, pass single floats to adhere to standard API conventions
    if len(chunk.stations) == 1:
        params["latitude"] = chunk.stations[0]["lat"]
        params["longitude"] = chunk.stations[0]["lon"]

    def _default_get(url: str, p: dict[str, Any]) -> Any:
        resp = requests.get(url, params=p, timeout=120)
        if resp.status_code == 429:
            retry_after = parse_retry_after(resp.headers.get("Retry-After"))
            err = requests.HTTPError(f"429 Client Error: Too Many Requests for url: {resp.url}")
            err.response = resp
            err.retry_after = retry_after
            raise err
        resp.raise_for_status()
        return resp.json()

    getter = http_get or _default_get

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            return getter(ARCHIVE_URL, params)
        except requests.HTTPError as exc:
            status = getattr(exc.response, "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                # Fatal client error (e.g. 400 Bad Request) - do not retry
                raise
            last_error = exc
            retry_after = getattr(exc, "retry_after", None)
            jitter = random.uniform(0.1, 0.5)
            calc_backoff = min(
                max_backoff_seconds, (backoff_factor * (2 ** (attempt - 1))) + jitter
            )
            wait_time = max(retry_after or 0.0, calc_backoff)
            logger.warning(
                "chunk %s attempt %d failed (%s); backing off for %.2fs",
                chunk.chunk_id,
                attempt,
                exc,
                wait_time,
            )
            sleep_fn(wait_time)
        except Exception as exc:
            last_error = exc
            jitter = random.uniform(0.1, 0.5)
            wait_time = min(max_backoff_seconds, (backoff_factor * (2 ** (attempt - 1))) + jitter)
            logger.warning(
                "chunk %s attempt %d network exception (%s); backing off for %.2fs",
                chunk.chunk_id,
                attempt,
                exc,
                wait_time,
            )
            sleep_fn(wait_time)

    raise RuntimeError(f"chunk {chunk.chunk_id} failed after {max_retries} attempts: {last_error}")


def merge_and_save(
    staged_files: Sequence[Path],
    target_parquet: Path,
    *,
    existing_parquet: Path | None = None,
) -> Path:
    """Merge staged chunk parquets into target, deduplicating on (location, variable, time)."""
    target = Path(target_parquet)
    frames: list[pd.DataFrame] = []

    ref_path = existing_parquet if existing_parquet is not None else target
    if ref_path.is_file():
        frames.append(pd.read_parquet(ref_path))

    for sf in staged_files:
        frames.append(pd.read_parquet(sf))

    if not frames:
        merged = _empty_era5_frame()
    else:
        merged = pd.concat(frames, ignore_index=True)
        # Deduplicate on (location, variable, time) keeping latest
        merged = merged.drop_duplicates(subset=["location", "variable", "time"], keep="last")
        merged = merged.sort_values(["location", "variable", "time"]).reset_index(drop=True)

    validate_era5_schema(merged)
    merged = _coerce_era5_dtypes(merged)

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_target = target.parent / f"{target.name}.tmp.{os.getpid()}"
    merged.to_parquet(tmp_target, index=False)
    tmp_target.replace(target)
    return target


def run_batch_ingest(
    *,
    root: Path | None = None,
    scope: str = "global",
    start_date: str = "1996-01-01",
    end_date: str | None = None,
    station_batch_size: int = DEFAULT_STATION_BATCH_SIZE,
    chunk_days: int = DEFAULT_CHUNK_DAYS,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    output_path: Path | None = None,
    checkpoint_dir: Path | None = None,
    resume: bool = True,
    dry_run: bool = False,
    http_get: Callable[[str, dict[str, Any]], Any] | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Execute or plan the batch ingestion run."""
    root = Path(root) if root is not None else find_repo_root()
    all_reg = load_all_regions(root)
    all_stations = all_reg["stations"]

    if scope == "global":
        stations = [s for s in all_stations if s.get("region") != "argentina"]
    elif scope == "argentina":
        stations = [s for s in all_stations if s.get("region") == "argentina"]
    elif scope == "all":
        stations = all_stations
    else:
        raise ValueError(f"unknown scope {scope!r}; must be 'global', 'argentina', or 'all'")

    if end_date is None:
        end_date = (datetime.now(UTC).date() - pd.Timedelta(days=6)).isoformat()

    chunks = plan_chunks(
        stations,
        start_date,
        end_date,
        station_batch_size=station_batch_size,
        chunk_days=chunk_days,
    )

    out_file = output_path or (root / "data" / "raw" / "openmeteo-era5.parquet")
    chk_dir = checkpoint_dir or (root / "data" / "raw" / "_era5_checkpoint")

    plan_summary = {
        "scope": scope,
        "station_count": len(stations),
        "start_date": start_date,
        "end_date": end_date,
        "chunk_count": len(chunks),
        "station_batch_size": station_batch_size,
        "chunk_days": chunk_days,
        "target_file": str(out_file),
        "checkpoint_dir": str(chk_dir),
    }

    if dry_run:
        return {"status": "dry_run", "plan": plan_summary}

    mgr = CheckpointManager(chk_dir)
    completed_now = 0
    skipped_resume = 0

    for idx, chunk in enumerate(chunks, start=1):
        if resume and mgr.is_completed(chunk.chunk_id):
            skipped_resume += 1
            continue

        payload = fetch_chunk_with_retry(
            chunk,
            http_get=http_get,
            sleep_fn=sleep_fn,
            max_retries=max_retries,
        )
        df_chunk = parse_era5_payload(payload, chunk.stations)
        validate_era5_schema(df_chunk)
        mgr.record_completed_chunk(chunk.chunk_id, df_chunk)
        completed_now += 1

        if idx < len(chunks):
            sleep_fn(sleep_seconds)

    staged = mgr.get_staged_files()
    merge_and_save(staged, out_file)

    return {
        "status": "completed",
        "plan": plan_summary,
        "chunks_completed": completed_now,
        "chunks_resumed": skipped_resume,
        "total_staged_files": len(staged),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument(
        "--scope",
        choices=["global", "argentina", "all"],
        default="global",
        help="scope of stations to ingest (default: global for 113 ICAO stations)",
    )
    parser.add_argument("--start-date", type=str, default="1996-01-01")
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--station-batch-size", type=int, default=DEFAULT_STATION_BATCH_SIZE)
    parser.add_argument("--chunk-days", type=int, default=DEFAULT_CHUNK_DAYS)
    parser.add_argument("--sleep-seconds", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--max-retries", type=int, default=DEFAULT_MAX_RETRIES)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--no-resume", action="store_true", default=False)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="print chunk plan and exit without network calls or file writes",
    )

    args = parser.parse_args(argv)
    res = run_batch_ingest(
        root=args.root,
        scope=args.scope,
        start_date=args.start_date,
        end_date=args.end_date,
        station_batch_size=args.station_batch_size,
        chunk_days=args.chunk_days,
        sleep_seconds=args.sleep_seconds,
        max_retries=args.max_retries,
        output_path=args.output,
        checkpoint_dir=args.checkpoint_dir,
        resume=not args.no_resume,
        dry_run=args.dry_run,
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
