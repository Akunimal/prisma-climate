"""Visibility-only gap report for the SMN observation archive.

Lists the local-calendar dates present under ``observations/smn/datohorario/``
and ``observations/smn/observaciones/`` on the Hugging Face dataset (the
archive of record) plus the dates this run staged on local disk, then fails
when any day between the first archived date and the latest completed local day
is missing.

Limits, by construction:

- it never repairs anything: the SMN endpoints ignore ``fecha``, so a missed
  day cannot be backfilled — the only honest response is a visible red run;
- it only speaks when a run actually starts: a schedule GitHub never fires
  produces no report at all;
- days before the archive's first capture are out of scope, because the first
  archived date is the start of the checked interval.

    uv run --project backend --with huggingface_hub \\
        python scripts/check_observation_gaps.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

PREFIX = "observations/smn"
GAP_DATOS = ("datohorario", "observaciones")
# SMN is Argentina: the archive's day keys are Argentina local calendar days.
LOCAL_TZ = ZoneInfo("America/Argentina/Buenos_Aires")

_DATE_DIR_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})$")


def latest_completed_local_day(now: datetime) -> date:
    """Yesterday in Argentina: today's local day is still in progress."""
    return now.astimezone(LOCAL_TZ).date() - timedelta(days=1)


def dates_from_tree_paths(dato: str, paths: list[str]) -> set[date]:
    """Capture dates parsed from HF tree paths under one payload prefix."""
    prefix = f"{PREFIX}/{dato}/"
    dates: set[date] = set()
    for path in paths:
        if not path.startswith(prefix):
            continue
        candidate = path[len(prefix) :].split("/", maxsplit=1)[0]
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


def main(argv: list[str] | None = None) -> int:
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
    args = parser.parse_args(argv)

    repo = os.environ.get("HF_DATASET_REPO")
    if not repo:
        print("HF_DATASET_REPO not configured; cannot list the archive", file=sys.stderr)
        return 2

    from huggingface_hub import HfApi  # imported late: only needed for the listing

    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token) if token else HfApi()

    if args.now is not None:
        now = datetime.strptime(args.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    else:
        now = datetime.now(UTC)
    last = latest_completed_local_day(now)
    print(f"latest completed local day: {last.isoformat()} ({LOCAL_TZ.key})")

    failures = 0
    for dato in GAP_DATOS:
        try:
            entries = api.list_repo_tree(
                repo_id=repo,
                path_in_repo=f"{PREFIX}/{dato}",
                repo_type="dataset",
            )
        except Exception as exc:  # noqa: BLE001 - a listing error must be visible, not silent
            print(f"{dato}: cannot list the archive: {exc}", file=sys.stderr)
            failures += 1
            continue
        archived = dates_from_tree_paths(dato, [entry.path for entry in entries])
        staged = dates_on_disk(args.out, dato)
        archived_text = ", ".join(d.isoformat() for d in sorted(archived)) or "none"
        staged_text = ", ".join(d.isoformat() for d in sorted(staged)) or "none"
        print(f"{dato}: archived on HF: {archived_text} | staged this run: {staged_text}")

        if not archived:
            print(f"{dato}: no archived day yet; nothing to compare")
            continue
        missing = missing_days(archived, last)
        if missing:
            print(
                f"{dato}: MISSING "
                + ", ".join(d.isoformat() for d in missing)
                + f" (first archived {min(archived).isoformat()} .. latest completed "
                f"{last.isoformat()})",
                file=sys.stderr,
            )
            failures += 1
        else:
            print(
                f"{dato}: no missing day between {min(archived).isoformat()} "
                f"and {last.isoformat()}"
            )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
