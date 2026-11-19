"""Deterministic promotion gate for PRISMA global regions.

Audits committed raw evidence JSONs against all quantitative gates before
allowing status promotion in configs/sources.yaml. Safe by default (--dry-run).

Usage:
    python backend/scripts/promote_verified_regions.py [--region <slug>] [--dry-run] [--apply]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
NON_ARGENTINA_REGIONS = [
    "south_america",
    "north_america",
    "europe",
    "asia",
    "africa",
    "oceania",
    "middle_east",
]


def evaluate_region_readiness(region_slug: str) -> dict[str, Any]:
    evidence_path = ROOT / "results" / "stations" / "_evidence" / region_slug / "audit.json"
    if not evidence_path.exists():
        return {
            "region": region_slug,
            "eligible": False,
            "reason": f"Missing evidence file: {evidence_path.relative_to(ROOT)}",
        }

    with open(evidence_path, encoding="utf-8") as f:
        data = json.load(f)

    summary = data.get("summary", {})
    stations = data.get("stations", [])

    # Check 1: §3.8 Source probe status
    p1_val = summary.get("phase1_source_status") or summary.get("phase1_probe_status") or "UNKNOWN"
    p1_status = p1_val == "PASS"
    # Check 2: Phase 2 Vetting status
    p2_val = summary.get("phase2_vetting_status") or "UNKNOWN"
    p2_status = p2_val == "PASS"
    # Check 3: Phase 3 Obs reference telemetry status
    p3_val = summary.get("phase3_obs_status") or "UNKNOWN"
    p3_status = p3_val in ("PASS", "QUALIFIED")
    # Check 4: Retained station count >= 12
    retained_count = summary.get("retained_count", 0)
    count_ok = retained_count >= 12
    # Check 5: Telemetry >= 80%
    telemetry_pct = summary.get("active_telemetry_pct", 0.0)
    telemetry_ok = telemetry_pct >= 80.0
    # Check 6: Dual confirmation >= 80%
    confirmed_pct = summary.get("confirmed_second_source_pct", 0.0)
    confirmed_ok = confirmed_pct >= 80.0

    eligible = (
        p1_status
        and p2_status
        and p3_status
        and count_ok
        and telemetry_ok
        and confirmed_ok
    )

    reasons: list[str] = []
    if not p1_status:
        reasons.append(f"Phase 1 source check failed ({p1_val})")
    if not p2_status:
        reasons.append(f"Phase 2 vetting failed ({p2_val})")
    if not p3_status:
        reasons.append(f"Phase 3 obs status failed ({p3_val})")
    if not count_ok:
        reasons.append(f"Retained stations {retained_count} < 12")
    if not telemetry_ok:
        reasons.append(f"Active telemetry {telemetry_pct}% < 80.0%")
    if not confirmed_ok:
        reasons.append(f"Dual-catalog confirmation {confirmed_pct}% < 80.0%")

    return {
        "region": region_slug,
        "region_name": summary.get("region_name", region_slug),
        "eligible": eligible,
        "p1_probe": p1_val,
        "p2_vetting": p2_val,
        "p3_obs": p3_val,
        "retained": f"{retained_count}/{summary.get('total_stations', 0)}",
        "telemetry_pct": f"{telemetry_pct}%",
        "confirmed_pct": f"{confirmed_pct}%",
        "decision": "READY_FOR_REVIEW" if eligible else "BLOCKED",
        "reasons": "; ".join(reasons) if reasons else "All quantitative gates passed.",
    }


def run_promotion_gate(
    regions: list[str],
    dry_run: bool = True,
    apply: bool = False,
    target_status: str = "ready_for_review",
) -> int:
    evaluations = [evaluate_region_readiness(slug) for slug in regions]

    print("=" * 80)
    print("PRISMA CLIMATE — DETERMINISTIC REGIONAL PROMOTION GATE")
    print(f"Timestamp: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Mode: {'DRY RUN (no changes applied)' if dry_run else 'APPLY CHANGES'}")
    print("=" * 80)
    print(
        f"{'Region':<16} | {'P1':<6} | {'P2':<6} | {'P3':<6} | {'Retained':<9} | {'Telemetry':<10} | {'Decision':<16}"
    )
    print("-" * 80)

    for ev in evaluations:
        if "reason" in ev and not ev.get("eligible"):
            print(f"{ev['region']:<16} | ERROR: {ev['reason']}")
            continue
        print(
            f"{ev['region']:<16} | {ev['p1_probe']:<6} | {ev['p2_vetting']:<6} | {ev['p3_obs']:<6} | "
            f"{ev['retained']:<9} | {ev['telemetry_pct']:<10} | {ev['decision']:<16}"
        )
        if ev["decision"] == "BLOCKED":
            print(f"   -> Block reason: {ev['reasons']}")

    print("=" * 80)

    passing = [e for e in evaluations if e.get("eligible")]
    blocked = [e for e in evaluations if not e.get("eligible")]
    print(f"Summary: {len(passing)} eligible for '{target_status}', {len(blocked)} blocked.")

    if dry_run or not apply:
        print("\n[DRY RUN] No modifications written to configs/sources.yaml.")
        return 0

    # Apply changes to configs/sources.yaml
    sources_yaml_path = ROOT / "configs" / "sources.yaml"
    with open(sources_yaml_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    changed = 0
    for src in data.get("sources", []):
        src_id = src.get("id", "")
        for ev in evaluations:
            region_slug = ev["region"]
            expected_id = f"metar-{region_slug.replace('_', '-')}"
            if src_id == expected_id:
                if ev.get("eligible"):
                    old_st = src.get("status")
                    src["status"] = target_status
                    print(f"Updated {src_id}: status '{old_st}' -> '{target_status}'")
                    changed += 1
                else:
                    old_st = src.get("status")
                    src["status"] = "blocked"
                    print(f"Updated {src_id}: status '{old_st}' -> 'blocked'")
                    changed += 1

    if changed > 0:
        with open(sources_yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        print(f"\nApplied updates to {changed} sources in {sources_yaml_path.relative_to(ROOT)}.")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        choices=NON_ARGENTINA_REGIONS + ["all"],
        default="all",
        help="Region to evaluate (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Run without modifying configs (default: True)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply ready_for_review status updates to configs/sources.yaml",
    )
    args = parser.parse_args(argv)

    regions = NON_ARGENTINA_REGIONS if args.region == "all" else [args.region]
    is_apply = args.apply

    return run_promotion_gate(
        regions=regions,
        dry_run=not is_apply,
        apply=is_apply,
        target_status="ready_for_review",
    )


if __name__ == "__main__":
    sys.exit(main())
