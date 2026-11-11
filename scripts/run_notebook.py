"""Execute notebooks/01_data_overview.ipynb headlessly and write figures to results/.

Usage (from the repository root):

    uv run --project backend python scripts/run_notebook.py

The kernel runs with the repository root as its working directory and the Agg
backend, so the run is reproducible on machines without a display.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

os.environ.setdefault("MPLBACKEND", "Agg")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    notebook_path = root / "notebooks" / "01_data_overview.ipynb"
    if not notebook_path.exists():
        print(f"missing notebook: {notebook_path}", file=sys.stderr)
        return 1

    nb = nbformat.read(notebook_path, as_version=4)
    client = NotebookClient(
        nb,
        timeout=600,
        kernel_name="python3",
    )
    try:
        client.execute(cwd=str(root))
    except Exception as exc:  # noqa: BLE001 - surface the failing cell to the user
        print(f"notebook execution failed: {exc}", file=sys.stderr)
        return 1

    figures = sorted((root / "results" / "figures").glob("*.png"))
    for figure in figures:
        print(figure.relative_to(root))
    if not figures:
        print("no figures written to results/figures/", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
