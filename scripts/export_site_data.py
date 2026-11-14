"""Export the static JSON tree the app reads (GitHub Pages, no server).

Reads, without a token, the latest canonical ensemble forecast
(``forecasts/<issue_date>/openmeteo-ensemble_<issue_date>.parquet``) and the
latest archived SMN ``regtemp`` snapshot
(``observations/smn/regtemp/<last_fecha>/regtemp.zip``) from the public Hugging
Face dataset, and writes a small versioned JSON tree:

- ``latest.json`` — schema version, issue date/time, model ids, station list.
- ``stations/<station_id>.json`` — per variable, per lead day and per model,
  member quantiles; the last 30 days of SMN observed t2m_max/t2m_min.
- ``about.json`` — sources, licences, attribution and the status block.

Models are never pooled. The 80 % member rule of the 2026-11-14 amendment
(``docs/EVALUATION_PROTOCOL.md``) is applied per case: a case whose usable
members (``quality_flag == ok`` and non-null) are below 80 % of the model's
nominal count is exported as ``missing_members`` with null quantiles, never
filled.

No skill metric is computed here. The exported numbers are descriptive
statistics of the raw ensemble members and the archived observations;
verification results stay gated on 15 distinct issue dates.

Usage::

    uv run --project backend python scripts/export_site_data.py --out-dir data

The HF token is never read: the listing and download calls run unauthenticated
against the public dataset.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from prisma.ingest.base import find_repo_root, load_region
from prisma.verify.run import MEMBER_FRACTION, _parse_payload_zip, load_member_counts

SCHEMA_VERSION = "1.0"
DEFAULT_REPO = "Akunimal/prisma-climate"
DATASET_URL = "https://huggingface.co/datasets/Akunimal/prisma-climate"
REGION_REL = Path("configs") / "regions" / "argentina.yaml"
RESOLUTION_REL = Path("results") / "regtemp_names" / "region_resolution.csv"
VARIABLES = ("t2m_max", "t2m_min", "precip")
QUANTILES = (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))
PRECIP_THRESHOLDS = (("fraction_ge_1mm", 1.0), ("fraction_ge_10mm", 10.0))
ROUND_DIGITS = 2
OBSERVED_DAYS = 30

ABOUT_SOURCES = [
    {
        "id": "openmeteo-ensemble",
        "name": "Open-Meteo Ensemble API",
        "role": "raw ensemble forecast members (GFS and ECMWF IFS)",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Weather data by Open-Meteo.com",
        "attribution_url": "https://open-meteo.com/",
        "note": "free tier is non-commercial only; attribution link required next to the data",
    },
    {
        "id": "smn-argentina",
        "name": "Servicio Meteorológico Nacional (Argentina)",
        "role": "station observations (regtemp 365-day snapshot)",
        "licence": "CC BY 2.5 AR",
        "licence_url": "https://creativecommons.org/licenses/by/2.5/ar/",
        "attribution": "Servicio Meteorológico Nacional (SMN), Argentina",
        "attribution_url": "https://www.smn.gob.ar/",
        "note": "values archived as served; gaps are never filled",
    },
]


def list_archive_paths() -> list[str]:
    """Unauthenticated listing of the public HF dataset (no token read).

    ``token=False`` also stops ``huggingface_hub`` from falling back to a cached
    login token on disk: every read here is public.
    """
    os.environ.pop("HF_TOKEN", None)
    from huggingface_hub import list_repo_files

    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)
    return list(list_repo_files(repo, repo_type="dataset", token=False))


def _parts(raw: Any) -> list[str]:
    return str(raw).replace("\\", "/").split("/")


def latest_forecast(listing: Iterable[str]) -> tuple[str, str]:
    """Latest ``forecasts/<date>/<file>.parquet`` entry: (issue_date, path)."""
    by_date: dict[str, list[str]] = {}
    for raw in listing:
        parts = _parts(raw)
        if (
            len(parts) == 3
            and parts[0] == "forecasts"
            and parts[2].endswith(".parquet")
        ):
            by_date.setdefault(parts[1], []).append(str(raw))
    if not by_date:
        raise ValueError(
            "no forecasts/<issue_date>/*.parquet in the public archive listing"
        )
    issue_date = max(by_date)
    paths = sorted(by_date[issue_date])
    if len(paths) != 1:
        raise ValueError(
            f"expected one canonical forecast for {issue_date}, found {len(paths)}"
        )
    return issue_date, paths[0]


def latest_regtemp(listing: Iterable[str]) -> tuple[str, str]:
    """Latest ``observations/smn/regtemp/<date>/regtemp.zip``: (date, path)."""
    by_date: dict[str, list[str]] = {}
    for raw in listing:
        parts = _parts(raw)
        if (
            len(parts) == 5
            and parts[0] == "observations"
            and parts[1] == "smn"
            and parts[2] == "regtemp"
            and parts[4] == "regtemp.zip"
        ):
            by_date.setdefault(parts[3], []).append(str(raw))
    if not by_date:
        raise ValueError(
            "no observations/smn/regtemp/<date>/regtemp.zip in the public listing"
        )
    snapshot_date = max(by_date)
    paths = sorted(by_date[snapshot_date])
    if len(paths) != 1:
        raise ValueError(
            f"expected one regtemp.zip for {snapshot_date}, found {len(paths)}"
        )
    return snapshot_date, paths[0]


def member_share_ok(present: int, nominal: int) -> bool:
    """At least 80 % of the nominal member count present (2026-11-14 rule 1)."""
    return present * MEMBER_FRACTION[1] >= nominal * MEMBER_FRACTION[0]


def _rounded(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not np.isfinite(number):
        return None
    return round(number, ROUND_DIGITS)


def _quantiles(values: np.ndarray) -> dict[str, float | None]:
    block: dict[str, float | None] = {
        name: _rounded(np.percentile(values, q)) for name, q in QUANTILES
    }
    block["min"] = _rounded(values.min())
    block["max"] = _rounded(values.max())
    return block


def _iso_utc(stamp: Any) -> str:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def forecast_cases(
    station_frame: pd.DataFrame,
    models: list[str],
    member_counts: Mapping[str, int],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Per variable/model/lead quantile cases for one station."""
    work = station_frame.loc[
        station_frame["variable"].isin(VARIABLES) & station_frame["model"].isin(models)
    ].copy()
    work["time"] = pd.to_datetime(work["time"])
    forecast: dict[str, dict[str, list[dict[str, Any]]]] = {
        variable: {model: [] for model in models} for variable in VARIABLES
    }
    if work.empty:
        return forecast
    for (variable, model, lead_day), group in work.groupby(
        ["variable", "model", "lead_day"], sort=True
    ):
        dates = sorted(pd.Timestamp(value) for value in group["time"].unique())
        if len(dates) != 1:
            raise ValueError(
                f"case {variable}/{model}/lead {lead_day} carries "
                f"{len(dates)} valid dates; exactly one is required"
            )
        nominal = member_counts.get(str(model))
        if nominal is None:
            raise ValueError(
                f"no nominal member count for model {model!r} in "
                "configs/sources.yaml options.member_counts"
            )
        usable = group.loc[
            group["value"].notna() & group["quality_flag"].eq("ok")
        ]
        n_present = int(usable["value"].size)
        case: dict[str, Any] = {
            "lead_day": int(lead_day),
            "valid_local_date": dates[0].date().isoformat(),
            "n_members": n_present,
            "nominal_members": int(nominal),
        }
        if member_share_ok(n_present, nominal):
            values = usable["value"].to_numpy(dtype=float)
            case["status"] = "ok"
            case.update(_quantiles(values))
            if variable == "precip":
                for key, threshold in PRECIP_THRESHOLDS:
                    case[key] = round(float((values >= threshold).mean()), ROUND_DIGITS)
        else:
            case["status"] = "missing_members"
            case.update({name: None for name, _ in QUANTILES})
            case["min"] = None
            case["max"] = None
            if variable == "precip":
                for key, _threshold in PRECIP_THRESHOLDS:
                    case[key] = None
        forecast[str(variable)][str(model)].append(case)
    return forecast


