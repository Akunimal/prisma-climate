"""Capture METAR daily observations and archive them under ``observations/metar/``.

Fetches aggregated daily observations (t2m_max, t2m_min, precip) across worldwide
aerodromes declaring an ICAO code, saves them to a standardized Parquet file, and
optionally uploads to the Hugging Face dataset.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from prisma.ingest.base import load_all_regions
from prisma.ingest.metar import MetarGlobal


def capture_metar_observations(
    root: Path | None = None,
    hours: int = 48,
    out_dir: Path | str = "data/observations/metar",
) -> Path:
    """Fetch global METAR observations and write to local Parquet."""
    repo_root = Path(root) if root else Path(__file__).resolve().parents[1]
    region = load_all_regions(repo_root)
    connector = MetarGlobal(hours=hours)

    frame = connector.fetch_normalized(region)
    if frame.empty:
        print("warning: no METAR observations returned")

    date_str = datetime.now(UTC).strftime("%Y-%m-%d")
    out_path = Path(out_dir) / f"{date_str}.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(out_path, index=False)
    print(f"saved {len(frame)} METAR observation rows to {out_path}")
    return out_path


def upload_to_hf(parquet_path: Path, repo_id: str, token: str, replace: bool = False) -> bool:
    """Upload Parquet snapshot to Hugging Face dataset."""
    from huggingface_hub import HfApi

    api = HfApi(token=token)
    target = f"observations/metar/{parquet_path.name}"

    try:
        if not replace and api.file_exists(repo_id, target, repo_type="dataset"):
            print(f"target {target} already exists on {repo_id}; skipping")
            return False
    except Exception as exc:
        print(f"warning: file_exists check failed ({exc}); attempting upload")

    api.upload_file(
        path_or_fileobj=str(parquet_path),
        path_in_repo=target,
        repo_id=repo_id,
        repo_type="dataset",
        commit_message=f"chore: archive METAR observations {parquet_path.name}",
    )
    print(f"uploaded {parquet_path} -> {repo_id}:{target}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="repository root path")
    parser.add_argument("--hours", type=int, default=48, help="METAR lookback window in hours")
    parser.add_argument("--out-dir", default="data/observations/metar", help="output directory")
    parser.add_argument("--upload", action="store_true", help="upload to Hugging Face dataset")
    parser.add_argument("--replace", action="store_true", help="overwrite existing target in HF")
    args = parser.parse_args(argv)

    parquet_path = capture_metar_observations(
        root=Path(args.root) if args.root else None,
        hours=args.hours,
        out_dir=args.out_dir,
    )

    if args.upload:
        token = os.environ.get("HF_TOKEN")
        repo_id = os.environ.get("HF_DATASET_REPO")
        if not token or not repo_id:
            print("error: HF_TOKEN and HF_DATASET_REPO required for --upload", file=sys.stderr)
            return 2
        upload_to_hf(parquet_path, repo_id, token, replace=args.replace)

    return 0


if __name__ == "__main__":
    sys.exit(main())
