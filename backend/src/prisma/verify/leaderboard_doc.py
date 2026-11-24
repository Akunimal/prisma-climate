"""Operational leaderboard document shared by site export and API consumers.

Strict adherence to docs/EVALUATION_PROTOCOL.md and ROADMAP.md Phase 1:
- The operational leaderboard (raw ensemble vs climatology vs persistence)
  is gated on accumulating at least 15 distinct archived issue dates.
- When below the gate (status == "locked"), it exposes honest progress metadata
  (archived vs required issue dates, remaining dates) and NEVER emits premature
  rankings or metrics.
- When above the gate and results/verification/leaderboard.csv exists
  (status == "unlocked"), it exposes full structured model comparisons
  normalized to strict JSON (allow_nan=False, zero NaN/Inf literals).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .run import GATE_ISSUE_DATES, MIN_SAMPLE

SCHEMA_VERSION = "1.0"
ROUND_DIGITS = 4
LEADERBOARD_DIR_REL = Path("results") / "verification"
LEADERBOARD_CSV = "leaderboard.csv"
LEADERBOARD_STRATA_CSV = "leaderboard_by_issue_hour_stratum.csv"


def _clean_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(val):
        return None
    return round(val, ROUND_DIGITS)


def resolve_archived_issue_dates(root: Path) -> int:
    """Read verified count of archived issue dates without network calls."""
    issue_dates = 0

    # 1. Manifest
    manifest_path = root / "data" / "raw" / "_manifest.json"
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                issue_dates = len(data)
            elif isinstance(data, dict):
                dates = data.get("issue_dates")
                if isinstance(dates, (list, dict)):
                    issue_dates = len(dates)
                else:
                    issue_dates = sum(
                        1
                        for k in data
                        if isinstance(k, str) and len(k) == 10 and k[4] == "-"
                    )
        except Exception:
            issue_dates = 0

    if issue_dates > 0:
        return issue_dates

    # 2. Watchdog in results/ingest_status.json
    status_path = root / "results" / "ingest_status.json"
    if status_path.is_file():
        try:
            status_data = json.loads(status_path.read_text(encoding="utf-8"))
            watchdog = status_data.get("archive_watchdog", {})
            archived = watchdog.get("archived_issue_dates")
            if archived is not None:
                try:
                    val = int(archived)
                    if val > 0:
                        return val
                except (ValueError, TypeError):
                    pass
        except Exception:
            pass

    # 3. Report in results/verification/leaderboard.md
    md_path = root / LEADERBOARD_DIR_REL / "leaderboard.md"
    if md_path.is_file():
        try:
            content = md_path.read_text(encoding="utf-8")
            match = re.search(r"\((\d+)\s+distinct issue dates archived\)", content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

    # 4. Local forecast directories under forecasts/<YYYY-MM-DD>/
    forecasts_dir = root / "forecasts"
    if forecasts_dir.is_dir():
        try:
            count = sum(
                1
                for p in forecasts_dir.iterdir()
                if p.is_dir() and len(p.name) == 10 and p.name[4] == "-"
            )
            if count > 0:
                return count
        except Exception:
            pass

    return 0


def build_leaderboard_document(
    root: Path,
    *,
    override_issue_dates: int | None = None,
    override_csv_path: Path | None = None,
) -> dict[str, Any]:
    """Construct deterministic operational leaderboard payload.

    Respects strict JSON serialization (RFC 8259, allow_nan=False).
    """
    issue_dates = (
        override_issue_dates
        if override_issue_dates is not None
        else resolve_archived_issue_dates(root)
    )
    is_open = issue_dates >= GATE_ISSUE_DATES
    remaining = max(0, GATE_ISSUE_DATES - issue_dates)

    csv_path = (
        override_csv_path
        if override_csv_path is not None
        else (root / LEADERBOARD_DIR_REL / LEADERBOARD_CSV)
    )

    now_iso = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # If below gate or CSV has not been generated yet
    if not is_open or not csv_path.is_file():
        gate_status_str = "unlocked" if is_open else "locked"
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now_iso,
            "protocol": "docs/EVALUATION_PROTOCOL.md",
            "gate": {
                "status": gate_status_str,
                "required_issue_dates": GATE_ISSUE_DATES,
                "archived_issue_dates": issue_dates,
                "remaining_issue_dates": remaining,
                "open": is_open,
                "operational_leaderboard_published": False,
                "note": (
                    "Operational leaderboard numbers are computed and published only "
                    f"after accumulating at least {GATE_ISSUE_DATES} distinct archived issue dates "
                    "under forecasts/ in accordance with docs/EVALUATION_PROTOCOL.md."
                ),
            },
            "summary": None,
            "models": ["gfs_seamless", "ecmwf_ifs025"],
            "baselines": ["climatology", "persistence"],
            "cells": [],
        }

    # Above gate and CSV present: load and normalize cells
    try:
        df = pd.read_csv(csv_path)
    except Exception as exc:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": now_iso,
            "protocol": "docs/EVALUATION_PROTOCOL.md",
            "gate": {
                "status": "unlocked",
                "required_issue_dates": GATE_ISSUE_DATES,
                "archived_issue_dates": issue_dates,
                "remaining_issue_dates": 0,
                "open": True,
                "operational_leaderboard_published": False,
                "note": (
                    "Operational verification leaderboard withheld: "
                    f"failed to read verification CSV ({exc})."
                ),
            },
            "summary": None,
            "models": ["gfs_seamless", "ecmwf_ifs025"],
            "baselines": ["climatology", "persistence"],
            "cells": [],
        }

    clean_cells: list[dict[str, Any]] = []

    for row in df.to_dict(orient="records"):
        clean_row: dict[str, Any] = {
            "location": str(row.get("location", "")),
            "variable": str(row.get("variable", "")),
            "model": str(row.get("model", "")),
            "lead_day": int(row.get("lead_day", 0)),
            "n_pairs": int(row.get("n_pairs", 0)),
            "n_missing": int(row.get("n_missing", 0)),
            "insufficient": bool(row.get("insufficient", False)),
            "n_climatology": (
                int(row.get("n_climatology", 0))
                if pd.notna(row.get("n_climatology"))
                else None
            ),
            "n_persistence": (
                int(row.get("n_persistence", 0))
                if pd.notna(row.get("n_persistence"))
                else None
            ),
            "crps_raw": _clean_float(row.get("crps_raw")),
            "crps_climatology": _clean_float(row.get("crps_climatology")),
            "crps_persistence": _clean_float(row.get("crps_persistence")),
            "crpss_vs_climatology": _clean_float(row.get("crpss_vs_climatology")),
            "crpss_vs_persistence": _clean_float(row.get("crpss_vs_persistence")),
        }
        clean_cells.append(clean_row)

    sufficient_cells = [c for c in clean_cells if not c["insufficient"]]

    def _mean_metric(key: str) -> float | None:
        values = [c[key] for c in sufficient_cells if c[key] is not None]
        if not values:
            return None
        return _clean_float(np.mean(values))

    models_found = sorted(list({c["model"] for c in clean_cells if c["model"]}))
    summary = {
        "n_cells": len(clean_cells),
        "n_sufficient": len(sufficient_cells),
        "min_sample_threshold": MIN_SAMPLE,
        "mean_crpss_vs_climatology": _mean_metric("crpss_vs_climatology"),
        "mean_crpss_vs_persistence": _mean_metric("crpss_vs_persistence"),
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": now_iso,
        "protocol": "docs/EVALUATION_PROTOCOL.md",
        "gate": {
            "status": "unlocked",
            "required_issue_dates": GATE_ISSUE_DATES,
            "archived_issue_dates": issue_dates,
            "remaining_issue_dates": 0,
            "open": True,
            "operational_leaderboard_published": True,
            "note": (
                "Operational verification leaderboard (raw ensemble vs climatology vs "
                f"persistence) computed over {issue_dates} distinct issue dates in accordance "
                "with docs/EVALUATION_PROTOCOL.md."
            ),
        },
        "summary": summary,
        "models": models_found,
        "baselines": ["climatology", "persistence"],
        "cells": clean_cells,
    }
