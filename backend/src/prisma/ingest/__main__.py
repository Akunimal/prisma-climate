"""CLI: download and normalize sources into Parquet.

    python -m prisma.ingest --region argentina --tier 1
    python -m prisma.ingest --list
"""

from __future__ import annotations

import argparse

from .base import find_repo_root, load_region
from .registry import load_registry
from .runner import run_sources


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    parser = argparse.ArgumentParser(prog="python -m prisma.ingest")
    parser.add_argument("--region", default="argentina", help="file stem under configs/regions")
    parser.add_argument("--sources", default=None, help="comma separated source ids")
    parser.add_argument("--tier", type=int, default=None)
    parser.add_argument("--out", default="data/raw")
    parser.add_argument("--list", action="store_true", help="list registered sources and exit")
    args = parser.parse_args(argv)

    registry = load_registry(root / "configs" / "sources.yaml")

    if args.list:
        for entry in registry:
            print(f"tier {entry.get('tier')}  {entry.get('status'):<8} {entry['id']}")
        return 0

    region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
    ids = [item.strip() for item in args.sources.split(",")] if args.sources else None

    manifest = run_sources(region, registry, root / args.out, tier=args.tier, ids=ids)
    failed = [name for name, info in manifest["sources"].items() if info["status"] != "ok"]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
