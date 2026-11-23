"""Visibility-only gap report for SMN and global METAR observation archives.

Lists the dates present under:
1. ``observations/smn/datohorario/`` and ``observations/smn/observaciones/``
   (local-calendar dates, Argentina timezone) on Hugging Face and local staging.
2. ``observations/metar/<region>/`` (UTC dates) for all active non-Argentina
   regions discovered dynamically from ``configs/sources.yaml``.

Limits, by construction:
- it never repairs anything: missed observation days cannot be backfilled;
  the only honest response is a visible report;
- it only speaks when a run actually starts;
- days before the archive's first capture are out of scope.

Usage::

    uv run --project backend --with huggingface_hub \\
        python scripts/check_observation_gaps.py
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

SMN_PREFIX = "observations/smn"
GAP_DATOS = ("datohorario", "observaciones")
# SMN is Argentina: the archive's day keys are Argentina local calendar days.
LOCAL_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

METAR_PREFIX = "observations/metar"

_DATE_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def latest_completed_local_day(now: datetime) -> date:
    """Yesterday in Argentina: today's local day is still in progress."""
    return now.astimezone(LOCAL_TZ).date() - timedelta(days=1)


def latest_completed_utc_day(now: datetime) -> date:
    """Yesterday in UTC: today's UTC day is still in progress."""
    return now.astimezone(UTC).date() - timedelta(days=1)


def dates_from_tree_paths(dato: str, paths: list[str]) -> set[date]:
    """Capture dates parsed from HF tree paths under one SMN payload prefix."""
    prefix = f"{SMN_PREFIX}/{dato}/"
    dates: set[date] = set()
    for path in paths:
        normalized = str(path).replace("\\", "/")
        if not normalized.startswith(prefix):
            continue
        candidate = normalized[len(prefix) :].split("/", maxsplit=1)[0]
        match = _DATE_DIR_RE.match(candidate)
        if match:
            dates.add(date.fromisoformat(match.group(1)))
    return dates


def dates_on_disk(out_root: Path, dato: str) -> set[date]:
    """Dates staged on local disk under ``<out_root>/<dato>/<date>/``."""
    root = out_root / dato
    if not root.is_dir():
        return set()
    dates: set[date] = set()
    for entry in root.iterdir():
        if entry.is_dir() and _DATE_DIR_RE.match(entry.name):
            dates.add(date.fromisoformat(entry.name))
    return dates


def missing_days(archived: set[date], last: date) -> list[date]:
    """Days between the first archived date and ``last`` (inclusive) that are absent."""
    if not archived:
        return []
    first = min(archived)
    expected = {first + timedelta(days=i) for i in range((last - first).days + 1)}
    return sorted(expected - archived)


def load_active_metar_regions(sources_yaml_path: Path) -> list[str]:
    """Return active non-Argentina METAR region names from configs/sources.yaml."""
    if not sources_yaml_path.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(sources_yaml_path.read_text(encoding="utf-8")) or {}
        regions: list[str] = []
        for s in data.get("sources", []):
            s_id = str(s.get("id", ""))
            status = s.get("status")
            if s_id.startswith("metar-") and s_id != "metar-global" and status == "active":
                region_name = s_id.removeprefix("metar-").replace("-", "_")
                regions.append(region_name)
        return sorted(regions)
    except (OSError, yaml.YAMLError):
        return []


def dates_from_metar_tree_paths(region: str, paths: list[str]) -> set[date]:
    """Extract dates for a region from HF tree paths under observations/metar/."""
    dates: set[date] = set()
    prefix_reg = f"{METAR_PREFIX}/{region}/"
    prefix_global = f"{METAR_PREFIX}/"

    for raw in paths:
        path = str(raw).replace("\\", "/")
        # Format 1: observations/metar/<region>/<YYYY-MM-DD>/... or <YYYY-MM-DD>.parquet
        if path.startswith(prefix_reg):
            sub = path[len(prefix_reg) :]
            first_seg = sub.split("/", maxsplit=1)[0]
            match = _DATE_DIR_RE.match(first_seg)
            if match:
                dates.add(date.fromisoformat(match.group(1)))
                continue
            if sub.endswith(".parquet"):
                stem = sub[:-8]
                match = _DATE_DIR_RE.match(stem.split("/", maxsplit=1)[0])
                if match:
                    dates.add(date.fromisoformat(match.group(1)))
                    continue
        # Format 2: observations/metar/<YYYY-MM-DD>.parquet (shared global archive)
        elif path.startswith(prefix_global) and path.endswith(".parquet"):
            stem = path[len(prefix_global) : -8]
            match = _DATE_DIR_RE.match(stem)
            if match:
                dates.add(date.fromisoformat(match.group(1)))

    return dates


