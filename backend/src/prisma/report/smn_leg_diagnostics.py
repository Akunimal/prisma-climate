"""SMN-leg diagnostics table (T26a step 1.0b), always produced by script.

Reads the repo's own data dependencies — normalized ERA5 Parquet, the
gitignored regtemp capture, the SMN catalogue and the region config — and
writes ``results/discrepancies/smn_leg_diagnostics.{csv,md}``: one row per
region station with the identity chain (GHCN id → NRO → catalogue → regtemp),
regtemp coverage, and paired-day means over exactly the same local-calendar
dates for ``t2m_max`` and ``t2m_min``. The bias sign is normalized to
**ERA5 − SMN** on both variables (the committed ``smn_vs_era5.csv`` stores
SMN − ERA5; this table is the sign-correct reading).

Flags here are discrepancy diagnostics only (``n_days < 300``, a calendar
month with zero paired days, fuzzy/unresolved identity, no ERA5 pairing, and
a capture-wide ``mean(TMAX) <= mean(TMIN) + 3 °C`` mean inversion on either
source — the sign of a parse or variable swap; individual low diurnal-range
days are normal weather and stay a plain column) — never forecast-skill
numbers: no CRPS, Brier or reliability value is computed before the
15-issue-date gate in ``docs/EVALUATION_PROTOCOL.md``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingest.base import find_repo_root, load_region, utc_now
from .smn_leg import (
    build_smn_frame,
    load_capture_manifest,
    parse_catalogue_nro_names,
    parse_regtemp,
    resolve_region_stations,
)

MIN_PAIR_DAYS = 300
TMAX_TMIN_MARGIN_C = 3.0
MONTH_COLUMNS = [f"m{month:02d}" for month in range(1, 13)]

BA_LOCATION = "Buenos Aires Observatorio"
BA_RAW_SPOT_CHECK_LINES = 10


def _ok_values(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    rows = frame.loc[
        frame["quality_flag"].eq("ok"),
        ["location", "variable", "time", "value"],
    ].copy()
    rows["time"] = pd.to_datetime(rows["time"]).dt.normalize()
    return rows.rename(columns={"value": value_name})


def pair_sources(
    smn_frame: pd.DataFrame,
    era5: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join SMN and ERA5 ok rows on (location, variable, local day)."""
    left = _ok_values(smn_frame, "smn")
    right = _ok_values(era5, "era5")
    return left.merge(right, on=["location", "variable", "time"], how="inner")


def _correlation(group: pd.DataFrame) -> float | None:
    if len(group) <= 2:
        return None
    corr = group["smn"].corr(group["era5"])
    return float(corr) if corr == corr else None


