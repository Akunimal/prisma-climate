"""Upload the daily forecast archive to a public Hugging Face dataset.

Used by .github/workflows/ingest.yml when HF_TOKEN (secret) and
HF_DATASET_REPO (repository variable) are configured. Exits with code 2 when
they are not, so the workflow can fall back to a GitHub Release.

    HF_TOKEN=... HF_DATASET_REPO=... \
      uv run --project backend --with huggingface_hub \
      python scripts/upload_forecast.py --archive-dir data/archive --issue-date 2026-11-11
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir", default="data/archive")
    parser.add_argument("--issue-date", required=True, help="UTC date of the forecast issue, YYYY-MM-DD")
    args = parser.parse_args(argv)

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
    files = sorted(archive_dir.glob(f"*_{args.issue_date}.parquet"))
    if not files:
        print(f"no archive file for {args.issue_date} in {archive_dir}", file=sys.stderr)
        return 1

    from huggingface_hub import HfApi  # imported late: only needed when uploading

    api = HfApi(token=token)
    api.create_repo(repo, repo_type="dataset", exist_ok=True)
    for path in files:
        api.upload_file(
            path_or_fileobj=str(path),
            path_in_repo=f"forecasts/{args.issue_date}/{path.name}",
            repo_id=repo,
            repo_type="dataset",
            commit_message=f"forecast archive {args.issue_date}",
        )
        print(f"uploaded {path.name} -> {repo}/forecasts/{args.issue_date}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