def dates_on_disk_metar(out_root: Path, region: str) -> set[date]:
    """Dates staged on disk under <out_root>/metar/<region>/<date> or <date>.parquet."""
    dates: set[date] = set()
    metar_root = out_root / "metar"
    if not metar_root.is_dir():
        return dates

    # Check <out_root>/metar/<region>/
    reg_dir = metar_root / region
    if reg_dir.is_dir():
        for entry in reg_dir.iterdir():
            if entry.is_dir() and _DATE_DIR_RE.match(entry.name):
                dates.add(date.fromisoformat(entry.name))
            elif (
                entry.is_file()
                and entry.suffix == ".parquet"
                and _DATE_DIR_RE.match(entry.stem)
            ):
                dates.add(date.fromisoformat(entry.stem))

    # Check <out_root>/metar/<YYYY-MM-DD>.parquet
    for entry in metar_root.iterdir():
        if entry.is_file() and entry.suffix == ".parquet" and _DATE_DIR_RE.match(entry.stem):
            dates.add(date.fromisoformat(entry.stem))

    return dates


def audit_metar_observations(
    paths: list[str],
    active_regions: list[str],
    last_day: date,
    staged_root: Path | None = None,
) -> dict[str, Any]:
    """Audit METAR archive continuity across active regions."""
    region_audits: dict[str, Any] = {}
    total_gaps = 0

    for reg in active_regions:
        archived = dates_from_metar_tree_paths(reg, paths)
        if staged_root:
            archived |= dates_on_disk_metar(staged_root, reg)

        missing = missing_days(archived, last_day) if archived else []
        total_gaps += len(missing)

        status_str = "empty" if not archived else ("gap" if missing else "ok")
        region_audits[reg] = {
            "status": status_str,
            "archived_dates_count": len(archived),
            "first_archived": min(archived).isoformat() if archived else None,
            "latest_archived": max(archived).isoformat() if archived else None,
            "missing_dates": [d.isoformat() for d in missing],
        }

    has_data = sum(1 for r in region_audits.values() if r["archived_dates_count"] > 0)
    overall_status = "ok" if total_gaps == 0 else "gaps_detected"

    return {
        "as_of": last_day.isoformat(),
        "total_active_regions": len(active_regions),
        "regions_with_data": has_data,
        "total_gaps": total_gaps,
        "status": overall_status,
        "regions": region_audits,
    }


