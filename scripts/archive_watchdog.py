"""Record archive coverage gaps against the UTC calendar (visibility only).

Compares UTC calendar days from the archive start through "as of" (default:
today UTC) with the issue dates present in the public Hugging Face archive
(``forecasts/<issue_date>/``). Missing days are written to
``results/ingest_status.json`` under ``archive_watchdog`` so a dropped
scheduled day is visible in the repository heartbeat.

This is **visibility only**: it never fetches, repairs or uploads anything,
and a missing day does not fail the workflow. The check reads the archive
through a Hugging Face repository listing, which can be cache-prone: a
reported missing day may be a false positive — verify against the dataset
before acting.

    uv run --project backend --with huggingface_hub \
        python scripts/archive_watchdog.py

Requires huggingface_hub (installed with ``--with huggingface_hub`` in the
workflow). The Hugging Face token, when present, is read from the environment
by the hub client and never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_STATUS = REPO / "results" / "ingest_status.json"
DEFAULT_SINCE = date(2026, 11, 11)  # first archived issue date
FORECAST_PATH = re.compile(r"^forecasts/(\d{4}-\d{2}-\d{2})/")


def issue_dates_from_repo_files(files: list[str]) -> set[str]:
    """Issue dates present under forecasts/<issue_date>/ in the HF repo."""
    dates: set[str] = set()
    for name in files:
        match = FORECAST_PATH.match(name)
        if not match:
            continue
        raw = match.group(1)
        try:
            date.fromisoformat(raw)
        except ValueError:
            continue
        dates.add(raw)
    return dates


def missing_days(archived: set[str], since: date, as_of: date) -> list[str]:
    """Every UTC calendar day in [since, as_of] with no archived issue date."""
    if as_of < since:
        raise ValueError(f"as_of {as_of} is before since {since}")
    missing: list[str] = []
    day = since
    while day <= as_of:
        iso = day.isoformat()
        if iso not in archived:
            missing.append(iso)
        day += timedelta(days=1)
    return missing


def merge_status(
    status_path: Path,
    *,
    missing: list[str],
    archived: set[str],
    since: date,
    as_of: date,
    checked_at: datetime,
) -> dict:
    """Add the watchdog block to the ingest status, preserving every other key."""
    if not status_path.is_file():
        raise FileNotFoundError(f"status file not found: {status_path}")
    payload = json.loads(status_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{status_path}: expected a JSON object")
    payload["archive_watchdog"] = {
        "checked_at": checked_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "since": since.isoformat(),
        "as_of": as_of.isoformat(),
        "archived_issue_dates": len(archived),
        "missing_issue_dates": missing,
        "note": (
            "visibility only; no repair is performed by this check; "
            "the HF listing can be cache-prone, so a missing day may be "
            "a false positive — verify against the dataset before acting"
        ),
    }
    return payload


def list_forecast_files(repo_id: str) -> list[str]:
    """File paths in the public HF dataset (lazy import: needs huggingface_hub)."""
    from huggingface_hub import list_repo_files

    return list(list_repo_files(repo_id=repo_id, repo_type="dataset"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", type=Path, default=DEFAULT_STATUS)
    parser.add_argument(
        "--since",
        type=date.fromisoformat,
        default=DEFAULT_SINCE,
        help="first UTC calendar day to check (default 2026-11-11)",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="last UTC calendar day to check (default: today UTC)",
    )
    parser.add_argument(
        "--hf-repo",
        default=os.environ.get("HF_DATASET_REPO", "Akunimal/prisma-climate"),
        help="Hugging Face dataset repo (default: env HF_DATASET_REPO)",
    )
    args = parser.parse_args(argv)

    as_of = args.as_of or datetime.now(UTC).date()
    try:
        files = list_forecast_files(args.hf_repo)
        archived = issue_dates_from_repo_files(files)
        missing = missing_days(archived, args.since, as_of)
        payload = merge_status(
            args.status,
            missing=missing,
            archived=archived,
            since=args.since,
            as_of=as_of,
            checked_at=datetime.now(UTC),
        )
    except Exception as exc:  # noqa: BLE001 - visibility step; error is reported, not raised
        print(f"archive watchdog failed: {exc}", file=sys.stderr)
        return 1

    args.status.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(
        f"archive watchdog: {len(archived)} issue dates archived, "
        f"{len(missing)} missing in {args.since.isoformat()}..{as_of.isoformat()}"
    )
    if missing:
        print("missing: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
