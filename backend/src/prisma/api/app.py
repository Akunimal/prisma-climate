"""FastAPI service for the Phase 2 app: /forecast, /skill, /sources, /enso.

Honesty gates (docs/EVALUATION_PROTOCOL.md, ROADMAP.md):

- ``/skill`` serves only hindcast-labelled calibration scores. Operational
  archive leaderboard numbers stay unpublished until the 15-issue-date gate;
  the response always carries ``label: "hindcast"`` and the gate status.
- ``/forecast`` serves descriptive statistics of the raw ensemble (percentiles
  of usable members) — never a single deterministic value, never pooled
  across models.
- Sources come from ``configs/sources.yaml``; licences and attribution
  strings are reproduced verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from ..calibrate.skill_doc import build_skill_document
from ..ingest.base import find_repo_root, load_all_regions
from ..ingest.base import load_region as _load_region_file
from ..verify.leaderboard_doc import build_leaderboard_document
from ..verify.run import MEMBER_FRACTION

SCHEMA_VERSION = "1.0"
FORECAST_REL = Path("data") / "raw" / "openmeteo-ensemble.parquet"
ONI_REL = Path("data") / "raw" / "noaa-oni.parquet"
SOURCES_REL = Path("configs") / "sources.yaml"
REGION_REL = Path("configs") / "regions" / "argentina.yaml"
QUANTILES = (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))
ROUND_DIGITS = 2


def _rounded(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not np.isfinite(number):
        return None
    return round(number, ROUND_DIGITS)


def _iso_utc(stamp: Any) -> str:
    ts = pd.Timestamp(stamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def load_forecast_frame(root: Path) -> pd.DataFrame:
    path = root / FORECAST_REL
    if not path.is_file():
        raise HTTPException(status_code=503, detail=f"forecast archive missing: {path.name}")
    return pd.read_parquet(path)


def latest_issue(frame: pd.DataFrame) -> tuple[str, pd.Timestamp]:
    if frame.empty or "issue_time" not in frame.columns:
        raise HTTPException(status_code=503, detail="forecast archive has no issue_time")
    issue = frame["issue_time"].max()
    if pd.isna(issue):
        raise HTTPException(status_code=503, detail="forecast archive has no issue_time")
    return pd.Timestamp(issue).strftime("%Y-%m-%d"), pd.Timestamp(issue)


def member_share_ok(present: int, nominal: int) -> bool:
    return present * MEMBER_FRACTION[1] >= nominal * MEMBER_FRACTION[0]


def forecast_cases(
    station_frame: pd.DataFrame,
    models: list[str],
    member_counts: dict[str, int],
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Per variable/model quantile cases for one station (raw ensemble only)."""
    variables = sorted(station_frame["variable"].dropna().unique())
    work = station_frame.loc[
        station_frame["variable"].isin(variables) & station_frame["model"].isin(models)
    ].copy()
    work["time"] = pd.to_datetime(work["time"])
    out: dict[str, dict[str, list[dict[str, Any]]]] = {
        str(v): {m: [] for m in models} for v in variables
    }
    if work.empty:
        return out
    for (variable, model, lead_day), group in work.groupby(
        ["variable", "model", "lead_day"], sort=True
    ):
        dates = sorted(pd.Timestamp(value) for value in group["time"].unique())
        if len(dates) != 1:
            continue
        nominal = member_counts.get(str(model), 0)
        usable = group.loc[group["value"].notna() & group["quality_flag"].eq("ok")]
        n_present = int(usable["value"].size)
        case: dict[str, Any] = {
            "lead_day": int(lead_day),
            "valid_local_date": dates[0].date().isoformat(),
            "n_members": n_present,
            "nominal_members": int(nominal),
        }
        if nominal and member_share_ok(n_present, nominal):
            values = usable["value"].to_numpy(dtype=float)
            case["status"] = "ok"
            for name, q in QUANTILES:
                case[name] = _rounded(np.percentile(values, q))
            case["min"] = _rounded(values.min())
            case["max"] = _rounded(values.max())
            if str(variable) == "precip":
                case["fraction_ge_1mm"] = round(float((values >= 1.0).mean()), ROUND_DIGITS)
                case["fraction_ge_10mm"] = round(float((values >= 10.0).mean()), ROUND_DIGITS)
        else:
            case["status"] = "missing_members"
            for name, _ in QUANTILES:
                case[name] = None
            case["min"] = None
            case["max"] = None
            if str(variable) == "precip":
                case["fraction_ge_1mm"] = None
                case["fraction_ge_10mm"] = None
        out[str(variable)][str(model)].append(case)
    return out