def update_ingest_status(
    status_file: Path,
    metar_audit: dict[str, Any],
    stamp_iso: str | None = None,
) -> None:
    """Additively update results/ingest_status.json with the METAR watchdog block."""
    data: dict[str, Any] = {}
    if status_file.is_file():
        try:
            data = json.loads(status_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}

    checked_at = (
        stamp_iso
        if stamp_iso is not None
        else datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    data["metar_watchdog"] = {
        "checked_at": checked_at,
        "as_of": metar_audit.get("as_of"),
        "total_active_regions": metar_audit.get("total_active_regions"),
        "regions_with_data": metar_audit.get("regions_with_data"),
        "total_gaps": metar_audit.get("total_gaps"),
        "status": metar_audit.get("status"),
        "regions": metar_audit.get("regions"),
        "note": (
            "visibility only; audits daily METAR observation continuity across active global regions"
        ),
    }

    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(
        json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def main(
    argv: list[str] | None = None,
    *,
    list_tree: Callable[[str, str], list[str]] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/observations"),
        help="local staging root written by the capture steps of this run",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="UTC instant to evaluate (default: now; for tests)",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        default=Path("configs/sources.yaml"),
        help="path to configs/sources.yaml",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help="optional path to results/ingest_status.json to update with metar watchdog",
    )
    parser.add_argument(
        "--skip-smn",
        action="store_true",
        help="skip SMN observation check",
    )
    parser.add_argument(
        "--skip-metar",
        action="store_true",
        help="skip METAR observation check",
    )
    args = parser.parse_args(argv)

    if args.now is not None:
        now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    else:
        now = datetime.now(UTC)

    repo = os.environ.get("HF_DATASET_REPO")
    if not repo and list_tree is None:
        print("HF_DATASET_REPO not configured; cannot list the archive", file=sys.stderr)
        return 2

    # Fetch listing function
    if list_tree is not None:
        fetch_paths = list_tree
    else:
        from huggingface_hub import HfApi

        token = os.environ.get("HF_TOKEN")
        api = HfApi(token=token) if token else HfApi()

        def _hf_list(repo_id: str, path_in_repo: str) -> list[str]:
            entries = api.list_repo_tree(
                repo_id=repo_id,
                path_in_repo=path_in_repo,
                repo_type="dataset",
            )
            return [entry.path for entry in entries]

        fetch_paths = _hf_list

    failures = 0

    # 1. SMN Observation Check
    if not args.skip_smn:
        last_smn = latest_completed_local_day(now)
        print(f"SMN latest completed local day: {last_smn.isoformat()} ({LOCAL_TZ.key})")
        for dato in GAP_DATOS:
            try:
                paths = fetch_paths(repo, f"{SMN_PREFIX}/{dato}")
            except Exception as exc:  # noqa: BLE001
                print(f"{dato}: cannot list the archive: {exc}", file=sys.stderr)
                failures += 1
                continue
            archived = dates_from_tree_paths(dato, paths)
            staged = dates_on_disk(args.out, dato)
            archived_text = ", ".join(d.isoformat() for d in sorted(archived)) or "none"
            staged_text = ", ".join(d.isoformat() for d in sorted(staged)) or "none"
            print(f"{dato}: archived on HF: {archived_text} | staged this run: {staged_text}")

            if not archived:
                print(f"{dato}: no archived day yet; nothing to compare")
                continue
            missing = missing_days(archived, last_smn)
            if missing:
                print(
                    f"{dato}: MISSING "
                    + ", ".join(d.isoformat() for d in missing)
                    + f" (first archived {min(archived).isoformat()} .. latest completed "
                    f"{last_smn.isoformat()})",
                    file=sys.stderr,
                )
                failures += 1
            else:
                print(
                    f"{dato}: no missing day between {min(archived).isoformat()} "
                    f"and {last_smn.isoformat()}"
                )

    # 2. METAR Global Observation Check
    if not args.skip_metar:
        last_utc = latest_completed_utc_day(now)
        active_regions = load_active_metar_regions(args.sources)
        print(
            f"METAR latest completed UTC day: {last_utc.isoformat()} (UTC); "
            f"{len(active_regions)} active non-Argentina region(s): "
            + ", ".join(active_regions)
        )
        try:
            metar_paths = fetch_paths(repo, METAR_PREFIX)
        except Exception as exc:  # noqa: BLE001
            print(f"metar: cannot list archive at {METAR_PREFIX}: {exc}", file=sys.stderr)
            metar_paths = []
            failures += 1

        metar_audit = audit_metar_observations(
            metar_paths,
            active_regions,
            last_utc,
            staged_root=args.out,
        )

        for reg, reg_res in metar_audit["regions"].items():
            status = reg_res["status"]
            count = reg_res["archived_dates_count"]
            missing = reg_res["missing_dates"]
            if status == "empty":
                print(f"metar [{reg}]: no archived dates yet (collecting)")
            elif status == "gap":
                print(
                    f"metar [{reg}]: MISSING {', '.join(missing)} "
                    f"({count} archived: {reg_res['first_archived']} .. {reg_res['latest_archived']})",
                    file=sys.stderr,
                )
                failures += 1
            else:
                print(
                    f"metar [{reg}]: ok ({count} archived: "
                    f"{reg_res['first_archived']} .. {reg_res['latest_archived']})"
                )

        if args.status_file:
            update_ingest_status(args.status_file, metar_audit)
            print(f"updated ingest status file with metar_watchdog at {args.status_file}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