def build_diagnostics(
    era5: pd.DataFrame,
    regtemp: pd.DataFrame,
    resolution: pd.DataFrame,
) -> pd.DataFrame:
    """One diagnostics row per configured station (identity + pairing + flags)."""
    paired = pair_sources(build_smn_frame(regtemp, resolution), era5)
    records: list[dict[str, Any]] = []

    for row in resolution.itertuples(index=False):
        resolved = str(row.match_status).startswith("resolved") and row.regtemp_name
        days = (
            regtemp.loc[regtemp["regtemp_name"] == row.regtemp_name]
            if resolved
            else regtemp.iloc[0:0]
        )
        record: dict[str, Any] = {
            "location": row.location,
            "ghcn_id": row.ghcn_id,
            "smn_nro": row.smn_nro,
            "catalogue_name": row.catalogue_name,
            "regtemp_name": row.regtemp_name,
            "match_status": row.match_status,
            "regtemp_row_days": int(len(days)),
            "blank_tmax_days": int(days["t2m_max"].isna().sum()) if len(days) else 0,
            "blank_tmin_days": int(days["t2m_min"].isna().sum()) if len(days) else 0,
            "regtemp_first": str(days["time"].min().date()) if len(days) else "",
            "regtemp_last": str(days["time"].max().date()) if len(days) else "",
        }

        flags: list[str] = []
        if row.match_status == "resolved_fuzzy":
            flags.append("fuzzy_match")
        elif not resolved:
            flags.append("unresolved_identity")

        station_pairs = paired.loc[paired["location"].eq(row.location)]
        max_pairs = station_pairs.loc[station_pairs["variable"].eq("t2m_max")].sort_values(
            "time"
        )
        min_pairs = station_pairs.loc[station_pairs["variable"].eq("t2m_min")].sort_values(
            "time"
        )

        record["paired_n_max"] = int(len(max_pairs))
        record["paired_n_min"] = int(len(min_pairs))
        record["paired_first"] = (
            str(max_pairs["time"].iloc[0].date()) if len(max_pairs) else ""
        )
        record["paired_last"] = str(max_pairs["time"].iloc[-1].date()) if len(max_pairs) else ""

        month_counts = (
            max_pairs["time"].dt.month.value_counts().reindex(range(1, 13), fill_value=0)
            if len(max_pairs)
            else pd.Series(0, index=range(1, 13))
        )
        for month in range(1, 13):
            record[f"m{month:02d}"] = int(month_counts.loc[month])
        if len(max_pairs) and (month_counts == 0).any():
            zero_months = ", ".join(
                f"{month:02d}" for month in range(1, 13) if month_counts.loc[month] == 0
            )
            flags.append(f"month_zero:{zero_months}")
        if resolved and len(max_pairs) < MIN_PAIR_DAYS:
            flags.append(f"n_days_t2m_max<{MIN_PAIR_DAYS}")

        for variable, pairs in (("t2m_max", max_pairs), ("t2m_min", min_pairs)):
            if len(pairs):
                record[f"mean_smn_{variable}"] = float(pairs["smn"].mean())
                record[f"mean_era5_{variable}"] = float(pairs["era5"].mean())
                # Sign normalized here: positive = ERA5 warmer than SMN.
                record[f"bias_era5_minus_smn_{variable}"] = float(
                    (pairs["era5"] - pairs["smn"]).mean()
                )
                record[f"corr_{variable}"] = _correlation(pairs)
            else:
                record[f"mean_smn_{variable}"] = float("nan")
                record[f"mean_era5_{variable}"] = float("nan")
                record[f"bias_era5_minus_smn_{variable}"] = float("nan")
                record[f"corr_{variable}"] = float("nan")
        if resolved and not len(station_pairs):
            flags.append("no_era5_paired_days")

        if len(days):
            both = days.dropna(subset=["t2m_max", "t2m_min"])
            violations = int((both["t2m_max"] <= both["t2m_min"] + TMAX_TMIN_MARGIN_C).sum())
            # Structural check: a capture-wide mean inversion means a parse or
            # variable swap; individual low-range days are normal weather, so
            # the daily count stays a column, never a flag on its own.
            if len(both) and both["t2m_max"].mean() <= both["t2m_min"].mean() + TMAX_TMIN_MARGIN_C:
                flags.append(f"smn_mean_tmax<=tmin+{TMAX_TMIN_MARGIN_C:g}C")
        else:
            violations = 0
        era5_both = era5.loc[
            era5["quality_flag"].eq("ok") & era5["location"].eq(row.location)
        ]
        era5_wide = era5_both.pivot_table(
            index="time", columns="variable", values="value", aggfunc="last"
        )
        if {"t2m_max", "t2m_min"}.issubset(era5_wide.columns):
            era5_wide = era5_wide.dropna(subset=["t2m_max", "t2m_min"])
            if (
                len(era5_wide)
                and era5_wide["t2m_max"].mean()
                <= era5_wide["t2m_min"].mean() + TMAX_TMIN_MARGIN_C
            ):
                flags.append(f"era5_mean_tmax<=tmin+{TMAX_TMIN_MARGIN_C:g}C")
        record["smn_tmax_le_tmin_plus3_days"] = violations

        record["flags"] = "; ".join(flags)
        records.append(record)

    frame = pd.DataFrame.from_records(records)
    front = [
        "location",
        "ghcn_id",
        "smn_nro",
        "catalogue_name",
        "regtemp_name",
        "match_status",
    ]
    month_and_rest = [column for column in frame.columns if column not in front]
    return frame[front + month_and_rest]


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    if isinstance(value, (int,)):
        return str(value)
    return f"{float(value):.{digits}f}"


def _display_table(frame: pd.DataFrame) -> pd.DataFrame:
    """Rounded projection of the full table for the Markdown report."""
    columns = [
        "location",
        "match_status",
        "regtemp_row_days",
        "blank_tmax_days",
        "blank_tmin_days",
        "paired_n_max",
        "paired_first",
        "paired_last",
        "mean_smn_t2m_max",
        "mean_era5_t2m_max",
        "bias_era5_minus_smn_t2m_max",
        "mean_smn_t2m_min",
        "mean_era5_t2m_min",
        "bias_era5_minus_smn_t2m_min",
        "smn_tmax_le_tmin_plus3_days",
        "flags",
    ]
    display = frame[columns].copy()
    for column in columns:
        if column.startswith(("mean_", "bias_")):
            display[column] = pd.to_numeric(display[column], errors="coerce").map(
                lambda value: _fmt(value)
            )
    return display


