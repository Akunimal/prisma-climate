"""Audit GHCN-Daily TMAX source/quality flags against the ERA5 bias step.

T26a showed the ERA5−GHCN t2m_max bias stepping from about −2.21 °C
(1996–2003) to −3.49 °C (2005–2025) alongside a coverage drop (mean n_days
271.8 in 2003 -> 169.3 in 2005). This audit reads the raw ``.dly`` files in
``data/cache/ghcn/`` (gitignored, never re-fetched here) and:

1. counts every TMAX value per station and per year 1996–2025 by GHCN SOURCE
   flag (column 8 of each 8-char day field) and by QUALITY flag (column 7);
2. pairs the same TMAX days with ERA5 (both sides ``quality_flag ok``, local
   calendar day, as in the discrepancy report) and computes the
   ERA5−GHCN t2m_max bias grouped by SOURCE flag and by period.

It reports whether the 2003→2005 step coincides with a change of source-flag
composition — a table reading, never a causal claim. No skill metric is
computed. Every value in results/ comes only from this script.

    uv run --project backend python scripts/ghcn_tmax_source_flag_audit.py

Outputs under results/discrepancies/:
- tmax_source_flag_counts.csv - location, year, source_flag, quality_flag, n
- tmax_bias_by_source_flag.csv - source_flag, period, n_pairs, mean bias
- tmax_source_flag_audit.md   - the tables and the step reading
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
CACHE_DIR = REPO / "data" / "cache" / "ghcn"
REGION = REPO / "configs" / "regions" / "argentina.yaml"
ERA5_PATH = REPO / "data" / "raw" / "openmeteo-era5.parquet"
OUT_DIR = REPO / "results" / "discrepancies"

ELEMENT = "TMAX"
MIN_YEAR = 1996
MAX_YEAR = 2025
PERIODS = (
    ("1996-2003", 1996, 2003),
    ("2004", 2004, 2004),
    ("2005-2025", 2005, 2025),
)
BLANK = "(blank)"


def flag_letter(char: str) -> str:
    """Readable flag: a blank column is a real value (the 'no flag' case)."""
    return BLANK if char.strip() == "" else char


def parse_tmax_flags(text: str, ghcn_id: str, location: str) -> pd.DataFrame:
    """Every non-missing TMAX value with its SOURCE and QUALITY flags.

    Day fields are 8 characters: 5-digit value in tenths, measurement flag,
    quality flag, source flag (NOAA GHCN-Daily readme, fixed-width layout).
    """
    rows: list[dict] = []
    for line in text.splitlines():
        if len(line) < 21:
            continue
        try:
            year = int(line[11:15])
            month = int(line[15:17])
        except ValueError:
            continue
        if line[17:21] != ELEMENT or not MIN_YEAR <= year <= MAX_YEAR:
            continue
        for day in range(31):
            chunk = line[21 + day * 8 : 21 + day * 8 + 8]
            if len(chunk) < 8:
                break
            raw = chunk[0:5].strip()
            if not raw:
                continue
            try:
                value = int(raw)
            except ValueError:
                continue
            if value == -9999:
                continue
            try:
                when = pd.Timestamp(year=year, month=month, day=day + 1)
            except ValueError:
                continue
            rows.append(
                {
                    "ghcn_id": ghcn_id,
                    "location": location,
                    "time": when,
                    "year": year,
                    "value": value / 10.0,
                    "source_flag": flag_letter(chunk[7]),
                    "quality_flag": flag_letter(chunk[6]),
                }
            )
    return pd.DataFrame(rows)


def load_stations(region_path: Path) -> list[tuple[str, str]]:
    """(ghcn_id, location name) pairs from the region config."""
    from prisma.ingest.base import load_region

    region = load_region(region_path)
    pairs = [
        (str(station["ghcn_id"]), str(station["name"]))
        for station in region["stations"]
        if station.get("ghcn_id")
    ]
    if not pairs:
        raise ValueError(f"{region_path} declares no ghcn_id")
    return pairs


def period_label(year: int) -> str:
    for label, start, end in PERIODS:
        if start <= year <= end:
            return label
    return "out-of-range"


def pair_with_era5(ghcn_days: pd.DataFrame, era5: pd.DataFrame) -> pd.DataFrame:
    """Paired local-calendar t2m_max days with the GHCN source flag attached."""
    era = era5.loc[
        era5["variable"].eq("t2m_max") & era5["quality_flag"].eq("ok"),
        ["location", "time", "value"],
    ].rename(columns={"value": "value_era5"})
    ok = ghcn_days.loc[ghcn_days["quality_flag"].eq(BLANK)].rename(
        columns={"value": "value_ghcn"}
    )
    merged = ok.merge(era, on=["location", "time"], how="inner")
    merged["bias_era5_minus_ghcn"] = merged["value_era5"] - merged["value_ghcn"]
    merged["period"] = merged["year"].map(period_label)
    return merged


def markdown_report(
    counts: pd.DataFrame,
    bias: pd.DataFrame,
    paired: pd.DataFrame,
    stations: list[tuple[str, str]],
    generated_at: datetime,
) -> str:
    lines = [
        "# GHCN TMAX source/quality flag audit",
        "",
        (
            f"Generated {generated_at.strftime('%Y-%m-%d %H:%M:%S')} (UTC) by "
            "`scripts/ghcn_tmax_source_flag_audit.py` from the raw `.dly` files in "
            f"`data/cache/ghcn/` ({len(stations)} stations, TMAX only, years "
            f"{MIN_YEAR}–{MAX_YEAR}; a blank flag column is shown as `{BLANK}`). "
            "The cache is gitignored and is read, never re-fetched, by this script."
        ),
        "",
        (
            "Diagnostic table, not a skill metric: no CRPS/Brier/reliability number "
            "exists before the 15-issue-date gate "
            "(`docs/EVALUATION_PROTOCOL.md`). Counts and biases below describe what "
            "the files carry; they assert no cause."
        ),
        "",
    ]

    period_counts = (
        counts.groupby(["period", "source_flag"], sort=False)["n"].sum().reset_index()
    )
    totals = period_counts.groupby("period")["n"].transform("sum")
    period_counts["share_pct"] = (100 * period_counts["n"] / totals).round(1)
    lines += [
        "## TMAX values by source flag and period",
        "",
        "| period | source_flag | n | share_pct |",
        "| --- | --- | --- | --- |",
    ]
    for row in period_counts.itertuples(index=False):
        lines.append(
            f"| {row.period} | {row.source_flag} | {row.n} | {row.share_pct} |"
        )

    lines += [
        "",
        "## TMAX values by quality flag and period",
        "",
        "| period | quality_flag | n |",
        "| --- | --- | --- |",
    ]
    quality_counts = (
        counts.groupby(["period", "quality_flag"], sort=False)["n"].sum().reset_index()
    )
    for row in quality_counts.itertuples(index=False):
        lines.append(f"| {row.period} | {row.quality_flag} | {row.n} |")

    lines += [
        "",
        "## Per-year source-flag composition (all stations)",
        "",
        "| year | " + " | ".join(sorted(counts["source_flag"].unique())) + " |",
        "| --- | " + " | ".join("---" for _ in counts["source_flag"].unique()) + " |",
    ]
    pivot = counts.pivot_table(
        index="year",
        columns="source_flag",
        values="n",
        aggfunc="sum",
        fill_value=0,
        sort=False,
    )
    pivot = pivot.reindex(columns=sorted(counts["source_flag"].unique()), fill_value=0)
    for year, row in pivot.iterrows():
        lines.append(f"| {year} | " + " | ".join(str(int(v)) for v in row) + " |")

    lines += [
        "",
        "## ERA5−GHCN t2m_max bias by source flag",
        "",
        (
            "Paired local-calendar days, both sides `quality_flag ok` (the same "
            "pairing as the discrepancy report); positive = ERA5 warmer."
        ),
        "",
        "| period | source_flag | n_pairs | mean_bias_C |",
        "| --- | --- | --- | --- |",
    ]
    for row in bias.itertuples(index=False):
        lines.append(
            f"| {row.period} | {row.source_flag} | {row.n_pairs} | "
            f"{row.mean_bias_era5_minus_ghcn:+.2f} |"
        )

    station_days = paired.groupby(["year", "location"]).size().reset_index(name="n_days")
    mean_days = station_days.groupby("year")["n_days"].mean()
    lines += [
        "",
        "## Coverage context (paired station-days, mean per station)",
        "",
        "| year | mean n_days |",
        "| --- | --- |",
    ]
    for year in sorted(mean_days.index):
        lines.append(f"| {year} | {mean_days.loc[year]:.1f} |")

    early = counts.loc[counts["period"].eq("1996-2003")].groupby("source_flag")["n"].sum()
    late = counts.loc[counts["period"].eq("2005-2025")].groupby("source_flag")["n"].sum()
    early_share = (100 * early / early.sum()).round(1).to_dict()
    late_share = (100 * late / late.sum()).round(1).to_dict()
    flags = sorted(set(early_share) | set(late_share))
    share_text = "; ".join(
        f"{flag} {early_share.get(flag, 0.0):.1f}% -> {late_share.get(flag, 0.0):.1f}%"
        for flag in flags
    )
    moved = [
        flag
        for flag in flags
        if abs(early_share.get(flag, 0.0) - late_share.get(flag, 0.0)) >= 1.0
    ]
    lines += [
        "",
        "## Reading: does the 2003→2005 step coincide with a source-flag change?",
        "",
        "Source-flag share of TMAX values, 1996–2003 vs 2005–2025: "
        + (share_text if share_text else "no TMAX values in either block")
        + ".",
        "",
        (
            f"Shares moved by >= 1.0 point: {', '.join(moved)}. The composition "
            "change and the bias/coverage step occur at the same time in these "
            "tables, and the per-period bias rows above show what each flag's "
            "own bias is on either side of the step."
            if moved
            else "No share moved by >= 1.0 point, so the step does not coincide "
            "with a source-flag composition change in these tables."
        ),
        "",
        (
            "Temporal coincidence in a table is not a cause: nothing here claims "
            "why the bias moved. The discriminating candidates stay the ones listed "
            "in `bias_reattribution.md`, none asserted."
        ),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR)
    parser.add_argument("--region", type=Path, default=REGION)
    parser.add_argument("--era5", type=Path, default=ERA5_PATH)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    stations = load_stations(args.region)
    frames = []
    for ghcn_id, location in stations:
        path = args.cache_dir / f"{ghcn_id}.dly"
        if not path.is_file():
            raise FileNotFoundError(f"missing cached .dly for {location}: {path}")
        frames.append(parse_tmax_flags(path.read_text(encoding="ascii"), ghcn_id, location))
    days = pd.concat(frames, ignore_index=True)

    counts = (
        days.groupby(["location", "year", "source_flag", "quality_flag"], sort=True)
        .size()
        .reset_index(name="n")
    )
    counts["period"] = counts["year"].map(period_label)
    counts = counts[
        ["location", "year", "period", "source_flag", "quality_flag", "n"]
    ]

    era5 = pd.read_parquet(args.era5)
    era5["time"] = pd.to_datetime(era5["time"])
    paired = pair_with_era5(days, era5)
    if paired.empty:
        raise ValueError("no paired ERA5/GHCN t2m_max days")

    bias = (
        paired.groupby(["period", "source_flag"], sort=False)["bias_era5_minus_ghcn"]
        .agg(n_pairs="size", mean_bias_era5_minus_ghcn="mean")
        .reset_index()
    )
    overall = (
        paired.groupby("source_flag")["bias_era5_minus_ghcn"]
        .agg(n_pairs="size", mean_bias_era5_minus_ghcn="mean")
        .reset_index()
    )
    overall.insert(0, "period", "all years")
    bias = pd.concat([overall, bias], ignore_index=True)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    counts.to_csv(args.out_dir / "tmax_source_flag_counts.csv", index=False)
    bias.to_csv(args.out_dir / "tmax_bias_by_source_flag.csv", index=False)
    generated = datetime.now(UTC)
    (args.out_dir / "tmax_source_flag_audit.md").write_text(
        markdown_report(counts, bias, paired, stations, generated),
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"{len(days)} TMAX values, {len(paired)} paired days -> "
        f"{args.out_dir / 'tmax_source_flag_audit.md'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