def load_member_counts(root: Path) -> dict[str, int]:
    path = root / SOURCES_REL
    registry = yaml.safe_load(path.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for source in registry.get("sources", []):
        options = source.get("options") or {}
        for model, n in (options.get("member_counts") or {}).items():
            counts[str(model)] = int(n)
    return counts


def load_region(root: Path) -> dict[str, Any]:
    return yaml.safe_load((root / REGION_REL).read_text(encoding="utf-8"))


def oni_state(value: float) -> str:
    if value >= 0.5:
        return "el_nino"
    if value <= -0.5:
        return "la_nina"
    return "neutral"


def create_app(root: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="PRISMA climate API",
        version=SCHEMA_VERSION,
        description=(
            "Probabilistic ensemble forecast statistics, hindcast calibration "
            "skill, source registry and ENSO state."
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    repo_root = root or find_repo_root()

    @app.get("/forecast")
    def forecast(
        station_id: str | None = Query(None, description="station id from the region file"),
        region: str | None = Query(
            None, description="region id (e.g. argentina, middle_east, global); default: argentina"
        ),
    ) -> dict[str, Any]:
        frame = load_forecast_frame(repo_root)
        issue_date, issue_time = latest_issue(frame)
        latest = frame.loc[frame["issue_time"].eq(frame["issue_time"].max())]

        if region is None or region.lower() == "argentina":
            region_config = load_region(repo_root)
        elif region.lower() in ("global", "all"):
            region_config = load_all_regions(repo_root)
        else:
            norm_reg = region.lower().replace("-", "_")
            candidate = repo_root / "configs" / "regions" / f"{norm_reg}.yaml"
            if not candidate.is_file():
                raise HTTPException(status_code=404, detail=f"unknown region {region}")
            region_config = _load_region_file(candidate)

        stations = region_config.get("stations", [])
        member_counts = load_member_counts(repo_root)
        models = sorted(str(m) for m in latest["model"].dropna().unique())

        def station_payload(station: dict[str, Any]) -> dict[str, Any]:
            sid = str(station["id"])
            sub = latest.loc[latest["location"].astype(str).eq(str(station["name"]))]
            st_res: dict[str, Any] = {
                "id": sid,
                "name": station["name"],
                "lat": station["lat"],
                "lon": station["lon"],
                "forecast": forecast_cases(sub, models, member_counts),
            }
            if "region" in station:
                st_res["region"] = station["region"]
            return st_res

        if station_id is not None:
            match = [s for s in stations if str(s["id"]) == station_id]
            if not match:
                raise HTTPException(status_code=404, detail=f"unknown station {station_id}")
            payload_stations = [station_payload(match[0])]
        else:
            payload_stations = [station_payload(s) for s in stations]

        out: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "issue_date": issue_date,
            "issue_time": _iso_utc(issue_time),
            "models": models,
            "calibrated": False,
            "note": "raw ensemble member statistics; models are never pooled",
            "stations": payload_stations,
        }
        if region is not None:
            out["region"] = str(region_config.get("id", region))
        return out

    @app.get("/leaderboard")
    def leaderboard() -> dict[str, Any]:
        return build_leaderboard_document(repo_root)

    @app.get("/skill")
    def skill() -> dict[str, Any]:
        return build_skill_document(repo_root)

    @app.get("/sources")
    def sources() -> dict[str, Any]:
        path = repo_root / SOURCES_REL
        if not path.is_file():
            raise HTTPException(status_code=503, detail="configs/sources.yaml missing")
        registry = yaml.safe_load(path.read_text(encoding="utf-8"))
        rows = []
        for source in registry.get("sources", []):
            rows.append(
                {
                    "id": source.get("id"),
                    "name": source.get("name"),
                    "tier": source.get("tier"),
                    "status": source.get("status"),
                    "variables": source.get("variables"),
                    "day_convention": source.get("day_convention"),
                    "license": source.get("license"),
                    "redistributable": source.get("redistributable"),
                    "coverage": source.get("coverage"),
                    "update_frequency": source.get("update_frequency"),
                    "verified_on": source.get("verified_on"),
                    "notes": source.get("notes"),
                }
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "registry_version": registry.get("version"),
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sources": rows,
        }

    @app.get("/enso")
    def enso() -> dict[str, Any]:
        path = repo_root / ONI_REL
        if not path.is_file():
            raise HTTPException(status_code=503, detail="ONI archive missing")
        frame = pd.read_parquet(path)
        frame = frame.loc[frame["variable"].eq("oni")].copy()
        if frame.empty:
            raise HTTPException(status_code=503, detail="no ONI rows in archive")
        frame["time"] = pd.to_datetime(frame["time"])
        frame = frame.sort_values("time")
        series = [
            {"time": row.time.date().isoformat(), "oni": _rounded(row.value)}
            for row in frame.itertuples(index=False)
        ]
        latest_row = frame.iloc[-1]
        value = float(latest_row["value"])
        return {
            "schema_version": SCHEMA_VERSION,
            "index": "oni",
            "provider": "NOAA CPC",
            "unit": "degC",
            "latest": {
                "time": latest_row["time"].date().isoformat(),
                "oni": _rounded(value),
                "state": oni_state(value),
            },
            "thresholds": {"el_nino": ">= +0.5", "la_nina": "<= -0.5", "neutral": "in between"},
            "series": series,
            "note": "Niño 3.4 seasonal ONI; slow signal for conditioning, not a forecast",
        }

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