def observed_series(
    regtemp: pd.DataFrame, payload_name: str | None
) -> list[dict[str, Any]]:
    """Last 30 archived SMN days for one station (local calendar dates)."""
    if not payload_name:
        return []
    series = regtemp.loc[regtemp["smn_name"].eq(payload_name)].copy()
    if series.empty:
        return []
    series["time"] = pd.to_datetime(series["time"])
    series = series.sort_values("time").tail(OBSERVED_DAYS)
    return [
        {
            "date": pd.Timestamp(day).date().isoformat(),
            "t2m_max": _rounded(tmax),
            "t2m_min": _rounded(tmin),
        }
        for day, tmax, tmin in series[["time", "t2m_max", "t2m_min"]].itertuples(
            index=False
        )
    ]


def load_resolution(root: Path) -> dict[str, str]:
    """Region station name -> regtemp payload name (committed resolve table)."""
    path = root / RESOLUTION_REL
    if not path.is_file():
        raise FileNotFoundError(
            f"{RESOLUTION_REL} not found: run scripts/reconcile_regtemp_names.py"
        )
    table = pd.read_csv(path)
    resolved = table.loc[table["status"].astype(str).str.startswith("resolved")]
    return {
        str(row.location): str(row.regtemp_name) for row in resolved.itertuples(index=False)
    }


