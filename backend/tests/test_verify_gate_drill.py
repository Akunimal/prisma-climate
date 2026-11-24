"""End-to-end gate unlock drill for Phase 1 operational verification.

Exercises the full pipeline in an isolated tmp_path without network calls:
1. Control below threshold (< 15 dates):
   - prisma.verify.run.main halts with gate refusal message.
   - scripts/export_site_data.py exports leaderboard.json with status == "locked".
2. At/above threshold (>= 15 dates):
   - run_above_gate executes scoring pipeline.
   - leaderboard.csv and strata tables are produced.
   - scripts/export_site_data.py exports leaderboard.json with status == "unlocked".
   - strict JSON RFC 8259 (zero NaN / Inf).
   - summary and cells conform to schema.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from test_verify_run import _e2e_workspace

from prisma.verify.leaderboard_doc import (
    GATE_ISSUE_DATES,
    MIN_SAMPLE,
    build_leaderboard_document,
)
from prisma.verify.run import main as verify_main
from prisma.verify.run import run_above_gate


def _get_export_site_data():
    import importlib.util

    export_script = Path(__file__).resolve().parents[2] / "scripts" / "export_site_data.py"
    spec = importlib.util.spec_from_file_location("export_site_data_module", export_script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.export_site_data



def test_gate_drill_below_threshold_stays_locked_and_empty(tmp_path: Path) -> None:
    root, list_files, _ = _e2e_workspace(tmp_path)
    all_paths = list_files()
    # Filter listing to only 14 forecast issue dates (below 15 gate)
    forecast_paths = [p for p in all_paths if p.startswith("forecasts/")]
    other_paths = [p for p in all_paths if not p.startswith("forecasts/")]
    truncated_forecasts = forecast_paths[:14]
    listing_14 = lambda: [*truncated_forecasts, *other_paths]  # noqa: E731

    # verify_main must refuse to compute and return code 1
    code = verify_main([], list_files=listing_14)
    assert code == 1

    # leaderboard_doc with 14 dates must be strictly locked
    doc = build_leaderboard_document(root, override_issue_dates=14)
    assert doc["schema_version"] == "1.0"
    assert doc["gate"]["status"] == "locked"
    assert doc["gate"]["open"] is False
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["gate"]["required_issue_dates"] == GATE_ISSUE_DATES
    assert doc["gate"]["archived_issue_dates"] == 14
    assert doc["gate"]["remaining_issue_dates"] == 1
    assert doc["summary"] is None
    assert doc["cells"] == []


def test_gate_drill_at_threshold_unlocked_pipeline_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root, list_files, download = _e2e_workspace(tmp_path)
    verification_dir = root / "results" / "verification"
    assert not verification_dir.exists()

    # Provide committed resolve table for site export
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    # 1. Execute run_above_gate with 15 dates
    code = run_above_gate(
        GATE_ISSUE_DATES, list_files=list_files, download=download, root=root
    )
    assert code == 0
    assert (verification_dir / "leaderboard.csv").is_file()
    assert (verification_dir / "leaderboard_by_issue_hour_stratum.csv").is_file()
    assert (verification_dir / "leaderboard.md").is_file()

    # 2. Wire and execute static export via scripts/export_site_data
    import importlib.util
    import sys

    export_script = Path(__file__).resolve().parents[2] / "scripts" / "export_site_data.py"
    spec = importlib.util.spec_from_file_location("export_site_data_drill", export_script)
    assert spec is not None and spec.loader is not None
    export_mod = importlib.util.module_from_spec(spec)
    sys.modules["export_site_data_drill"] = export_mod
    spec.loader.exec_module(export_mod)

    out_dir = root / "_site" / "data"
    written = export_mod.export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
    )
    assert len(written) >= 4
    leaderboard_file = out_dir / "leaderboard.json"
    assert leaderboard_file.is_file()

    # 3. Strict JSON check: no NaN, Inf, -Inf literals
    raw_text = leaderboard_file.read_text(encoding="utf-8")
    assert "NaN" not in raw_text
    assert "Infinity" not in raw_text
    assert "-Infinity" not in raw_text

    doc = json.loads(raw_text)

    # 4. Gate assertions: unlocked and published
    gate = doc["gate"]
    assert gate["status"] == "unlocked"
    assert gate["open"] is True
    assert gate["operational_leaderboard_published"] is True
    assert gate["required_issue_dates"] == GATE_ISSUE_DATES
    assert gate["archived_issue_dates"] >= GATE_ISSUE_DATES
    assert gate["remaining_issue_dates"] == 0

    # 5. Summary assertions
    summary = doc["summary"]
    assert summary is not None
    assert summary["n_cells"] == 3
    assert summary["n_sufficient"] == 1
    assert summary["min_sample_threshold"] == MIN_SAMPLE
    assert summary["mean_crpss_vs_climatology"] == pytest.approx(0.5)
    assert summary["mean_crpss_vs_persistence"] == pytest.approx(0.75)

    # 6. Cells assertions
    cells = doc["cells"]
    assert len(cells) == 3

    # Cell 1: gfs_seamless, lead 1 -> sufficient
    cell_gfs1 = next(
        c for c in cells if c["model"] == "gfs_seamless" and c["lead_day"] == 1
    )
    assert cell_gfs1["location"] == "Alfa"
    assert cell_gfs1["variable"] == "t2m_max"
    assert cell_gfs1["n_pairs"] == 15
    assert cell_gfs1["n_missing"] == 0
    assert cell_gfs1["insufficient"] is False
    assert cell_gfs1["crps_raw"] == pytest.approx(1.0)
    assert cell_gfs1["crps_climatology"] == pytest.approx(2.0)
    assert cell_gfs1["crps_persistence"] == pytest.approx(4.0)
    assert cell_gfs1["crpss_vs_climatology"] == pytest.approx(0.5)
    assert cell_gfs1["crpss_vs_persistence"] == pytest.approx(0.75)

    # Cell 2: gfs_seamless, lead 2 -> insufficient sample (n_pairs = 3 < 10)
    cell_gfs2 = next(
        c for c in cells if c["model"] == "gfs_seamless" and c["lead_day"] == 2
    )
    assert cell_gfs2["n_pairs"] == 3
    assert cell_gfs2["insufficient"] is True
    assert cell_gfs2["crpss_vs_climatology"] is None
    assert cell_gfs2["crpss_vs_persistence"] is None

    # Cell 3: ecmwf_ifs025 -> insufficient members (< 80%)
    cell_ecmwf = next(c for c in cells if c["model"] == "ecmwf_ifs025")
    assert cell_ecmwf["n_pairs"] == 0
    assert cell_ecmwf["n_missing"] == 15
    assert cell_ecmwf["insufficient"] is True
    assert cell_ecmwf["crps_raw"] is None


def test_auto_wire_below_threshold_skips_verification(tmp_path: Path) -> None:
    """Gate closed (<15 dates): export_site_data skips verification and exports locked doc."""
    export_site_data = _get_export_site_data()

    root, list_files, download = _e2e_workspace(tmp_path)
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    all_paths = list_files()
    forecast_paths = [p for p in all_paths if p.startswith("forecasts/")]
    other_paths = [p for p in all_paths if not p.startswith("forecasts/")]
    listing_14 = lambda: [*forecast_paths[:14], *other_paths]  # noqa: E731

    out_dir = root / "_site" / "data"
    written = export_site_data(
        root=root,
        list_files=listing_14,
        download=download,
        out_dir=out_dir,
    )
    assert len(written) >= 4

    # Verification must NOT have run (no leaderboard.csv created)
    assert not (root / "results" / "verification" / "leaderboard.csv").exists()

    # leaderboard.json must be locked
    doc = json.loads((out_dir / "leaderboard.json").read_text(encoding="utf-8"))
    assert doc["gate"]["status"] == "locked"
    assert doc["gate"]["open"] is False
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["gate"]["archived_issue_dates"] == 14
    assert doc["gate"]["remaining_issue_dates"] == 1
    assert doc["cells"] == []


def test_auto_wire_at_threshold_runs_verification_automatically(tmp_path: Path) -> None:
    """Day 15 threshold: export_site_data auto-wires run_above_gate without manual step."""
    export_site_data = _get_export_site_data()

    root, list_files, download = _e2e_workspace(tmp_path)
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    verification_csv = root / "results" / "verification" / "leaderboard.csv"
    assert not verification_csv.exists()

    out_dir = root / "_site" / "data"
    # Invoke export_site_data directly WITHOUT manually calling run_above_gate
    written = export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
    )
    assert len(written) >= 4

    # run_above_gate was triggered automatically, creating leaderboard.csv
    assert verification_csv.is_file()

    doc = json.loads((out_dir / "leaderboard.json").read_text(encoding="utf-8"))
    assert doc["gate"]["status"] == "unlocked"
    assert doc["gate"]["open"] is True
    assert doc["gate"]["operational_leaderboard_published"] is True
    assert doc["gate"]["archived_issue_dates"] >= GATE_ISSUE_DATES
    assert doc["gate"]["remaining_issue_dates"] == 0
    assert len(doc["cells"]) == 3
    assert doc["summary"]["n_cells"] == 3


def test_auto_wire_day16_refreshes_stale_leaderboard(tmp_path: Path) -> None:
    """Day 16+ idempotence: stale/frozen leaderboard.csv is recomputed and overwritten."""
    export_site_data = _get_export_site_data()

    root, list_files, download = _e2e_workspace(tmp_path)
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    # Seed an obsolete/stale leaderboard.csv with fake n_pairs
    stale_csv = root / "results" / "verification" / "leaderboard.csv"
    stale_csv.parent.mkdir(parents=True, exist_ok=True)
    stale_csv.write_text(
        "model,location,variable,lead_day,n_pairs,n_missing,insufficient,"
        "crps_raw,crps_climatology,crps_persistence,crpss_vs_climatology,crpss_vs_persistence\n"
        "gfs_seamless,Alfa,t2m_max,1,9999,0,False,0.1,0.2,0.4,0.5,0.75\n",
        encoding="utf-8",
    )

    out_dir = root / "_site" / "data"
    export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
    )

    # Verify that stale_csv was overwritten with fresh run results (n_pairs is 15, not 9999)
    doc = json.loads((out_dir / "leaderboard.json").read_text(encoding="utf-8"))
    cell_gfs1 = next(
        c for c in doc["cells"] if c["model"] == "gfs_seamless" and c["lead_day"] == 1
    )
    assert cell_gfs1["n_pairs"] == 15
    assert cell_gfs1["n_pairs"] != 9999


def test_auto_wire_handles_verification_failure_gracefully(tmp_path: Path) -> None:
    """Controlled failure: error in run_above_gate degrades leaderboard safely without crash."""
    export_site_data = _get_export_site_data()

    root, list_files, download = _e2e_workspace(tmp_path)
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    out_dir = root / "_site" / "data"

    def _failing_verifier(dates: int) -> int:
        raise RuntimeError("Disk full / I/O simulated verification error")

    # Export must NOT raise an exception
    written = export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
        run_verify=_failing_verifier,
    )
    assert len(written) >= 4

    # Essential site files must still exist
    assert (out_dir / "latest.json").is_file()
    assert (out_dir / "about.json").is_file()
    assert (out_dir / "skill.json").is_file()
    assert (out_dir / "leaderboard.json").is_file()

    # leaderboard.json safely degraded to unpublished
    doc = json.loads((out_dir / "leaderboard.json").read_text(encoding="utf-8"))
    assert doc["gate"]["status"] == "unlocked"
    assert doc["gate"]["open"] is True
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["summary"] is None
    assert doc["cells"] == []


def test_auto_wire_skip_verify_flag(tmp_path: Path) -> None:
    """Flag --skip-verify explicitly suppresses verification even at/above gate threshold."""
    export_site_data = _get_export_site_data()

    root, list_files, download = _e2e_workspace(tmp_path)
    (root / "results" / "regtemp_names").mkdir(parents=True, exist_ok=True)
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        "location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status\n"
        "Alfa,87007,Alfa,Alfa,Alfa,365,resolved\n",
        encoding="utf-8",
    )

    verification_csv = root / "results" / "verification" / "leaderboard.csv"
    assert not verification_csv.exists()

    out_dir = root / "_site" / "data"
    written = export_site_data(
        root=root,
        list_files=list_files,
        download=download,
        out_dir=out_dir,
        skip_verify=True,
    )
    assert len(written) >= 4

    # Verification must NOT have run
    assert not verification_csv.exists()

    # leaderboard.json must not be published
    doc = json.loads((out_dir / "leaderboard.json").read_text(encoding="utf-8"))
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["cells"] == []


def test_resolve_archived_issue_dates_type_safety(tmp_path: Path) -> None:
    """Type safety: numeric strings and floats in ingest_status.json parse safely."""
    from prisma.verify.leaderboard_doc import resolve_archived_issue_dates

    # 1. Clean root with no status files -> 0
    assert resolve_archived_issue_dates(tmp_path) == 0

    # 2. String-encoded integer in watchdog
    status_file = tmp_path / "results" / "ingest_status.json"
    status_file.parent.mkdir(parents=True, exist_ok=True)
    status_file.write_text(
        json.dumps({"archive_watchdog": {"archived_issue_dates": "15"}}),
        encoding="utf-8",
    )
    assert resolve_archived_issue_dates(tmp_path) == 15

    # 3. Float in watchdog
    status_file.write_text(
        json.dumps({"archive_watchdog": {"archived_issue_dates": 15.0}}),
        encoding="utf-8",
    )
    assert resolve_archived_issue_dates(tmp_path) == 15

    # 4. Invalid / corrupt watchdog value falls back safely to 0
    status_file.write_text(
        json.dumps({"archive_watchdog": {"archived_issue_dates": "not-a-number"}}),
        encoding="utf-8",
    )
    assert resolve_archived_issue_dates(tmp_path) == 0


def test_build_leaderboard_document_handles_empty_or_corrupt_csv(tmp_path: Path) -> None:
    """Defensive fail-safe: 0-byte or corrupted CSV degrades safely to unpublished state."""
    from prisma.verify.leaderboard_doc import build_leaderboard_document

    csv_dir = tmp_path / "results" / "verification"
    csv_dir.mkdir(parents=True, exist_ok=True)
    csv_file = csv_dir / "leaderboard.csv"

    # 1. 0-byte empty file
    csv_file.write_bytes(b"")
    doc = build_leaderboard_document(tmp_path, override_issue_dates=15)
    assert doc["gate"]["status"] == "unlocked"
    assert doc["gate"]["open"] is True
    assert doc["gate"]["operational_leaderboard_published"] is False
    assert doc["summary"] is None
    assert doc["cells"] == []
    assert "failed to read verification CSV" in doc["gate"]["note"]

    # 2. Corrupt binary garbage
    csv_file.write_bytes(b"\x00\xff\xfe\x00\x01\x02\x03")
    doc_corrupt = build_leaderboard_document(tmp_path, override_issue_dates=15)
    assert doc_corrupt["gate"]["status"] == "unlocked"
    assert doc_corrupt["gate"]["open"] is True
    assert doc_corrupt["gate"]["operational_leaderboard_published"] is False
    assert doc_corrupt["summary"] is None
    assert doc_corrupt["cells"] == []


def test_build_leaderboard_document_boundary_14_vs_15(tmp_path: Path) -> None:
    """Exact boundary condition: 14 dates strictly locked, 15 dates unlocked."""
    from prisma.verify.leaderboard_doc import build_leaderboard_document

    # 14 dates: strictly locked, open=False
    doc14 = build_leaderboard_document(tmp_path, override_issue_dates=14)
    assert doc14["gate"]["status"] == "locked"
    assert doc14["gate"]["open"] is False
    assert doc14["gate"]["archived_issue_dates"] == 14
    assert doc14["gate"]["remaining_issue_dates"] == 1
    assert doc14["gate"]["operational_leaderboard_published"] is False
    assert doc14["summary"] is None
    assert doc14["cells"] == []

    # 15 dates (no CSV yet): unlocked, open=True, remaining=0, published=False
    doc15 = build_leaderboard_document(tmp_path, override_issue_dates=15)
    assert doc15["gate"]["status"] == "unlocked"
    assert doc15["gate"]["open"] is True
    assert doc15["gate"]["archived_issue_dates"] == 15
    assert doc15["gate"]["remaining_issue_dates"] == 0
    assert doc15["gate"]["operational_leaderboard_published"] is False
    assert doc15["summary"] is None
    assert doc15["cells"] == []



