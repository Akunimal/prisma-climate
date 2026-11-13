"""Frozen SMN-ERA5 climatology adjustment table (protocol amendment 2026-11-13).

The evaluation protocol (docs/EVALUATION_PROTOCOL.md, amendment 2026-11-13)
makes SMN Argentina the temperature observation reference and defines the
climatology baseline for ``t2m_max`` / ``t2m_min`` as ERA5 (``models=era5``)
at the station points over the training window, adjusted to SMN by a
per-station, per-calendar-month mean difference **(SMN − ERA5)** estimated
**only** on the regtemp capture window **2025-11-11 → 2026-11-10**.

Rules implemented here, exactly as amended:

- paired local-calendar days, both sides ``quality_flag == ok``;
- cell = (station, variable, calendar month); ``n_paired_days >= 20`` uses
  the cell mean, fewer uses that station's all-months mean difference
  (Formosa has zero paired days in September–October);
- the table is written once to ``results/climatology_adjustment/`` with the
  sha256 of its inputs and is **FROZEN**: the script refuses to overwrite an
  existing table unless ``--force`` is passed, and ``--force`` is only
  legitimate under a new dated amendment;
- no skill metric is computed (15-issue-date gate still closed).

    uv run --project backend python scripts/smn_era5_climatology_adjustment.py

Outputs under results/climatology_adjustment/:
- smn_era5_adjustment.csv   - per station/variable/month table with sha256
- smn_era5_adjustment.md    - provenance, method, fallback cells, limits
"""

from __future__ import annotations

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
REGTEMP_PATH = REPO / "data" / "smn_probe" / "regtemp" / "registro_temperatura365d_smn.txt"
CATALOGUE_PATH = REPO / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
ERA5_PATH = REPO / "data" / "raw" / "openmeteo-era5.parquet"
REGION_PATH = REPO / "configs" / "regions" / "argentina.yaml"
OUT_DIR = REPO / "results" / "climatology_adjustment"

WINDOW_START = pd.Timestamp("2025-11-11")
WINDOW_END = pd.Timestamp("2026-11-10")
MIN_PAIRED_DAYS = 20
AMENDMENT_DATE = "2026-11-13"
VARIABLES = ("t2m_max", "t2m_min")


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_smn_era5(
    smn: pd.DataFrame,
    era5: pd.DataFrame,
    *,
    window_start: pd.Timestamp = WINDOW_START,
    window_end: pd.Timestamp = WINDOW_END,
) -> pd.DataFrame:
    """Paired local-calendar days inside the capture window (both ok).

    Returns columns ``location``, ``variable``, ``time``, ``diff_smn_minus_era5``.
    """
    keep = ["location", "variable", "time", "value"]
    left = smn.loc[smn["quality_flag"].eq("ok"), keep].rename(
        columns={"value": "value_smn"}
    )
    right = era5.loc[era5["quality_flag"].eq("ok"), keep].rename(
        columns={"value": "value_era5"}
    )
    for frame in (left, right):
        frame["time"] = pd.to_datetime(frame["time"]).dt.normalize()
        frame["variable"] = frame["variable"].astype(str)
    merged = left.merge(right, on=["location", "variable", "time"], how="inner")
    merged = merged.loc[
        merged["time"].ge(window_start) & merged["time"].le(window_end)
    ]
    merged = merged.loc[merged["variable"].isin(VARIABLES)].copy()
    merged["diff_smn_minus_era5"] = merged["value_smn"] - merged["value_era5"]
    return merged[["location", "variable", "time", "diff_smn_minus_era5"]]