def _month_line(row: pd.Series) -> str:
    counts = " ".join(f"{month:02d}:{int(row[f'm{month:02d}'])}" for month in range(1, 13))
    paired = int(row["paired_n_max"])
    if paired:
        winter = int(row["m06"]) + int(row["m07"]) + int(row["m08"])
        share = winter / paired
        winter_note = (
            f" Jun–Aug = {winter} days ({share:.1%} of paired days; a uniform "
            "calendar would be 25 %)."
        )
    else:
        winter_note = ""
    return f"Paired t2m_max days per calendar month (MM:count): {counts}.{winter_note}"


def _raw_spot_check(regtemp_path: Path, regtemp_name: str) -> list[str]:
    """First raw regtemp lines for one station with the parser's fixed slices."""
    from .smn_leg import _FECHA_SLICE, _NOMBRE_SLICE, _TMAX_SLICE, _TMIN_SLICE

    lines: list[str] = []
    picked = 0
    with regtemp_path.open(encoding="latin-1") as handle:
        for raw in handle:
            line = raw.rstrip("\n\r")
            if len(line) < 22:
                continue
            if line[_NOMBRE_SLICE].strip() != regtemp_name:
                continue
            fecha = line[_FECHA_SLICE]
            if not (fecha.isdigit() and len(fecha) == 8):
                continue
            picked += 1
            if picked > BA_RAW_SPOT_CHECK_LINES:
                break
            lines.append(
                f"- raw `{line[:40].rstrip()}` → FECHA=`{fecha}` "
                f"(DDMMYYYY → {pd.to_datetime(fecha, format='%d%m%Y').date()}), "
                f"TMAX=`{line[_TMAX_SLICE].strip()}`, "
                f"TMIN=`{line[_TMIN_SLICE].strip()}`, "
                f"NOMBRE=`{line[_NOMBRE_SLICE].strip()}`"
            )
    return lines


def _date_parse_audit(regtemp: pd.DataFrame, regtemp_name: str) -> list[str]:
    days = regtemp.loc[regtemp["regtemp_name"] == regtemp_name].sort_values("time")
    distinct = int(days["time"].nunique())
    rows = int(len(days))
    return [
        f"- Parsed rows: {rows}; distinct local-calendar dates: {distinct} "
        f"({'no duplicate dates' if distinct == rows else 'DUPLICATE DATES PRESENT'}).",
        f"- Date range: {days['time'].min().date()} to {days['time'].max().date()} "
        "(parsed with format `%d%m%Y`; a DD/MM vs MM/DD swap would raise on "
        "day > 12 and abort `parse_regtemp`, so every stored row validated as "
        "DDMMYYYY).",
    ]


