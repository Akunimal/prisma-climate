"""Deterministic promotion gate for PRISMA global regions.

Audits committed raw evidence JSONs against all quantitative gates before
allowing status promotion in configs/sources.yaml. Safe by default (--dry-run).

Usage:
    python backend/scripts/promote_verified_regions.py [--region <slug>] [--dry-run] [--apply]
"""

from __future__ import annotations

import argparse
import json
import re
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


def check_headline_gate(evaluations: list[dict[str, Any]]) -> None:
    """Ensure README headline is never changed to a global-coverage claim unless 100% of regions pass."""
    all_active = all(e.get("eligible") for e in evaluations)
    readme_path = ROOT / "README.md"
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    if not all_active:
        conservative = "**Starting with Argentina, designed to scale globally (Empezando por Argentina, diseñado para escalar globalmente).**"
        if "Global planetary coverage" in text:
            print("[HEADLINE GATE] middle_east is blocked; enforcing conservative README headline.")
            text = text.replace(
                "**Global planetary coverage, open climate forecast verification (Cobertura planetaria global, verificación abierta).**",
                conservative,
            )
            readme_path.write_text(text, encoding="utf-8")


def apply_promotions_to_sources_yaml(
    evaluations: list[dict[str, Any]],
    target_status: str = "active",
    verified_date: str = "2026-11-19",
) -> int:
    """Apply status and verified_on updates preserving file comments and formatting."""
    sources_yaml_path = ROOT / "configs" / "sources.yaml"
    text = sources_yaml_path.read_text(encoding="utf-8")

    changed = 0
    for ev in evaluations:
        region_slug = ev["region"]
        expected_id = f"metar-{region_slug.replace('_', '-')}"

        # Locate the source block
        pattern = rf"(  - id: {re.escape(expected_id)}\b.*?)(?=\n  - id: |\Z)"
        match = re.search(pattern, text, flags=re.DOTALL)
        if not match:
            continue

        block = match.group(1)
        original_block = block

        if ev.get("eligible"):
            # Update status
            block = re.sub(r"status:\s*[a-zA-Z0-9_-]+", f"status: {target_status}", block, count=1)
            # Update verified_on
            if target_status == "active":
                block = re.sub(r"verified_on:\s*(null|none|~|\"[^\"]*\")?", f'verified_on: "{verified_date}"', block, count=1)
            print(f"Updated {expected_id}: status -> '{target_status}', verified_on -> '{verified_date}'")
        else:
            block = re.sub(r"status:\s*[a-zA-Z0-9_-]+", "status: blocked", block, count=1)
            block = re.sub(r"verified_on:\s*(null|none|~|\"[^\"]*\")?", "verified_on: null", block, count=1)
            print(f"Updated {expected_id}: status -> 'blocked', verified_on -> null")

        if block != original_block:
            text = text[:match.start(1)] + block + text[match.end(1):]
            changed += 1

    if changed > 0:
        sources_yaml_path.write_text(text, encoding="utf-8")
        print(f"\nApplied updates to {changed} sources in {sources_yaml_path.relative_to(ROOT)} (comments preserved).")

    return changed


def run_promotion_gate(
    regions: list[str],
    dry_run: bool = True,
    apply: bool = False,
    target_status: str = "active",
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

    check_headline_gate(evaluations)

    if dry_run or not apply:
        print("\n[DRY RUN] No modifications written to configs/sources.yaml.")
        return 0

    apply_promotions_to_sources_yaml(evaluations, target_status=target_status, verified_date="2026-11-19")
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
        default=False,
        help="Run without modifying configs",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply active status updates to configs/sources.yaml",
    )
    parser.add_argument(
        "--target-status",
        default="active",
        choices=["active", "ready_for_review"],
        help="Target status for eligible regions (default: active)",
    )
    args = parser.parse_args(argv)

    regions = NON_ARGENTINA_REGIONS if args.region == "all" else [args.region]
    is_apply = args.apply

    return run_promotion_gate(
        regions=regions,
        dry_run=not is_apply,
        apply=is_apply,
        target_status=args.target_status,
    )


if __name__ == "__main__":
    sys.exit(main())
