"""Reconcile every distinct regtemp station name against the SMN catalogue.

regtemp has no NRO or coordinates (FECHA/TMAX/TMIN/NOMBRE only), so the join is
name-based. Fixed-column parsing is required: blank TMAX/TMIN shift fields and a
whitespace split invents fake station tokens. This script writes a full table
under results/regtemp_names/. Values in results/ come only from this script.

    uv run --project backend python scripts/reconcile_regtemp_names.py

Outputs:
- regtemp_names.csv  — every distinct NOMBRE, day count, match status, flags
- regtemp_names.md   — summary, partial-coverage table, region resolution

Prerequisite for wiring the regtemp backfill (T22); this script does not wire
anything into the connector.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGTEMP = REPO / "data" / "smn_probe" / "regtemp" / "registro_temperatura365d_smn.txt"
CATALOGUE = REPO / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
REGION_CSV = REPO / "results" / "stations" / "ghcn_vs_smn.csv"
OUT_DIR = REPO / "results" / "regtemp_names"

EXPECTED_DAYS = 365
FUZZY_CUTOFF = 0.85


def parse_regtemp(path: Path) -> dict[str, set[str]]:
    """Return {NOMBRE: {distinct FECHA strings}}. Fixed columns, latin-1.

    Skips the header and the dashed separator row (FECHA must be 8 digits).
    """
    days: dict[str, set[str]] = defaultdict(set)
    with path.open(encoding="latin-1") as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            if not line.strip() or len(line) < 22:
                continue
            fecha = line[0:8]
            if not (fecha.isdigit() and len(fecha) == 8):
                continue
            nombre = line[21:].strip()
            if not nombre:
                continue
            days[nombre].add(fecha)
    return dict(days)


def parse_catalogue(path: Path) -> list[dict[str, str]]:
    """Parse estaciones_smn.txt with fixed columns; join name-wrap fragments.

    Name = chars 0-30, NRO = chars 110-115. Lines without an NRO segment are
    name-wrap fragments of the previous station and are appended to its name.
    """
    stations: list[dict[str, str]] = []
    with path.open(encoding="latin-1") as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            if not line.strip():
                continue
            # Skip header / unit lines (no NRO and not a wrap continuation of data)
            nro = line[110:115].strip() if len(line) > 115 else ""
            name = line[0:30].strip()
            if nro.isdigit():
                stations.append({"name": name, "nro": nro})
            elif stations and name:
                # 30-char name field truncated mid-word; fragment continues it
                stations[-1]["name"] = stations[-1]["name"] + name
            # else: header/units/blank — ignore
    return stations


def parse_region(path: Path) -> list[dict[str, str]]:
    """Region stations from ghcn_vs_smn.csv: location, smn_nro, smn_name."""
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    "location": row["location"],
                    "smn_nro": row["smn_nro"].strip(),
                    "smn_name": row["smn_name"].strip(),
                }
            )
    return rows


def match_names(
    regtemp_names: list[str], catalogue: list[dict[str, str]]
) -> list[dict[str, str]]:
    """Exact / fuzzy / none match for each regtemp name against the catalogue."""
    by_name: dict[str, list[dict[str, str]]] = defaultdict(list)
    for station in catalogue:
        by_name[station["name"]].append(station)

    catalog_names = sorted(by_name)
    results: list[dict[str, str]] = []
    for name in sorted(regtemp_names):
        hits = by_name.get(name, [])
        if len(hits) == 1:
            status = "exact"
            nro = hits[0]["nro"]
            candidates = ""
            flag = ""
        elif len(hits) > 1:
            status = "exact"
            nro = ";".join(h["nro"] for h in hits)
            candidates = ""
            flag = "one-to-many"
        else:
            close = difflib.get_close_matches(name, catalog_names, n=3, cutoff=FUZZY_CUTOFF)
            if close:
                status = "fuzzy"
                nro = ";".join(by_name[c][0]["nro"] for c in close)
                candidates = ";".join(close)
                flag = "ambiguous" if len(close) > 1 else ""
            else:
                status = "none"
                nro = ""
                candidates = ""
                flag = "unmatched"
        results.append(
            {
                "regtemp_name": name,
                "match_status": status,
                "catalogue_nro": nro,
                "fuzzy_candidates": candidates,
                "flag": flag,
            }
        )
    return results


def resolve_region(
    region: list[dict[str, str]],
    catalogue: list[dict[str, str]],
    regtemp_days: dict[str, set[str]],
) -> list[dict[str, str]]:
    """Resolve each region station via catalogue NRO -> name -> regtemp days."""
    by_nro = {s["nro"]: s for s in catalogue}
    resolved: list[dict[str, str]] = []
    for row in region:
        nro = row["smn_nro"]
        station = by_nro.get(nro)
        if station is None:
            resolved.append(
                {
                    "location": row["location"],
                    "smn_nro": nro,
                    "smn_name": row["smn_name"],
                    "catalogue_name": "",
                    "regtemp_name": "",
                    "days": "0",
                    "status": "catalogue_nro_missing",
                }
            )
            continue
        cname = station["name"]
        # Exact name match into regtemp
        if cname in regtemp_days:
            days = len(regtemp_days[cname])
            status = "resolved" if days >= EXPECTED_DAYS else "partial"
            resolved.append(
                {
                    "location": row["location"],
                    "smn_nro": nro,
                    "smn_name": row["smn_name"],
                    "catalogue_name": cname,
                    "regtemp_name": cname,
                    "days": str(days),
                    "status": status,
                }
            )
        else:
            # Fuzzy fallback against regtemp names
            close = difflib.get_close_matches(
                cname, sorted(regtemp_days), n=1, cutoff=FUZZY_CUTOFF
            )
            if close:
                days = len(regtemp_days[close[0]])
                status = "resolved_fuzzy" if days >= EXPECTED_DAYS else "partial_fuzzy"
                resolved.append(
                    {
                        "location": row["location"],
                        "smn_nro": nro,
                        "smn_name": row["smn_name"],
                        "catalogue_name": cname,
                        "regtemp_name": close[0],
                        "days": str(days),
                        "status": status,
                    }
                )
            else:
                resolved.append(
                    {
                        "location": row["location"],
                        "smn_nro": nro,
                        "smn_name": row["smn_name"],
                        "catalogue_name": cname,
                        "regtemp_name": "",
                        "days": "0",
                        "status": "not_in_regtemp",
                    }
                )
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regtemp", type=Path, default=REGTEMP)
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE)
    parser.add_argument("--region", type=Path, default=REGION_CSV)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    for path in (args.regtemp, args.catalogue, args.region):
        if not path.is_file():
            print(f"missing file: {path}", file=sys.stderr)
            return 1

    regtemp_days = parse_regtemp(args.regtemp)
    catalogue = parse_catalogue(args.catalogue)
    region = parse_region(args.region)

    total_rows = sum(len(v) for v in regtemp_days.values())
    distinct_days = set()
    for days in regtemp_days.values():
        distinct_days |= days

    matches = match_names(sorted(regtemp_days), catalogue)
    region_resolved = resolve_region(region, catalogue, regtemp_days)

    # Coverage flags
    by_name_days = {m["regtemp_name"]: m for m in matches}
    for name, days in regtemp_days.items():
        row = by_name_days.get(name)
        if row is None:
            continue
        n = len(days)
        if n < EXPECTED_DAYS:
            extra = "partial_coverage"
            row["flag"] = (row["flag"] + ";" + extra).strip(";")
        else:
            row["days"] = str(n)
        row["days"] = str(n)

    status_counts = defaultdict(int)
    for m in matches:
        status_counts[m["match_status"]] += 1

    partial_names = sorted(n for n, d in regtemp_days.items() if len(d) < EXPECTED_DAYS)
    missing_station_days = sum(EXPECTED_DAYS - len(regtemp_days[n]) for n in partial_names)

    catalog_names = {s["name"] for s in catalogue}
    regtemp_names = set(regtemp_days)
    catalog_not_in_regtemp = sorted(catalog_names - regtemp_names)

    # Duplicate catalogue names (one-to-many risk)
    name_counts: dict[str, int] = defaultdict(int)
    for s in catalogue:
        name_counts[s["name"]] += 1
    duplicates = sorted(n for n, c in name_counts.items() if c > 1)

    ambiguous = [m for m in matches if m["match_status"] == "fuzzy"]
    unmatched = [m for m in matches if m["match_status"] == "none"]

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # CSV: every distinct regtemp name
    csv_path = args.out_dir / "regtemp_names.csv"
    fieldnames = [
        "regtemp_name",
        "days",
        "match_status",
        "catalogue_nro",
        "fuzzy_candidates",
        "flag",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for m in sorted(matches, key=lambda r: r["regtemp_name"]):
            m = dict(m)
            m["days"] = str(len(regtemp_days[m["regtemp_name"]]))
            writer.writerow({k: m.get(k, "") for k in fieldnames})

    # Region CSV
    region_path = args.out_dir / "region_resolution.csv"
    region_fields = [
        "location",
        "smn_nro",
        "smn_name",
        "catalogue_name",
        "regtemp_name",
        "days",
        "status",
    ]
    with region_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=region_fields)
        writer.writeheader()
        for row in region_resolved:
            writer.writerow(row)

    region_ok = sum(1 for r in region_resolved if r["status"].startswith("resolved"))
    region_partial = sum(1 for r in region_resolved if r["status"].startswith("partial"))
    region_bad = sum(
        1 for r in region_resolved if r["status"] in ("catalogue_nro_missing", "not_in_regtemp")
    )

    # Markdown report
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = []
    lines.append("# regtemp station-name reconciliation")
    lines.append("")
    lines.append(f"Generated {now} by `scripts/reconcile_regtemp_names.py`.")
    lines.append("Values in `results/` come only from this script.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- regtemp rows with parseable name/date: **{total_rows}**")
    lines.append(f"- distinct local days: **{len(distinct_days)}** (expected {EXPECTED_DAYS})")
    lines.append(f"- distinct `NOMBRE` values: **{len(regtemp_days)}**")
    lines.append(f"- catalogue stations parsed: **{len(catalogue)}**")
    lines.append(f"- catalogue names not present in regtemp: **{len(catalog_not_in_regtemp)}**")
    lines.append("")
    lines.append("| Match status | Count |")
    lines.append("|---|---|")
    for status in ("exact", "fuzzy", "none"):
        lines.append(f"| {status} | {status_counts.get(status, 0)} |")
    lines.append("")
    lines.append(f"- Ambiguous (fuzzy) matches: **{len(ambiguous)}**")
    lines.append(f"- Unmatched (no catalogue hit): **{len(unmatched)}**")
    lines.append(f"- One-to-many catalogue duplicates: **{len(duplicates)}**")
    if duplicates:
        lines.append(f"  - {', '.join(duplicates)}")
    lines.append("")
    lines.append("### Why not 135 names")
    lines.append("")
    lines.append(
        "A whitespace `split()` parse of regtemp yields ~134 distinct tokens because "
        "rows with blank `TMAX`/`TMIN` shift fields and invent fake station tokens "
        "(e.g. `AERO`). Fixed-column parsing "
        "(name at chars 21+, date at chars 0-8 as `DDMMYYYY`) is required and gives "
        f"**{len(regtemp_days)}** distinct names over **{total_rows}** rows / "
        f"**{len(distinct_days)}** days."
    )
    lines.append("")
    lines.append("## Partial coverage")
    lines.append("")
    if partial_names:
        lines.append("| Station | Days present | Missing days |")
        lines.append("|---|---|---|")
        for name in partial_names:
            n = len(regtemp_days[name])
            lines.append(f"| {name} | {n} | {EXPECTED_DAYS - n} |")
        lines.append("")
        lines.append(
            f"Total missing station-days: **{missing_station_days}** "
            f"({len(partial_names)} stations below {EXPECTED_DAYS} days)."
        )
    else:
        lines.append(f"All {len(regtemp_days)} stations have {EXPECTED_DAYS} days.")
    lines.append("")
    lines.append("## Region station resolution (via catalogue NRO)")
    lines.append("")
    lines.append(
        f"Region stations from `results/stations/ghcn_vs_smn.csv`: "
        f"**{region_ok} resolved**, **{region_partial} partial**, **{region_bad} unresolved** "
        f"of {len(region)}."
    )
    lines.append("")
    lines.append("| Location | NRO | Catalogue name | regtemp name | Days | Status |")
    lines.append("|---|---|---|---|---|---|")
    for r in region_resolved:
        lines.append(
            f"| {r['location']} | {r['smn_nro']} | {r['catalogue_name']} | "
            f"{r['regtemp_name']} | {r['days']} | {r['status']} |"
        )
    lines.append("")
    lines.append("## Wiring status")
    lines.append("")
    lines.append(
        "**Not wired.** This table is a prerequisite for the future regtemp backfill "
        "(T22). Capture and name reconciliation do not imply ingest."
    )
    lines.append("")
    lines.append("Full per-name table: [`regtemp_names.csv`](regtemp_names.csv).")
    lines.append("Region resolution: [`region_resolution.csv`](region_resolution.csv).")
    lines.append("")

    md_path = args.out_dir / "regtemp_names.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"wrote {csv_path}")
    print(f"wrote {region_path}")
    print(f"wrote {md_path}")
    print(
        f"summary: {len(regtemp_days)} names, {total_rows} rows, "
        f"{status_counts.get('exact', 0)} exact, "
        f"{status_counts.get('fuzzy', 0)} fuzzy, "
        f"{status_counts.get('none', 0)} none; "
        f"region {region_ok}/{len(region)} resolved"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
