"""Hindcast skill document shared by the FastAPI /skill route and the site export.

Honesty rules (docs/EVALUATION_PROTOCOL.md, ROADMAP.md Phase 2):

- Only hindcast-labelled calibration scores are exposed. Operational archive
  leaderboard numbers stay unpublished until the 15-issue-date gate.
- Every document carries ``label``, provider and ``retrieved_at`` from the
  run metadata; synthetic unit runs are never preferred over real ones.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..verify.run import GATE_ISSUE_DATES

HINDCAST_DIR_REL = Path("results") / "hindcast"
SCHEMA_VERSION = "1.0"
ROUND_DIGITS = 4


def _rounded(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return round(number, ROUND_DIGITS)


def latest_hindcast_result(root: Path) -> dict[str, Any] | None:
    """Newest real hindcast CRPSS triplet under results/hindcast/.

    Prefers non-synthetic runs (smoke/full) over ``--synthetic`` unit paths;
    falls back to synthetic only when nothing real exists.
    """
    directory = root / HINDCAST_DIR_REL
    if not directory.is_dir():
        return None
    metas = sorted(directory.glob("crpss_*.meta.json"), key=lambda p: p.stat().st_mtime)
    real = [p for p in metas if "synthetic" not in p.name]
    candidates = real or metas
    if not candidates:
        return None
    meta_path = candidates[-1]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    stem = meta_path.name[: -len(".meta.json")]
    csv_path = directory / f"{stem}.csv"
    md_path = directory / f"{stem}.md"
    cells = pd.read_csv(csv_path).to_dict(orient="records") if csv_path.is_file() else []
    # numpy / pandas scalars → plain JSON types
    clean_cells: list[dict[str, Any]] = []
    for cell in cells:
        clean: dict[str, Any] = {}
        for key, value in cell.items():
            if value is None or (isinstance(value, float) and not np.isfinite(value)):
                clean[key] = None
            elif isinstance(value, (np.floating,)):
                clean[key] = float(value)
            elif isinstance(value, (np.integer,)):
                clean[key] = int(value)
            elif isinstance(value, np.bool_):
                clean[key] = bool(value)
            elif pd.isna(value):
                clean[key] = None
            else:
                clean[key] = value
        clean_cells.append(clean)
    return {
        "meta": meta,
        "cells": clean_cells,
        "report": md_path.read_text(encoding="utf-8") if md_path.is_file() else None,
        "files": {"csv": csv_path.name, "meta": meta_path.name, "md": md_path.name},
    }


def gate_status(root: Path) -> dict[str, Any]:
    """Operational gate state — always reported, never bypassed."""
    archive = root / "data" / "raw" / "_manifest.json"
    issue_dates = 0
    if archive.is_file():
        try:
            manifest = json.loads(archive.read_text(encoding="utf-8"))
            if isinstance(manifest, list):
                issue_dates = len(manifest)
            elif isinstance(manifest, dict):
                dates = manifest.get("issue_dates")
                if isinstance(dates, list):
                    issue_dates = len(dates)
                elif isinstance(dates, dict):
                    issue_dates = len(dates)
                else:
                    # manifest keys may be issue dates themselves
                    issue_dates = sum(
                        1
                        for key in manifest
                        if isinstance(key, str) and len(key) == 10 and key[4] == "-"
                    )
        except (json.JSONDecodeError, TypeError, AttributeError):
            issue_dates = 0

    if issue_dates == 0:
        status_file = root / "results" / "ingest_status.json"
        if status_file.is_file():
            try:
                status_doc = json.loads(status_file.read_text(encoding="utf-8"))
                watchdog = status_doc.get("archive_watchdog", {})
                dates_count = watchdog.get("archived_issue_dates")
                if isinstance(dates_count, int) and dates_count > 0:
                    issue_dates = dates_count
            except Exception:
                pass

    return {
        "required_issue_dates": GATE_ISSUE_DATES,
        "archived_issue_dates": issue_dates,
        "open": issue_dates >= GATE_ISSUE_DATES,
        "operational_leaderboard_published": False,
        "note": (
            "Operational verification numbers are not published before "
            f"{GATE_ISSUE_DATES} distinct archived issue dates. Skill shown "
            "here is hindcast-labelled only."
        ),
    }


def build_skill_document(root: Path) -> dict[str, Any]:
    """Full /skill payload; also written as data/skill.json for the static app."""
    result = latest_hindcast_result(root)
    gate = gate_status(root)
    if result is None:
        fallback = root / "data" / "skill.json"
        if fallback.is_file():
            try:
                doc = json.loads(fallback.read_text(encoding="utf-8"))
                if doc.get("available"):
                    doc["gate"] = gate
                    return doc
            except Exception:
                pass
        return {
            "schema_version": SCHEMA_VERSION,
            "label": "hindcast",
            "available": False,
            "gate": gate,
            "message": "no hindcast calibration run found under results/hindcast/",
        }
    meta = result["meta"]
    cells = result["cells"]
    sufficient = [c for c in cells if not c.get("insufficient")]

    def _mean(key: str) -> float | None:
        values = [c.get(key) for c in sufficient if c.get(key) is not None]
        if not values:
            return None
        return _rounded(float(np.mean([float(v) for v in values])))

    return {
        "schema_version": SCHEMA_VERSION,
        "label": meta.get("label", "hindcast"),
        "available": True,
        "provider": meta.get("provider"),
        "retrieved_at": meta.get("retrieved_at"),
        "mode": meta.get("mode"),
        "window": {"start": meta.get("window_start"), "end": meta.get("window_end")},
        "leads": meta.get("leads"),
        "n_cells": len(cells),
        "n_sufficient": len(sufficient),
        "mean_crpss_emos_vs_raw": _mean("crpss_emos_vs_raw"),
        "mean_crpss_qm_vs_raw": _mean("crpss_qm_vs_raw"),
        "cells": cells,
        "report": result["report"],
        "files": result["files"],
        "gate": gate,
        "note": (
            "Hindcast calibration scores (label hindcast, provider and "
            "retrieved_at above). Not operational-archive leaderboard "
            "numbers; never mixed with the Phase 1 series."
        ),
    }
