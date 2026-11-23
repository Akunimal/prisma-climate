"""Tests for prisma.verify.leaderboard_doc — operational leaderboard static export.

Verifies strict gate protection, locked/unlocked state handling, and RFC 8259 JSON compliance.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from prisma.verify.leaderboard_doc import (
    GATE_ISSUE_DATES,
    SCHEMA_VERSION,
    build_leaderboard_document,
    resolve_archived_issue_dates,
)


def test_resolve_archived_issue_dates_reads_ingest_status(tmp_path: Path) -> None:
    results_dir = tmp_path / "results"
    results_dir.mkdir(parents=True)
    status_file = results_dir / "ingest_status.json"
    status_file.write_text(
        json.dumps({
            "archive_watchdog": {
                "archived_issue_dates": 12,
                "missing_issue_dates": ["2026-11-23"],
            }
        }),
        encoding="utf-8",
    )
    assert resolve_archived_issue_dates(tmp_path) == 12


def test_resolve_archived_issue_dates_handles_missing_files(tmp_path: Path) -> None:
    assert resolve_archived_issue_dates(tmp_path) == 0


def test_build_leaderboard_document_locked_state(tmp_path: Path) -> None:
    doc = build_leaderboard_document(tmp_path, override_issue_dates=12)
    assert doc["schema_version"] == SCHEMA_VERSION
    assert doc["protocol"] == "docs/EVALUATION_PROTOCOL.md"
    assert doc["gate"]["status"] == "locked"
    assert doc["gate"]["open"] is False
    assert doc["gate"]["archived_issue_dates"] == 12
    assert doc["gate"]["required_issue_dates"] == GATE_ISSUE_DATES
    assert doc["gate"]["remaining_issue_dates"] == 3
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["summary"] is None
    assert doc["cells"] == []

    # Strict JSON compliance test (zero NaN/Infinity)
    serialized = json.dumps(doc, allow_nan=False)
    assert "NaN" not in serialized
    assert "Infinity" not in serialized


def test_build_leaderboard_document_unlocked_with_synthetic_csv(tmp_path: Path) -> None:
    # Fabricate synthetic leaderboard CSV with finite and NaN values
    csv_file = tmp_path / "synthetic_leaderboard.csv"
    records = [
        {
            "location": "buenos_aires",
            "variable": "t2m_max",
            "model": "gfs_seamless",
            "lead_day": 1,
            "n_pairs": 15,
            "n_missing": 0,
            "insufficient": False,
            "n_climatology": 15,
            "n_persistence": 15,
            "crps_raw": 1.45,
            "crps_climatology": 2.10,
            "crps_persistence": 2.30,
            "crpss_vs_climatology": 0.3095,
            "crpss_vs_persistence": 0.3696,
        },
        {
            "location": "cordoba",
            "variable": "t2m_max",
            "model": "ecmwf_ifs025",
            "lead_day": 5,
            "n_pairs": 8,
            "n_missing": 2,
            "insufficient": True,
            "n_climatology": 8,
            "n_persistence": float("nan"),
            "crps_raw": 1.95,
            "crps_climatology": 2.20,
            "crps_persistence": float("nan"),
            "crpss_vs_climatology": float("nan"),
            "crpss_vs_persistence": float("nan"),
        },
    ]
    pd.DataFrame.from_records(records).to_csv(csv_file, index=False)

    doc = build_leaderboard_document(
        tmp_path,
        override_issue_dates=15,
        override_csv_path=csv_file,
    )
    assert doc["gate"]["status"] == "unlocked"
    assert doc["gate"]["open"] is True
    assert doc["gate"]["archived_issue_dates"] == 15
    assert doc["gate"]["remaining_issue_dates"] == 0
    assert doc["gate"]["operational_leaderboard_published"] is True
    assert doc["summary"] is not None
    assert doc["summary"]["n_cells"] == 2
    assert doc["summary"]["n_sufficient"] == 1
    assert doc["summary"]["mean_crpss_vs_climatology"] == 0.3095
    assert doc["summary"]["mean_crpss_vs_persistence"] == 0.3696

    assert len(doc["cells"]) == 2
    # Verify second cell has NaNs cleanly converted to None/null
    cell2 = doc["cells"][1]
    assert cell2["insufficient"] is True
    assert cell2["crpss_vs_climatology"] is None
    assert cell2["crpss_vs_persistence"] is None
    assert cell2["n_persistence"] is None

    # Strict JSON compliance test (zero NaN/Infinity)
    serialized = json.dumps(doc, allow_nan=False)
    assert "NaN" not in serialized
    assert "Infinity" not in serialized
    decoded = json.loads(serialized)
    assert decoded["cells"][1]["crpss_vs_climatology"] is None