def render_diagnostics_markdown(
    table: pd.DataFrame,
    *,
    regtemp: pd.DataFrame,
    regtemp_path: Path,
    provenance: dict[str, Any],
    generated_at: pd.Timestamp,
) -> str:
    flagged = table.loc[table["flags"].ne("")]
    lines = [
        "# SMN-leg diagnostics — 19-station pairing table",
        "",
        f"Generated by `python -m prisma.report.smn_leg_diagnostics` on "
        f"{generated_at} (UTC).",
        "",
        "- **Sign convention:** every bias here is **ERA5 − SMN** "
        "(positive = ERA5 warmer than the station). The committed "
        "`smn_vs_era5.csv` stores SMN − ERA5; flip the sign before comparing.",
        "- Means are taken over **exactly the same paired local-calendar days** "
        "per row (`paired_first` → `paired_last`); missing days are never filled.",
        f"- Flags are diagnostics, not skill: `n_days_t2m_max < {MIN_PAIR_DAYS}`, "
        "a calendar month with zero paired days, fuzzy/unresolved identity, "
        "no ERA5 pairing, and a capture-wide "
        f"`mean(TMAX) <= mean(TMIN) + {TMAX_TMIN_MARGIN_C:g} °C` mean inversion "
        "(the signature of a parse/variable swap — individual low "
        "diurnal-range days are normal weather and are counted only in the "
        "`smn_tmax_le_tmin_plus3_days` column). "
        "No CRPS/Brier/reliability number exists before the 15-issue-date gate "
        "(`docs/EVALUATION_PROTOCOL.md`).",
        f"- Capture: `{regtemp_path.name}`, retrieved "
        f"{provenance.get('retrieved_at', 'unknown')}, window "
        f"{(provenance.get('served_window_local') or {}).get('first', '?')} → "
        f"{(provenance.get('served_window_local') or {}).get('last', '?')} "
        f"(gitignored data dependency; never an Actions artifact).",
        "",
        "## Per-station table (full precision in the CSV)",
        "",
    ]
    lines.append(_md_table(_display_table(table)))
    lines += ["", "## Flagged rows", ""]
    if flagged.empty:
        lines.append("No station crossed a diagnostic flag.")
    else:
        for row in flagged.itertuples(index=False):
            lines.append(f"- **{row.location}**: {row.flags}")

    ba = table.loc[table["location"].eq(BA_LOCATION)]
    if not ba.empty:
        row = ba.iloc[0]
        regtemp_name = str(row["regtemp_name"])
        lines += [
            "",
            f"## {BA_LOCATION} — raw-line and pairing spot check",
            "",
            "### (a) Paired-day calendar distribution",
            "",
            _month_line(row),
            "",
            "### (b) t2m_max vs t2m_min means over the same paired days",
            "",
            "| variable | mean SMN | mean ERA5 | bias (ERA5 − SMN) | corr |",
            "| --- | --- | --- | --- | --- |",
            "| t2m_max | "
            f"{_fmt(row['mean_smn_t2m_max'])} | {_fmt(row['mean_era5_t2m_max'])} | "
            f"{_fmt(row['bias_era5_minus_smn_t2m_max'])} | "
            f"{_fmt(row['corr_t2m_max'])} |",
            "| t2m_min | "
            f"{_fmt(row['mean_smn_t2m_min'])} | {_fmt(row['mean_era5_t2m_min'])} | "
            f"{_fmt(row['bias_era5_minus_smn_t2m_min'])} | "
            f"{_fmt(row['corr_t2m_min'])} |",
            "",
            "Both variables are reported side by side so a value cited as "
            "“the station mean” can be attributed to the row it actually "
            "comes from.",
            "",
            "### (c) Identity chain",
            "",
            f"- GHCN id `{row['ghcn_id']}` → SMN NRO `{row['smn_nro']}` → "
            f"catalogue `{row['catalogue_name']}` → regtemp `{regtemp_name}` "
            f"(match: **{row['match_status']}**).",
            f"- regtemp rows: {int(row['regtemp_row_days'])} "
            f"({row['regtemp_first']} → {row['regtemp_last']}); "
            f"blank TMAX {int(row['blank_tmax_days'])}, "
            f"blank TMIN {int(row['blank_tmin_days'])}.",
            "",
            "### (d) Raw-line parse (first "
            f"{BA_RAW_SPOT_CHECK_LINES} lines, fixed-width slices)",
            "",
        ]
        lines += _raw_spot_check(regtemp_path, regtemp_name) or ["- (no raw lines found)"]
        lines += ["", "Parsed-frame audit:", ""]
        lines += _date_parse_audit(regtemp, regtemp_name)

    lines += [
        "",
        "## What this does not show",
        "",
        "- No forecast is involved: this is a two-source observation comparison, "
        "not verification (Phase 1, 15-issue-date gate).",
        "- The SMN leg covers only the regtemp capture window; the GHCN leg "
        "covers a different, earlier period — see the confounder note in the "
        "discrepancy report before comparing flags across legs.",
        "- A flag is a prompt to investigate, not proof of an error in either "
        "source.",
        "",
    ]
    return "\n".join(lines)


def _md_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = ["" if pd.isna(value) or value is None else str(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    parser = argparse.ArgumentParser(prog="python -m prisma.report.smn_leg_diagnostics")
    parser.add_argument(
        "--era5",
        type=Path,
        default=root / "data" / "raw" / "openmeteo-era5.parquet",
    )
    parser.add_argument(
        "--regtemp",
        type=Path,
        default=root / "data" / "smn_probe" / "regtemp" / "registro_temperatura365d_smn.txt",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "results" / "discrepancies",
    )
    parser.add_argument("--region", default="argentina")
    args = parser.parse_args(argv)

    era5 = pd.read_parquet(args.era5)
    era5["time"] = pd.to_datetime(era5["time"])
    regtemp = parse_regtemp(args.regtemp)
    provenance = load_capture_manifest(args.regtemp.with_name("manifest.json"))

    region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
    catalogue_path = root / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
    catalogue_by_nro = (
        parse_catalogue_nro_names(catalogue_path) if catalogue_path.exists() else {}
    )
    regtemp_names = set(regtemp["regtemp_name"])
    resolution = resolve_region_stations(region, catalogue_by_nro, regtemp_names)

    table = build_diagnostics(era5, regtemp, resolution)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = args.out_dir / "smn_leg_diagnostics.csv"
    md_path = args.out_dir / "smn_leg_diagnostics.md"
    table.to_csv(csv_path, index=False)
    md_path.write_text(
        render_diagnostics_markdown(
            table,
            regtemp=regtemp,
            regtemp_path=args.regtemp,
            provenance=provenance,
            generated_at=utc_now(),
        ),
        encoding="utf-8",
    )
    resolved_n = int(table["match_status"].str.startswith("resolved").sum())
    flagged_n = int(table["flags"].ne("").sum())
    print(
        f"{len(table)} stations ({resolved_n} resolved), {flagged_n} flagged -> "
        f"{csv_path.relative_to(root)}"
    )
    print(f"report -> {md_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
