"""Run a selection of sources and record what happened."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq

from .base import find_repo_root, utc_now
from .registry import build, select_sources


def write_ingest_status(
    manifest: dict[str, Any],
    path: Path | None = None,
) -> Path:
    """Write the small status file that gets committed to the repository.

    It records the last run, rows per source and failures. The scheduled
    workflow commits this file so the repository keeps a visible heartbeat.
    """
    status_path = path or (find_repo_root() / "results" / "ingest_status.json")
    status_path.parent.mkdir(parents=True, exist_ok=True)

    rows: dict[str, int] = {}
    failures: list[dict[str, str]] = []
    for source_id, info in manifest.get("sources", {}).items():
        if info.get("status") == "ok":
            rows[source_id] = int(info.get("rows", 0))
        else:
            failures.append({"source": source_id, "error": info.get("error", "unknown")})

    payload = {
        "last_run": manifest.get("generated_at"),
        "region": manifest.get("region"),
        "rows": rows,
        "failures": failures,
        "status": "ok" if not failures else ("partial" if rows else "failed"),
    }
    status_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return status_path


def run_sources(
    region: dict[str, Any],
    registry: list[dict[str, Any]],
    out_dir: Path,
    *,
    tier: int | None = None,
    ids: list[str] | None = None,
    include_planned: bool = False,
    status_path: Path | None = None,
) -> dict[str, Any]:
    selected = select_sources(registry, tier=tier, ids=ids, include_planned=include_planned)
    if not selected:
        raise ValueError("no sources selected")

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, Any] = {
        "region": region["id"],
        "generated_at": utc_now().isoformat(),
        "sources": {},
    }

    for entry in selected:
        connector = build(entry)
        try:
            path = connector.run(
                region,
                out_dir,
                day_convention=entry.get("day_convention"),
                **entry.get("options", {}),
            )
        except Exception as exc:  # noqa: BLE001 - recorded in the manifest, not swallowed
            manifest["sources"][entry["id"]] = {"status": "error", "error": str(exc)}
            print(f"{entry['id']:<22} FAILED  {exc}")
            continue

        rows = pq.ParquetFile(path).metadata.num_rows
        manifest["sources"][entry["id"]] = {
            "status": "ok",
            "rows": rows,
            "file": path.name,
            "tier": entry.get("tier"),
        }
        print(f"{entry['id']:<22} {rows:>9} rows  {path.name}")

    (out_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_ingest_status(manifest, status_path)
    return manifest
