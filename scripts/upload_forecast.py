"""Upload the daily forecast archive to a public Hugging Face dataset.

Used by .github/workflows/ingest.yml when HF_TOKEN (secret) and
HF_DATASET_REPO (repository variable) are configured. Exits with code 2 when
they are not, so the workflow can fall back to a GitHub Release.

The target path is ``forecasts/<issue_date>/<file>``, where ``issue_date`` is
read from the parquet's ``issue_time`` column and never from the wall clock: a
same-day re-run resolves to the same path instead of minting a second archive
for a cycle that is already stored. An existing target is skipped, because the
first archive of an issue date is canonical and frozen. ``--replace`` exists
only for one-shot corrections and is never set by the workflow.

    HF_TOKEN=... HF_DATASET_REPO=... \
      uv run --project backend --with huggingface_hub \
      python scripts/upload_forecast.py --archive-dir data/archive --issue-date 2026-11-11
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd


def issue_date_from_parquet(path: Path | str) -> str:
    """UTC date of the forecast issue, read from the archive itself.

    ``issue_time`` records when the provider cycle was fetched (UTC). Deriving
    the archive key from it keeps a re-run on the same day from duplicating an
    issue date the15-date gate already counts.
    """
    frame = pd.read_parquet(path)
    if "issue_time" not in frame.columns:
        raise ValueError(f"{path} has no issue_time column; cannot derive the archive date")
    if frame.empty:
        raise ValueError(f"{path} has no rows")
    stamps = pd.to_datetime(frame["issue_time"], utc=True, errors="raise")
    dates = sorted({stamp.strftime("%Y-%m-%d") for stamp in stamps})
    if len(dates) != 1:
        raise ValueError(
            f"{path} carries {len(dates)} issue dates ({', '.join(dates)}); "
            "one archive file must hold exactly one issue date"
        )
    return dates[0]


def plan_uploads(
    files: Iterable[Path],
    issue_date: str,
    exists: Callable[[str], bool],
    *,
    replace: bool = False,
) -> tuple[list[tuple[Path, str]], list[str]]:
    """Split archive files into uploads and already-canonical targets.

    Without ``replace`` an existing target is never clobbered, so the first
    archive of an issue date stays the one every later run points at.
    """
    planned: list[tuple[Path, str]] = []
    skipped: list[str] = []
    for path in sorted(files):
        target = f"forecasts/{issue_date}/{path.name}"
        if exists(target) and not replace:
            skipped.append(target)
        else:
            planned.append((path, target))
    return planned, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default="data/archive")
    parser.add_argument(
        "--issue-date",
        default=None,
        help="expected UTC issue date YYYY-MM-DD, verified against the parquet issue_time",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="overwrite an existing target (one-shot correction; the daily workflow never sets this)",
    )
    parser.add_argument(
        "--print-issue-date",
        metavar="PARQUET",
        default=None,
        help="print the issue date derived from PARQUET and exit",
    )
    parser.add_argument(
        "--card",
        metavar="PATH",
        default=None,
        help="also publish PATH as the dataset README.md, independently of the parquet skip",
    )
    args = parser.parse_args(argv)

    if args.print_issue_date:
        print(issue_date_from_parquet(args.print_issue_date))
        return 0

    token = os.environ.get("HF_TOKEN")
    repo = os.environ.get("HF_DATASET_REPO")
    if not token or not repo:
        print(
            "HF_TOKEN / HF_DATASET_REPO not configured; the workflow should use the "
            "GitHub Release fallback instead.",
            file=sys.stderr,
        )
        return 2

    archive_dir = Path(args.archive_dir)
    pattern = f"*_{args.issue_date}.parquet" if args.issue_date else "*.parquet"
    files = sorted(archive_dir.glob(pattern))
    if not files:
        print(f"no archive file for {args.issue_date or '*'} in {archive_dir}", file=sys.stderr)
        return 1

    try:
        derived = {issue_date_from_parquet(path) for path in files}
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    if len(derived) != 1:
        print(
            f"archive files span several issue dates: {', '.join(sorted(derived))}",
            file=sys.stderr,
        )
        return 1
    issue_date = derived.pop()
    if args.issue_date and args.issue_date != issue_date:
        print(
            f"--issue-date {args.issue_date} does not match the parquet issue_time "
            f"({issue_date}); refusing to archive under the wrong date",
            file=sys.stderr,
        )
        return 1

    card = Path(args.card) if args.card else None
    if card is not None and not card.is_file():
        print(f"card not found: {card}", file=sys.stderr)
        return 1

    from huggingface_hub import HfApi  # imported late: only needed when uploading

    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", exist_ok=True)

    planned, skipped = plan_uploads(
        files,
        issue_date,
        lambda target: api.file_exists(repo, target, repo_type="dataset"),
        replace=args.replace,
    )
    for target in skipped:
        print(f"skip {target}: already present (first archive of the issue date is frozen)")
    for path, target in planned:
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=target,
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"forecast archive {issue_date}",
        )
        print(f"uploaded {path.name} -> {repo}/{target}")
    if not planned:
        print(f"nothing to upload for {issue_date}")
    if card is not None:
        api.upload_file(
            path_or_fileobj=str(card),
            path_in_repo="README.md",
            repo_id=repo,
            repo_type="dataset",
            commit_message="update dataset card",
        )
        print(f"uploaded {card.name} -> {repo}/README.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
