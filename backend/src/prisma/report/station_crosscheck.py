"""Cross-match configured region stations against the SMN station catalogue.

Matches each station in configs/regions/*.yaml to data/smn_probe/estaciones/
estaciones_smn.txt by SMN NRO (any 5-digit window of the GHCN id, rightmost
first — the ids pad the WMO number inconsistently), falling back to the
nearest catalogue entry by coordinates. Flags coordinate offsets above
0.05° and elevation offsets above 50 m so station metadata can be checked
before any residual difference is attributed to a gridded source.

Produced only by this script; output lands under results/stations/.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingest.base import find_repo_root, load_region, utc_now

LAT_FLAG_DEG = 0.05
ELEV_FLAG_M = 50

# Numeric tail of a data row: lat gr/min, lon gr/min, elevation, NRO, OACI.
# Anchored at the end so rows whose name and province run together with a
# single space (two rows in the real file) still parse.
_TAIL_RE = re.compile(
    r"(?P<lat_gr>-?\d+)\s+(?P<lat_min>\d+)\s+"
    r"(?P<lon_gr>-?\d+)\s+(?P<lon_min>\d+)\s+"
    r"(?P<elev>-?\d+)\s+(?P<nro>\d+)(?:\s+(?P<oaci>\S+))?\s*$"
)


def parse_smn_estaciones(path: Path) -> pd.DataFrame:
    """Parse estaciones_smn.txt (aligned columns, two-or-more-space heads).

    In the real file NRO and OACI are separated by a single space, and two
    station rows carry only one space between name and province, so the
    numeric tail is matched from the end of the line instead of by a fixed
    split. Orphan fragment lines (``ERO``, ``RO``) never match and are
    skipped.
    """
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        match = _TAIL_RE.search(line)
        if match is None:
            continue  # header / units / orphan fragment lines
        head_parts = re.split(r"\s{2,}", line[: match.start()].strip())
        lat = (1 if int(match["lat_gr"]) >= 0 else -1) * (
            abs(int(match["lat_gr"])) + int(match["lat_min"]) / 60.0
        )
        lon = (1 if int(match["lon_gr"]) >= 0 else -1) * (
            abs(int(match["lon_gr"])) + int(match["lon_min"]) / 60.0
        )
        records.append(
            {
                "smn_name": head_parts[0] if head_parts else "",
                "smn_province": head_parts[1] if len(head_parts) > 1 else "",
                "smn_lat": lat,
                "smn_lon": lon,
                "smn_elevation_m": float(match["elev"]),
                "smn_nro": int(match["nro"]),
            }
        )
    if not records:
        raise ValueError(f"no stations parsed from {path}")
    return pd.DataFrame.from_records(records)


def _nearest(lat: float, lon: float, catalogue: pd.DataFrame) -> pd.Series:
    distance = (catalogue["smn_lat"] - lat).abs() + (catalogue["smn_lon"] - lon).abs()
    return catalogue.loc[distance.idxmin()]


def _candidate_nros(ghcn_id: Any) -> list[int]:
    """All 5-digit windows of a GHCN id, rightmost first.

    GHCN-Daily ids pad the WMO station number inconsistently
    (``ARM00087938`` → 87938 but ``AR000870470`` → 87047, not 70470), so
    every window is tried until one exists in the SMN catalogue.
    """
    digits = re.sub(r"\D", "", str(ghcn_id or ""))
    return [int(digits[i : i + 5]) for i in range(len(digits) - 4, -1, -1)]


def crosscheck_region(
    region: dict[str, Any],
    catalogue: pd.DataFrame,
) -> pd.DataFrame:
    """Match every configured station; flag |Δ| > 0.05° or > 50 m."""
    records: list[dict[str, Any]] = []
    for station in region["stations"]:
        nro = next(
            (
                candidate
                for candidate in _candidate_nros(station.get("ghcn_id"))
                if (catalogue["smn_nro"] == candidate).any()
            ),
            None,
        )
        if nro is not None:
            match = catalogue.loc[catalogue["smn_nro"] == nro].iloc[0]
            matched_by = "nro"
        else:
            match = _nearest(station["lat"], station["lon"], catalogue)
            matched_by = "nearest"

        delta_lat = float(match["smn_lat"]) - float(station["lat"])
        delta_lon = float(match["smn_lon"]) - float(station["lon"])
        config_elev = station.get("elevation_m")
        delta_elev = (
            float(match["smn_elevation_m"]) - float(config_elev)
            if config_elev is not None
            else None
        )

        flags: list[str] = []
        if abs(delta_lat) > LAT_FLAG_DEG:
            flags.append(f"|Δlat|={abs(delta_lat):.3f}° > {LAT_FLAG_DEG}°")
        if abs(delta_lon) > LAT_FLAG_DEG:
            flags.append(f"|Δlon|={abs(delta_lon):.3f}° > {LAT_FLAG_DEG}°")
        if delta_elev is not None and abs(delta_elev) > ELEV_FLAG_M:
            flags.append(f"|Δelev|={abs(delta_elev):.0f} m > {ELEV_FLAG_M} m")

        records.append(
            {
                "location": station["name"],
                "ghcn_id": station.get("ghcn_id"),
                "matched_by": matched_by,
                "smn_nro": int(match["smn_nro"]),
                "smn_name": match["smn_name"],
                "config_lat": station["lat"],
                "config_lon": station["lon"],
                "smn_lat": float(match["smn_lat"]),
                "smn_lon": float(match["smn_lon"]),
                "delta_lat": delta_lat,
                "delta_lon": delta_lon,
                "config_elevation_m": config_elev,
                "smn_elevation_m": float(match["smn_elevation_m"]),
                "delta_elevation_m": delta_elev,
                "name_exact": str(station["name"]).upper() == str(match["smn_name"]).upper(),
                "flags": "; ".join(flags),
            }
        )
    return pd.DataFrame.from_records(records)


def _markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = ["" if pd.isna(value) else str(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_markdown(table: pd.DataFrame, *, generated_at: pd.Timestamp, region_id: str) -> str:
    flagged = table.loc[table["flags"].ne("")]
    matched_by = table["matched_by"].value_counts().to_dict()
    lines = [
        f"# Station cross-check — {region_id} config vs SMN catalogue",
        "",
        f"Generated by `python -m prisma.report.station_crosscheck` on {generated_at} (UTC).",
        "",
        f"- Configured stations: {len(table)}; matched by NRO: "
        f"{matched_by.get('nro', 0)}; by nearest coordinate: {matched_by.get('nearest', 0)}",
        f"- Flag thresholds: |Δlat| or |Δlon| > {LAT_FLAG_DEG}°, "
        f"|Δelev| > {ELEV_FLAG_M} m",
        "",
        "## Results",
        "",
    ]
    display = table.copy()
    for column in ("config_lat", "config_lon", "smn_lat", "smn_lon", "delta_lat", "delta_lon"):
        display[column] = pd.to_numeric(display[column], errors="coerce").round(4)
    for column in ("config_elevation_m", "smn_elevation_m", "delta_elevation_m"):
        display[column] = pd.to_numeric(display[column], errors="coerce").round(1)
    lines.append(_markdown_table(display))
    lines += ["", "## Flags", ""]
    if flagged.empty:
        lines.append(
            f"No station exceeded the {LAT_FLAG_DEG}° / {ELEV_FLAG_M} m thresholds."
        )
    else:
        for row in flagged.itertuples(index=False):
            lines.append(f"- **{row.location}** ({row.smn_name}): {row.flags}")
    lines += [
        "",
        "Name strings are compared for information only: GHCN long names and "
        "SMN short names legitimately differ (e.g. "
        "\"Tucuman (Teniente Benjamin Matienzo)\" vs \"TUCUMAN AERO\"). "
        "A flag means coordinates or elevation disagree, not that the name "
        "looks different.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    parser = argparse.ArgumentParser(prog="python -m prisma.report.station_crosscheck")
    parser.add_argument("--region", default="argentina")
    parser.add_argument(
        "--catalogue",
        type=Path,
        default=root / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt",
        help="path to the parsed SMN station list",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "results" / "stations",
        help="directory for the CSV and Markdown output",
    )
    args = parser.parse_args(argv)

    if not args.catalogue.exists():
        print(f"catalogue not found: {args.catalogue}")
        return 1

    region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
    catalogue = parse_smn_estaciones(args.catalogue)
    table = crosscheck_region(region, catalogue)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "ghcn_vs_smn.csv"
    md_path = args.out_dir / "ghcn_vs_smn.md"
    table.to_csv(csv_path, index=False)
    md_path.write_text(
        render_markdown(table, generated_at=utc_now(), region_id=region["id"]),
        encoding="utf-8",
    )
    n_flagged = int(table["flags"].ne("").sum())
    print(f"{len(table)} stations, {n_flagged} flagged -> {csv_path.relative_to(root)}")
    print(f"report -> {md_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
