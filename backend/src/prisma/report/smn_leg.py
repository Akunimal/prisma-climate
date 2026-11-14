"""SMN leg of the source-discrepancy report (T22 regtemp wiring).

Loads the gitignored regtemp 365-day temperature capture in place under
``data/smn_probe/regtemp/`` as a data dependency of
``python -m prisma.report.discrepancies``, resolves every configured region
station to its regtemp name through the SMN catalogue NRO (GHCN id → candidate
NRO → catalogue name → regtemp name), and produces the same bias/correlation
comparison the report already applies to ERA5 vs GHCN-Daily.

All three sources store ``day_convention: local_calendar``, so the join is on
the same local calendar day. Missing station-days — capture-window gaps and
blank ``TMAX``/``TMIN`` fields — are reported as gaps and never filled.

The capture is never committed and is not ingested by the SMN connector: it is
read only for this report leg. Values are taken as served (no QC pass); the
flags below are discrepancy diagnostics, not skill metrics (15-issue-date gate
in ``docs/EVALUATION_PROTOCOL.md``).
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingest.base import find_repo_root
from ..ingest.smn import candidate_nros

EXPECTED_CAPTURE_DAYS = 365
FUZZY_CUTOFF = 0.85

# Fixed windows in a regtemp data line (header: FECHA TMAX TMIN NOMBRE).
_FECHA_SLICE = slice(0, 8)
_TMAX_SLICE = slice(10, 15)
_TMIN_SLICE = slice(16, 21)
_NOMBRE_SLICE = slice(21, None)


def parse_regtemp(path: Path) -> pd.DataFrame:
    """Parse the regtemp fixed-width capture file (latin-1 as served by SMN)."""
    return parse_regtemp_text(path.read_text(encoding="latin-1"))


def parse_regtemp_text(text: str) -> pd.DataFrame:
    """Parse regtemp payload text into one row per station-day.

    Columns: ``regtemp_name``, ``time`` (local calendar date), ``t2m_max``,
    ``t2m_min`` (``NaN`` when the field is blank). Header, separator and short
    lines are skipped by the FECHA digit check.
    """
    records: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.rstrip("\n\r")
        if len(line) < 22:
            continue
        fecha = line[_FECHA_SLICE]
        if not (fecha.isdigit() and len(fecha) == 8):
            continue
        nombre = line[_NOMBRE_SLICE].strip()
        if not nombre:
            continue
        tmax_text = line[_TMAX_SLICE].strip()
        tmin_text = line[_TMIN_SLICE].strip()
        records.append(
            {
                "regtemp_name": nombre,
                "time": pd.to_datetime(fecha, format="%d%m%Y"),
                "t2m_max": float(tmax_text) if tmax_text else float("nan"),
                "t2m_min": float(tmin_text) if tmin_text else float("nan"),
            }
        )
    if not records:
        raise ValueError("no regtemp data rows parsed from payload text")
    return pd.DataFrame.from_records(records)


def load_capture_manifest(path: Path) -> dict[str, Any]:
    """Return the capture manifest next to the regtemp file, or ``{}``."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_catalogue_nro_names(path: Path) -> dict[str, str]:
    """Map catalogue NRO → station name, joining 30-char name-wrap fragments.

    Name = chars 0-30, NRO = chars 110-115. Lines without an NRO segment are
    name-wrap fragments of the previous station and are appended to its name
    (same rule as ``scripts/reconcile_regtemp_names.py``).
    """
    by_nro: dict[str, str] = {}
    last_nro: str | None = None
    with path.open(encoding="latin-1") as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            if not line.strip():
                continue
            nro = line[110:115].strip() if len(line) > 115 else ""
            name = line[0:30].strip()
            if nro.isdigit():
                by_nro[nro] = name
                last_nro = nro
            elif last_nro is not None and name:
                by_nro[last_nro] = by_nro[last_nro] + name
    return by_nro


