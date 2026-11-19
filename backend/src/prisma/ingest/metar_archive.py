"""Isolated METAR observation reference archiver for PRISMA Climate.

Partitions and stores raw METAR observations under ``observations/metar/<region>/<year>/<station_id>.parquet``.

Key Safeguards & Invariants:
1. Timestamp Keying: Observation timestamps and year partition paths are derived
   strictly from the METAR observation time (``obsTime`` / ``valid_time``), NEVER
   from the system wall-clock.
2. Sliding Window: Constrained to NOAA AWC retention window (24 to 72 hours).
   Zero claims of historical observation backfill beyond the sliding window.
3. No Imputation: Missing values (nil reports, missing temperature) are stored as
   null/NaN and are NEVER forward-filled, imputed, or interpolated.
4. SMN Isolation: Writes ONLY to ``observations/metar/``. Absolutely forbidden
   from touching ``observations/smn/``, ``observations/hourly/``, or ``observations/daily/``.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml

from prisma.ingest.base import find_repo_root, load_all_regions, load_region
from prisma.ingest.metar import (
    DEFAULT_TIMEOUT,
    USER_AGENT,
    create_resilient_session,
    fetch_awc_batch,
    parse_metar_precip,
    parse_metar_temperature,
)

logger = logging.getLogger(__name__)

FORBIDDEN_STORES = ("observations/smn", "observations/hourly", "observations/daily")
MIN_RETENTION_HOURS = 24
MAX_RETENTION_HOURS = 72


def validate_target_path(path: Path) -> None:
    """Ensure target path complies with SMN isolation safeguards."""
    norm = path.as_posix()
    for forbidden in FORBIDDEN_STORES:
        if forbidden in norm:
            raise ValueError(
                f"Violation of isolation invariant: target path '{path}' touches forbidden store '{forbidden}'"
            )
    if "observations/metar" not in norm:
        raise ValueError(f"Target path '{path}' must be rooted under 'observations/metar/'")


def validate_retention_hours(hours: int) -> int:
    """Verify hours window stays within the physical NOAA AWC sliding retention window."""
    if not (MIN_RETENTION_HOURS <= hours <= MAX_RETENTION_HOURS):
        raise ValueError(
            f"Hours lookback must be within sliding METAR retention window [{MIN_RETENTION_HOURS}, {MAX_RETENTION_HOURS}], "
            f"got {hours}. Historical backfill beyond 72h is not supported by the AWC reference API."
        )
    return hours


def parse_raw_reports_to_frame(
    raw_reports: list[dict[str, Any]],
    station_lookup: dict[str, dict[str, Any]],
    retrieved_at_utc: str,
) -> pd.DataFrame:
    """Normalize raw AWC JSON reports into tabular records.
    
    Timestamps are derived STRICTLY from obsTime (never wall clock).
    Missing temperatures remain None (no imputation).
    """
    rows: list[dict[str, Any]] = []

    for rep in raw_reports:
        icao = (rep.get("icaoId") or "").strip().upper()
        if not icao or icao not in station_lookup:
            continue

        st_meta = station_lookup[icao]
        obs_epoch = rep.get("obsTime")
        if obs_epoch is None:
            continue

        try:
            obs_epoch_int = int(obs_epoch)
            obs_dt = datetime.fromtimestamp(obs_epoch_int, tz=UTC)
            obs_time_iso = obs_dt.isoformat().replace("+00:00", "Z")
            partition_year = obs_dt.year
        except (ValueError, TypeError, OverflowError):
            continue

        raw_ob = rep.get("rawOb")
        num_temp = rep.get("temp")
        temp_c = parse_metar_temperature(raw_ob, num_temp)

        num_precip = rep.get("precip")
        precip_mm, _ = parse_metar_precip(raw_ob, num_precip)

        rows.append({
            "station_id": st_meta["id"],
            "icao": icao,
            "region": st_meta.get("region", "unknown"),
            "obs_time_utc": obs_time_iso,
            "obs_epoch": obs_epoch_int,
            "partition_year": partition_year,
            "temperature_c": temp_c,
            "precip_mm": precip_mm,
            "raw_metar": raw_ob or "",
            "source": "noaa_awc_metar",
            "retrieved_at_utc": retrieved_at_utc,
        })

    if not rows:
        return pd.DataFrame(columns=[
            "station_id", "icao", "region", "obs_time_utc", "obs_epoch",
            "partition_year", "temperature_c", "precip_mm", "raw_metar",
            "source", "retrieved_at_utc"
        ])

    return pd.DataFrame(rows)


def write_partitioned_observations(
    df: pd.DataFrame,
    base_dir: Path,
) -> list[Path]:
    """Write observations partitioned by region/year/station_id.parquet.
    
    Merges with existing file if present, deduplicating strictly by (station_id, obs_epoch).
    """
    if df.empty:
        return []

    written_paths: list[Path] = []
    groups = df.groupby(["region", "partition_year", "station_id"])

    for (region, year, st_id), group_df in groups:
        target_dir = base_dir / "observations" / "metar" / str(region) / str(year)
        validate_target_path(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        target_file = target_dir / f"{st_id}.parquet"
        validate_target_path(target_file)

        cols_to_write = [
            "station_id", "icao", "region", "obs_time_utc", "obs_epoch",
            "temperature_c", "precip_mm", "raw_metar", "source", "retrieved_at_utc"
        ]
        new_records = group_df[cols_to_write].copy()

        if target_file.exists():
            existing_df = pd.read_parquet(target_file)
            combined = pd.concat([existing_df, new_records], ignore_index=True)
            combined = combined.drop_duplicates(subset=["station_id", "obs_epoch"], keep="last")
            combined = combined.sort_values("obs_epoch").reset_index(drop=True)
            combined.to_parquet(target_file, index=False)
        else:
            new_records = new_records.sort_values("obs_epoch").reset_index(drop=True)
            new_records.to_parquet(target_file, index=False)

        written_paths.append(target_file)

    return written_paths


def archive_metar_region(
    region_slug: str,
    root: Path | None = None,
    hours: int = 48,
    out_dir: Path | None = None,
    session: requests.Session | None = None,
    raw_reports: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Execute isolated METAR observation archiving for a specified region or all regions."""
    hours = validate_retention_hours(hours)
    repo_root = root or find_repo_root()
    base_out = out_dir or repo_root

    validate_target_path(base_out / "observations" / "metar")

    regions_list: list[dict[str, Any]] = []
    if region_slug in ("all", "active"):
        sources_cfg = repo_root / "configs" / "sources.yaml"
        blocked_slugs: set[str] = set()
        if sources_cfg.exists():
            with open(sources_cfg, encoding="utf-8") as f:
                raw_sources = yaml.safe_load(f).get("sources", [])
            blocked_slugs = {
                s["id"].replace("metar-", "").replace("-", "_")
                for s in raw_sources
                if s.get("status") == "blocked" and s.get("id", "").startswith("metar-")
            }

        regions_dir = repo_root / "configs" / "regions"
        for p in sorted(regions_dir.glob("*.yaml")):
            if p.stem == "argentina":
                continue  # SMN pipeline handles Argentina observations
            if p.stem in blocked_slugs:
                logger.info("Skipping blocked region '%s' from METAR archiving", p.stem)
                continue
            reg = load_region(p)
            for st in reg.get("stations", []):
                st.setdefault("region", reg.get("id"))
            regions_list.append(reg)
    elif "," in region_slug:
        for slug in region_slug.split(","):
            slug = slug.strip()
            path = repo_root / "configs" / "regions" / f"{slug}.yaml"
            if not path.exists():
                raise FileNotFoundError(f"Region config not found: {path}")
            reg = load_region(path)
            for st in reg.get("stations", []):
                st.setdefault("region", reg.get("id"))
            regions_list.append(reg)
    else:
        path = repo_root / "configs" / "regions" / f"{region_slug}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Region config not found: {path}")
        reg = load_region(path)
        # Ensure stations have region key
        for st in reg.get("stations", []):
            st.setdefault("region", reg.get("id"))
        regions_list = [reg]

    station_lookup: dict[str, dict[str, Any]] = {}
    for reg in regions_list:
        for st in reg.get("stations", []):
            icao = st.get("icao")
            if icao:
                station_lookup[icao.upper()] = st

    retrieved_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if raw_reports is None:
        icaos = sorted(station_lookup.keys())
        sess = session or create_resilient_session()
        raw_reports = fetch_awc_batch(icaos, hours=hours, session=sess, batch_size=3)

    df = parse_raw_reports_to_frame(raw_reports, station_lookup, retrieved_at)
    written = write_partitioned_observations(df, base_out)

    return {
        "region": region_slug,
        "hours": hours,
        "retrieved_at_utc": retrieved_at,
        "total_reports_fetched": len(raw_reports),
        "total_records_normalized": len(df),
        "partitioned_files_written": [str(p) for p in written],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        default="all",
        help="Region slug to archive (or 'all')",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=48,
        help="Sliding METAR observation window [24..72] hours",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Base directory for output storage (defaults to repo root)",
    )
    args = parser.parse_args(argv)

    try:
        res = archive_metar_region(
            region_slug=args.region,
            hours=args.hours,
            out_dir=Path(args.out_dir) if args.out_dir else None,
        )
        print(f"METAR archiving completed for {args.region}: {res['total_records_normalized']} records across {len(res['partitioned_files_written'])} files.")
        return 0
    except Exception as exc:
        logger.error("METAR archive failed: %s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