def adjustment_table(
    paired: pd.DataFrame,
    *,
    min_days: int = MIN_PAIRED_DAYS,
) -> pd.DataFrame:
    """Frozen table: one row per (station, variable, calendar month).

    Cells with ``n_paired_days < min_days`` carry the station's all-months
    mean difference instead of the cell mean (``used_fallback``). The grid is
    complete: every station × variable × calendar month 1–12, so a month with
    zero paired days is a visible fallback row, never an absent one.
    """
    if paired.empty:
        raise ValueError("no paired SMN/ERA5 days inside the capture window")
    paired = paired.copy()
    paired["calendar_month"] = paired["time"].dt.month
    station_mean = (
        paired.groupby(["location", "variable"], sort=True)["diff_smn_minus_era5"]
        .agg(station_all_months_mean="mean", station_all_months_n="size")
        .reset_index()
    )
    cells = (
        paired.groupby(["location", "variable", "calendar_month"], sort=True)[
            "diff_smn_minus_era5"
        ]
        .agg(n_paired_days="size", cell_mean="mean")
        .reset_index()
    )
    months = pd.DataFrame({"calendar_month": list(range(1, 13))})
    grid = station_mean[["location", "variable"]].merge(months, how="cross")
    table = grid.merge(cells, on=["location", "variable", "calendar_month"], how="left")
    table = table.merge(station_mean, on=["location", "variable"], how="left")
    table["n_paired_days"] = table["n_paired_days"].fillna(0).astype(int)
    table["used_fallback"] = table["n_paired_days"].lt(min_days)
    table["mean_diff_smn_minus_era5"] = table["cell_mean"].where(
        ~table["used_fallback"], table["station_all_months_mean"]
    )
    table["basis"] = table["used_fallback"].map(
        {True: "station_all_months", False: "station_calendar_month"}
    )
    zero_station = table["station_all_months_n"].isna().to_numpy().any()
    if zero_station:
        bad = table.loc[table["station_all_months_n"].isna(), "location"].unique()
        raise ValueError(
            f"no paired SMN/ERA5 days at all for station(s): {', '.join(bad)}"
        )
    table = table[
        [
            "location",
            "variable",
            "calendar_month",
            "n_paired_days",
            "mean_diff_smn_minus_era5",
            "used_fallback",
            "basis",
            "station_all_months_n",
        ]
    ].sort_values(["location", "variable", "calendar_month"], ignore_index=True)
    return table