def resolve_region_stations(
    region: dict[str, Any],
    catalogue_by_nro: dict[str, str],
    regtemp_names: set[str],
) -> pd.DataFrame:
    """Resolve each region station: GHCN id → NRO → catalogue name → regtemp.

    Exact catalogue-name match first, then difflib fuzzy against regtemp names
    (cutoff ``FUZZY_CUTOFF``). One row per configured station.
    """
    sorted_regtemp = sorted(regtemp_names)
    records: list[dict[str, Any]] = []
    for station in region["stations"]:
        nro_found: str | None = None
        catalogue_name = ""
        for candidate in candidate_nros(station.get("ghcn_id")):
            hit = catalogue_by_nro.get(str(candidate))
            if hit is not None:
                nro_found = str(candidate)
                catalogue_name = hit
                break
        if nro_found is None:
            records.append(
                {
                    "location": station["name"],
                    "ghcn_id": station.get("ghcn_id"),
                    "smn_nro": "",
                    "catalogue_name": "",
                    "regtemp_name": "",
                    "match_status": "catalogue_nro_missing",
                }
            )
            continue
        if catalogue_name in regtemp_names:
            regtemp_name = catalogue_name
            status = "resolved"
        else:
            close = difflib.get_close_matches(
                catalogue_name, sorted_regtemp, n=1, cutoff=FUZZY_CUTOFF
            )
            if close:
                regtemp_name = close[0]
                status = "resolved_fuzzy"
            else:
                regtemp_name = ""
                status = "not_in_regtemp"
        records.append(
            {
                "location": station["name"],
                "ghcn_id": station.get("ghcn_id"),
                "smn_nro": nro_found,
                "catalogue_name": catalogue_name,
                "regtemp_name": regtemp_name,
                "match_status": status,
            }
        )
    return pd.DataFrame.from_records(records)


def build_smn_frame(
    regtemp: pd.DataFrame,
    resolution: pd.DataFrame,
) -> pd.DataFrame:
    """Normalized long frame for ``compare()``: one row per present value.

    Only non-blank ``TMAX``/``TMIN`` fields emit a row, so a missing value is
    an absent gap — never a synthetic fill. ``location`` is the region station
    name so the join against ERA5/GHCN keys on the same identifier.
    """
    name_to_location = {
        row.regtemp_name: row.location
        for row in resolution.itertuples(index=False)
        if str(row.match_status).startswith("resolved") and row.regtemp_name
    }
    empty = pd.DataFrame(
        columns=[
            "location",
            "variable",
            "time",
            "value",
            "quality_flag",
            "source",
            "unit",
            "day_convention",
        ]
    )
    if not name_to_location:
        return empty
    scoped = regtemp.loc[regtemp["regtemp_name"].isin(name_to_location)]
    records: list[dict[str, Any]] = []
    for row in scoped.itertuples(index=False):
        location = name_to_location[row.regtemp_name]
        for variable, value in (
            ("t2m_max", row.t2m_max),
            ("t2m_min", row.t2m_min),
        ):
            if value != value:  # NaN: blank field → gap, not a row
                continue
            records.append(
                {
                    "location": location,
                    "variable": variable,
                    "time": row.time,
                    "value": float(value),
                    "quality_flag": "ok",
                    "source": "smn-regtemp",
                    "unit": "degC",
                    "day_convention": "local_calendar",
                }
            )
    if not records:
        return empty
    return pd.DataFrame.from_records(records)


def coverage_table(
    regtemp: pd.DataFrame,
    resolution: pd.DataFrame,
    *,
    expected_days: int = EXPECTED_CAPTURE_DAYS,
) -> pd.DataFrame:
    """Per-region-station row-day and value coverage; gaps are not filled."""
    records: list[dict[str, Any]] = []
    for row in resolution.itertuples(index=False):
        if not row.regtemp_name or not str(row.match_status).startswith("resolved"):
            records.append(
                {
                    "location": row.location,
                    "smn_nro": row.smn_nro,
                    "regtemp_name": row.regtemp_name,
                    "match_status": row.match_status,
                    "row_days": 0,
                    "expected_days": expected_days,
                    "missing_row_days": expected_days,
                    "t2m_max_values": 0,
                    "t2m_min_values": 0,
                    "blank_tmax_days": 0,
                    "blank_tmin_days": 0,
                    "status": "unresolved",
                }
            )
            continue
        days = regtemp.loc[regtemp["regtemp_name"] == row.regtemp_name]
        row_days = int(len(days))
        t2m_max_values = int(days["t2m_max"].notna().sum())
        t2m_min_values = int(days["t2m_min"].notna().sum())
        blank_tmax = row_days - t2m_max_values
        blank_tmin = row_days - t2m_min_values
        missing = max(0, expected_days - row_days)
        status = "full" if missing == 0 and blank_tmax == 0 and blank_tmin == 0 else "gaps"
        records.append(
            {
                "location": row.location,
                "smn_nro": row.smn_nro,
                "regtemp_name": row.regtemp_name,
                "match_status": row.match_status,
                "row_days": row_days,
                "expected_days": expected_days,
                "missing_row_days": missing,
                "t2m_max_values": t2m_max_values,
                "t2m_min_values": t2m_min_values,
                "blank_tmax_days": blank_tmax,
                "blank_tmin_days": blank_tmin,
                "status": status,
            }
        )
    return pd.DataFrame.from_records(records)