def _write_json(path: Path, document: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(document, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def export_site_data(
    *,
    root: Path | None = None,
    list_files: Callable[[], list[str]] | None = None,
    download: Callable[[str, str], Path] | None = None,
    out_dir: Path,
    generated_at: Any | None = None,
) -> list[Path]:
    """Run the export; ``list_files``/``download``/``root`` are injectable."""
    root = Path(root) if root is not None else find_repo_root()
    listing = list(list_files()) if list_files is not None else list_archive_paths()
    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)
    if download is None:
        os.environ.pop("HF_TOKEN", None)
        from huggingface_hub import hf_hub_download

        def fetch(repo_id: str, repo_path: str) -> Path:
            return Path(hf_hub_download(repo_id, repo_path, repo_type="dataset", token=False))

        fetch_file = fetch
    else:
        fetch_file = download

    issue_date, forecast_path = latest_forecast(listing)
    regtemp_date, regtemp_path = latest_regtemp(listing)

    frame = pd.read_parquet(fetch_file(repo, forecast_path))
    stamps = sorted(set(pd.to_datetime(frame["issue_time"], utc=True)))
    if len(stamps) != 1:
        raise ValueError(
            f"{forecast_path}: expected one issue_time, found {len(stamps)}"
        )
    issue_time = stamps[0]
    if issue_time.strftime("%Y-%m-%d") != issue_date:
        raise ValueError(
            f"{forecast_path}: issue_time {issue_time} does not match the "
            f"issue-date folder {issue_date}"
        )
    models = sorted(str(model) for model in frame["model"].dropna().unique())
    if not models:
        raise ValueError(f"{forecast_path}: no models in the forecast")
    member_counts = load_member_counts(root)
    for model in models:
        if model not in member_counts:
            raise ValueError(
                f"no nominal member count for model {model!r} in "
                "configs/sources.yaml options.member_counts"
            )

    region = load_region(root / REGION_REL)
    resolution = load_resolution(root)
    regtemp_frame = _parse_payload_zip(Path(fetch_file(repo, regtemp_path)), "regtemp")

    stamp = _iso_utc(generated_at if generated_at is not None else datetime.now(UTC))
    issue_time_text = _iso_utc(issue_time)
    stations_meta: list[dict[str, Any]] = []
    station_documents: list[tuple[str, dict[str, Any]]] = []
    for station in region["stations"]:
        station_id = str(station["id"])
        name = str(station["name"])
        meta = {
            "id": station_id,
            "name": name,
            "lat": float(station["lat"]),
            "lon": float(station["lon"]),
            "climate_zone": str(station.get("zone", "")),
        }
        stations_meta.append(meta)
        subset = frame.loc[frame["location"].eq(name)]
        if subset.empty:
            print(f"warning: no forecast rows for station {station_id} ({name})")
        payload_name = resolution.get(name)
        if payload_name is None:
            print(f"warning: no resolved regtemp name for station {station_id}")
        station_documents.append(
            (
                station_id,
                {
                    "schema_version": SCHEMA_VERSION,
                    "generated_at": stamp,
                    "station": meta,
                    "issue_date": issue_date,
                    "issue_time": issue_time_text,
                    "models": models,
                    "forecast": forecast_cases(subset, models, member_counts),
                    "observed": observed_series(regtemp_frame, payload_name),
                },
            )
        )

    latest_document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": stamp,
        "issue_date": issue_date,
        "issue_time": issue_time_text,
        "models": models,
        "stations": stations_meta,
    }
    about_document = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": stamp,
        "dataset_url": DATASET_URL,
        "region": {
            "id": str(region.get("id", "")),
            "name": str(region.get("name", "")),
            "timezone": str(region.get("timezone", "")),
        },
        "sources": ABOUT_SOURCES,
        "status": {
            "forecasts": (
                "raw ensemble members: not bias-corrected, not calibrated, "
                "not quality-controlled beyond the source quality flag"
            ),
            "verification": (
                "no verification results (CRPS, CRPSS, Brier, reliability, "
                "coverage, leaderboard) are published before the 15-issue-date "
                "gate in docs/EVALUATION_PROTOCOL.md"
            ),
            "observations": (
                "SMN regtemp snapshot archived as served; gaps stay null and "
                "are never filled; the 2026-11-14 product precedence rule "
                "applies (regtemp primary)"
            ),
            "smn_snapshot_date": regtemp_date,
        },
    }

    out = Path(out_dir)
    written = [
        _write_json(out / "latest.json", latest_document),
        _write_json(out / "about.json", about_document),
    ]
    for station_id, document in station_documents:
        written.append(_write_json(out / "stations" / f"{station_id}.json", document))
    return written


def main(
    argv: list[str] | None = None,
    *,
    list_files: Callable[[], list[str]] | None = None,
    download: Callable[[str, str], Path] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="repository root (default: detected from configs/sources.yaml)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output directory (default: <root>/data)",
    )
    args = parser.parse_args(argv)
    root = args.root if args.root is not None else find_repo_root()
    out_dir = args.out_dir if args.out_dir is not None else Path(root) / "data"
    written = export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
    )
    print(f"wrote {len(written)} file(s) under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