def render_markdown(
    table: pd.DataFrame,
    paired: pd.DataFrame,
    inputs: dict[str, str],
    window: tuple[pd.Timestamp, pd.Timestamp],
    generated: pd.Timestamp,
) -> str:
    """Provenance, method, fallback cells and limits (never a skill metric)."""
    fallback = table.loc[table["used_fallback"]]
    window_start, window_end = window
    lines = [
        "# Climatology adjustment table — SMN − ERA5 (frozen)",
        "",
        (f"Generated by `scripts/smn_era5_climatology_adjustment.py` on "
        f"{generated} (UTC)."),
        "",
        (f"**Frozen by the {AMENDMENT_DATE} amendment of "
        "`docs/EVALUATION_PROTOCOL.md`** (“Temperature observation reference "
        "and climatology baseline”). The table is computed once and is **not "
        "re-estimated with later data unless a new dated amendment says so**; "
        "the script refuses to overwrite this file otherwise."),
        "",
        "## Estimation window and method",
        "",
        (f"- Window (only these paired days are used): **{window_start.date()} → "
        f"{window_end.date()}** local calendar — the regtemp capture window. It "
        "ends before the first archived issue date (2026-11-11), so it does "
        "not overlap the verification period."),
        ("- Pairing: (station, variable, local-calendar day), both sides "
        "`quality_flag == ok`; difference = **SMN − ERA5** (degC)."),
        ("- Cell: (station, variable, calendar month) over the window; "
        f"`n_paired_days >= {MIN_PAIRED_DAYS}` uses the cell mean, fewer uses "
        "the station's all-months mean difference over the same window."),
        (f"- Paired days used: **{len(paired)}** across "
        f"{table['location'].nunique()} stations × {len(VARIABLES)} variables."),
        "",
        "## Input sha256 (the table's provenance)",
        "",
        "| input | sha256 |",
        "| --- | --- |",
    ]
    for label, digest in inputs.items():
        lines.append(f"| `{label}` | `{digest}` |")
    lines += [
        "",
        "## Cells using the fallback (fewer than 20 paired days)",
        "",
    ]
    if fallback.empty:
        lines.append("None — every station-month reached "
                     f"{MIN_PAIRED_DAYS} paired days.")
    else:
        lines.append("| location | variable | calendar_month | n_paired_days | "
                     "station_all_months_n | mean_diff_smn_minus_era5 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for row in fallback.itertuples(index=False):
            lines.append(
                f"| {row.location} | {row.variable} | {row.calendar_month} | "
                f"{row.n_paired_days} | {int(row.station_all_months_n)} | "
                f"{row.mean_diff_smn_minus_era5:+.3f} |"
            )
    lines += [
        "",
        "## Limits (stated in the amendment)",
        "",
        "- One year of overlap (the capture window above).",
        "- Mean shift only — no variance or quantile adjustment.",
        ("- A station-month rests on at most one calendar month of paired days "
        "(about 30 days), and fallback cells rest on that station's pooled "
        "window instead."),
        ("- Diagnostic/baseline input, not a skill metric: nothing here is a "
        "CRPS, Brier or reliability number (15-issue-date gate)."),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regtemp", type=Path, default=REGTEMP_PATH)
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE_PATH)
    parser.add_argument("--era5", type=Path, default=ERA5_PATH)
    parser.add_argument("--region", type=Path, default=REGION_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing frozen table (only with a new dated amendment)",
    )
    args = parser.parse_args(argv)

    out_csv = args.out_dir / "smn_era5_adjustment.csv"
    out_md = args.out_dir / "smn_era5_adjustment.md"
    if out_csv.exists() and not args.force:
        print(
            f"refusing to overwrite frozen table {out_csv}; it may only change "
            f"under a new dated amendment (pass --force with one)"
        )
        return 1

    from prisma.ingest.base import load_region
    from prisma.report.smn_leg import (
        build_smn_frame,
        parse_catalogue_nro_names,
        parse_regtemp,
        resolve_region_stations,
    )

    for path in (args.regtemp, args.catalogue, args.era5, args.region):
        if not path.is_file():
            raise FileNotFoundError(path)

    region = load_region(args.region)
    regtemp = parse_regtemp(args.regtemp)
    resolution = resolve_region_stations(
        region, parse_catalogue_nro_names(args.catalogue), set(regtemp["regtemp_name"])
    )
    unresolved = resolution.loc[
        ~resolution["match_status"].str.startswith("resolved"), "location"
    ].tolist()
    if unresolved:
        raise ValueError(f"unresolved region stations: {', '.join(unresolved)}")
    smn = build_smn_frame(regtemp, resolution)

    era5 = pd.read_parquet(args.era5)
    era5["time"] = pd.to_datetime(era5["time"])
    if "source" in era5.columns:
        era5 = era5.loc[era5["source"].eq("openmeteo-era5")]

    paired = pair_smn_era5(smn, era5)
    table = adjustment_table(paired)

    inputs = {
        args.regtemp.relative_to(REPO).as_posix(): sha256_of(args.regtemp),
        args.era5.relative_to(REPO).as_posix(): sha256_of(args.era5),
        args.catalogue.relative_to(REPO).as_posix(): sha256_of(args.catalogue),
        args.region.relative_to(REPO).as_posix(): sha256_of(args.region),
    }
    table = table.copy()
    table["input_regtemp_sha256"] = inputs[args.regtemp.relative_to(REPO).as_posix()]
    table["input_era5_sha256"] = inputs[args.era5.relative_to(REPO).as_posix()]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_csv, index=False)
    generated = datetime.now(UTC)
    out_md.write_text(
        render_markdown(table, paired, inputs, (WINDOW_START, WINDOW_END), generated),
        encoding="utf-8",
        newline="\n",
    )
    fallback_n = int(table["used_fallback"].sum())
    print(
        f"{len(paired)} paired days -> {out_csv} "
        f"({len(table)} cells, {fallback_n} fallback)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