def capture_gap_rows(
    regtemp: pd.DataFrame,
    *,
    expected_days: int = EXPECTED_CAPTURE_DAYS,
) -> list[dict[str, Any]]:
    """Capture-level partial stations (every NOMBRE, not only region ones)."""
    rows: list[dict[str, Any]] = []
    for name, group in regtemp.groupby("regtemp_name", sort=True):
        present = int(len(group))
        if present < expected_days:
            rows.append(
                {
                    "regtemp_name": name,
                    "row_days": present,
                    "missing_row_days": expected_days - present,
                }
            )
    return rows


def overlap_period(
    left: pd.DataFrame,
    right: pd.DataFrame,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """Shared local-calendar days between two normalized frames, or None."""
    if left.empty or right.empty:
        return None
    left_days = set(pd.to_datetime(left["time"]).dt.normalize())
    right_days = set(pd.to_datetime(right["time"]).dt.normalize())
    shared = left_days & right_days
    if not shared:
        return None
    return min(shared), max(shared)


def no_overlap_note(
    smn: pd.DataFrame,
    other: pd.DataFrame,
    *,
    other_label: str,
) -> str:
    """Honest sentence when the SMN capture and another source never meet."""
    smn_days = pd.to_datetime(smn["time"]) if not smn.empty else pd.Series(dtype="datetime64[ns]")
    other_days = (
        pd.to_datetime(other["time"]) if not other.empty else pd.Series(dtype="datetime64[ns]")
    )
    if smn_days.empty or other_days.empty:
        if smn_days.empty:
            smn_part = "has no values"
        else:
            smn_part = f"{smn_days.min().date()} to {smn_days.max().date()}"
        if other_days.empty:
            other_part = "has no ok rows"
        else:
            other_part = f"ok rows end {other_days.max().date()}"
        return (
            f"No overlapping local-calendar days: SMN regtemp {smn_part}; "
            f"{other_label} {other_part}. Comparison skipped — nothing filled."
        )
    return (
        f"No overlapping local-calendar days between the SMN regtemp capture "
        f"({smn_days.min().date()} to {smn_days.max().date()}) and {other_label} "
        f"ok rows ({other_days.min().date()} to {other_days.max().date()}). "
        f"The capture window starts after the {other_label} end date, so this "
        "leg cannot compare the two sources on current data; nothing is "
        "interpolated to manufacture overlap."
    )


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


def _comparison_block(
    title: str,
    table: pd.DataFrame | None,
    no_overlap: str | None,
    source_other: str,
) -> list[str]:
    lines = ["", f"### {title}", ""]
    if no_overlap:
        lines.append(no_overlap)
        return lines
    if table is None or table.empty:
        lines.append("_No overlapping rows; comparison skipped._")
        return lines
    display = table.copy()
    for column in ("bias", "mae", "rmse", "p95_abs_diff"):
        if column in display.columns:
            display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
    for column in list(display.columns):
        if column.startswith(("mean_", "ratio_")) or column == "corr":
            display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
    lines.append(
        "Joined on (location, variable, local-calendar day), "
        f"`quality_flag == ok` only; bias = mean(smn − {source_other})."
    )
    lines.append("")
    lines.append(_markdown_table(display))
    if "flags" in display.columns:
        flagged = display.loc[display["flags"].ne("")]
    else:
        flagged = display.iloc[0:0]
    lines.append("")
    if flagged.empty:
        lines.append("No group crossed a flag threshold.")
    else:
        lines.append(f"Flagged groups ({len(flagged)}):")
        for row in flagged.itertuples(index=False):
            lines.append(f"- **{row.location} / {row.variable}**: {row.flags}")
    return lines


def render_smn_section(
    *,
    smn_vs_era5: pd.DataFrame | None,
    smn_vs_ghcn: pd.DataFrame | None,
    era5_no_overlap: str | None,
    ghcn_no_overlap: str | None,
    provenance: dict[str, Any],
    resolution: pd.DataFrame,
    coverage: pd.DataFrame,
    capture_gaps: list[dict[str, Any]],
    regtemp_path: Path,
    era5_overlap: tuple[pd.Timestamp, pd.Timestamp] | None,
) -> str:
    """Markdown section for the SMN regtemp leg (provenance + comparisons)."""
    from .discrepancies import CORRELATION_FLAG, TEMP_BIAS_FLAG_C

    resolved = int(resolution["match_status"].str.startswith("resolved").sum())
    total = len(resolution)
    window = provenance.get("served_window_local") or {}
    window_first = window.get("first", "unknown")
    window_last = window.get("last", "unknown")
    try:
        capture_display = regtemp_path.resolve().relative_to(find_repo_root()).as_posix()
    except ValueError:
        capture_display = regtemp_path.as_posix()

    lines = [
        "",
        "## SMN leg — regtemp capture vs ERA5 and GHCN-Daily",
        "",
        "**Comparison convention:** ERA5, GHCN-Daily and the SMN regtemp capture "
        "all store `day_convention: local_calendar`, so every join below is on "
        "the same local calendar day (no UTC conversion, no mixed conventions).",
        "",
        "**Diagnostic, not skill:** the bias/correlation flags here are "
        "cross-source discrepancy diagnostics with the same thresholds as the "
        f"ERA5–GHCN leg (|bias| >= {TEMP_BIAS_FLAG_C:g} °C or corr < "
        f"{CORRELATION_FLAG:g} for temperature). They are **not** forecast skill "
        "metrics: no CRPS, Brier, reliability or leaderboard number is computed "
        "or published before the 15-issue-date gate "
        "(`docs/EVALUATION_PROTOCOL.md`).",
        "",
        "### Capture provenance (regtemp)",
        "",
        f"- File: `{capture_display}` (gitignored; read in place, never "
        "committed, never used as an Actions artifact)",
        f"- Retrieved at: {provenance.get('retrieved_at', 'unknown')}",
        f"- Served window (local): {window_first} → {window_last} "
        f"({window.get('distinct_days', 'unknown')} distinct days)",
        f"- Data rows in file: {provenance.get('data_rows', 'unknown')}",
        f"- sha256 (txt): `{provenance.get('sha256_txt', 'unknown')}`",
        f"- Endpoint: {provenance.get('endpoint', 'unknown')}",
        "- Day-convention evidence: "
        f"{provenance.get('day_convention_evidence', 'FECHA is a local calendar date')}",
        "- Role: data dependency of `python -m prisma.report.discrepancies` only; "
        "**not** ingested into `data/raw/smn-argentina.parquet` by the connector. "
        "Values are taken as served — no QC pass is applied in this leg.",
        "",
        "### Station identity (catalogue NRO)",
        "",
        "Region stations resolved GHCN id → SMN NRO → catalogue name → regtemp "
        f"name: **{resolved}/{total}** "
        f"({int((resolution['match_status'] == 'resolved').sum())} exact, "
        f"{int((resolution['match_status'] == 'resolved_fuzzy').sum())} fuzzy).",
        "",
        _markdown_table(resolution),
        "",
        "### Coverage gaps (reported, never filled)",
        "",
        "A blank `TMAX`/`TMIN` field or an absent station-day is a gap: this leg "
        "emits no row for it and never interpolates or carries values forward.",
        "",
    ]

    if capture_gaps:
        total_missing = sum(int(g["missing_row_days"]) for g in capture_gaps)
        lines.append(
            f"- Capture-level partial stations: **{len(capture_gaps)}** with "
            f"**{total_missing}** missing station-days against the "
            f"{EXPECTED_CAPTURE_DAYS}-day window "
            "(not filled; these are mostly non-region catalogue stations)."
        )
        for gap in capture_gaps:
            lines.append(
                f"  - {gap['regtemp_name']}: {gap['row_days']}/"
                f"{EXPECTED_CAPTURE_DAYS} days "
                f"({gap['missing_row_days']} missing)"
            )
    else:
        lines.append(
            f"- Capture-level: every station in the file has all "
            f"{EXPECTED_CAPTURE_DAYS} row-days."
        )

    if not coverage.empty:
        region_missing = int(coverage["missing_row_days"].sum())
        region_blank_max = int(coverage["blank_tmax_days"].sum())
        region_blank_min = int(coverage["blank_tmin_days"].sum())
        lines.append(
            f"- Region stations ({total} configured): **{region_missing}** missing "
            f"row-days; blank fields on present days: **{region_blank_max}** "
            f"`TMAX`, **{region_blank_min}** `TMIN` "
            "(each blank omits that variable's row from the join)."
        )
        lines.append("")
        lines.append(_markdown_table(coverage))

    if era5_overlap is not None:
        lines += [
            "",
            f"- SMN–ERA5 overlapping period: {era5_overlap[0].date()} to "
            f"{era5_overlap[1].date()} (local calendar).",
        ]

    lines += _comparison_block(
        "SMN vs ERA5",
        smn_vs_era5,
        era5_no_overlap,
        "era5",
    )
    lines += _comparison_block(
        "SMN vs GHCN-Daily",
        smn_vs_ghcn,
        ghcn_no_overlap,
        "ghcn",
    )

    lines += [
        "",
        "### What this leg does not show",
        "",
        "- The connector's live series (`data/raw/smn-argentina.parquet`, "
        "accumulating forward from the first run) is **not** merged into this "
        "comparison; only the regtemp capture is.",
        "- regtemp has no precipitation field — this leg is temperature only.",
        "- A flag is a prompt to investigate, not proof of an error in either "
        "source.",
        "",
    ]
    return "\n".join(lines)
