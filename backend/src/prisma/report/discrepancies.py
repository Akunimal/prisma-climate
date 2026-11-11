"""Cross-source discrepancy report (plan section 3.6).

Compares the same place and day across the normalized sources already stored
under data/raw/ and writes the report to results/discrepancies/. The report
serves three purposes: detect systematic bias in a source, catch unit or
timezone mistakes, and document honestly where sources disagree.

It also decomposes the ERA5-vs-station t2m_max bias into elevation,
hourly-sampling and day-convention contributions (plan section 3.6 follow-up),
and runs an orography check on the precipitation ratio at Salta and Ushuaia.

It is always produced by this script, never hand-edited.
"""

from __future__ import annotations

import argparse
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingest.base import find_repo_root, load_region, utc_now
from .bias_decomposition import (
    decompose_location,
    fetch_grid_elevation,
    fetch_hourly_t2m,
    hourly_sampling_correction,
    precip_orography_record,
)

# Labelling thresholds only; they never filter rows out of the comparison.
TEMP_BIAS_FLAG_C = 3.0
CORRELATION_FLAG = 0.90
PRECIP_RATIO_RANGE = (0.70, 1.40)


def _ok_rows(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    rows = frame.loc[frame["quality_flag"].eq("ok"), ["location", "variable", "time", "value"]]
    return rows.rename(columns={"value": value_name})


def compare(
    frame_a: pd.DataFrame,
    frame_b: pd.DataFrame,
    *,
    source_a: str,
    source_b: str,
) -> pd.DataFrame:
    """Inner-join two normalized frames on (location, variable, time) and score them."""
    merged = _ok_rows(frame_a, "value_a").merge(
        _ok_rows(frame_b, "value_b"),
        on=["location", "variable", "time"],
        how="inner",
    )
    if merged.empty:
        raise ValueError(f"no overlapping rows between {source_a} and {source_b}")

    records: list[dict] = []
    for (location, variable), group in merged.groupby(["location", "variable"], sort=True):
        diff = group["value_a"] - group["value_b"]
        n = len(group)
        record = {
            "location": location,
            "variable": variable,
            "n_days": n,
            "bias": diff.mean(),
            "mae": diff.abs().mean(),
            "rmse": (diff.pow(2).mean()) ** 0.5,
            "corr": group["value_a"].corr(group["value_b"]) if n > 2 else pd.NA,
            "p95_abs_diff": diff.abs().quantile(0.95),
            f"mean_{source_a}": group["value_a"].mean(),
            f"mean_{source_b}": group["value_b"].mean(),
            f"ratio_{source_a}_over_{source_b}": pd.NA,
        }
        if variable == "precip":
            total_b = group["value_b"].sum()
            if total_b > 0:
                record[f"ratio_{source_a}_over_{source_b}"] = group["value_a"].sum() / total_b
        record["flags"] = _flags(record, variable, source_a, source_b)
        records.append(record)

    return pd.DataFrame.from_records(records)


def _flags(record: dict, variable: str, source_a: str, source_b: str) -> str:
    notes: list[str] = []
    if variable in ("t2m", "t2m_max", "t2m_min"):
        if abs(record["bias"]) >= TEMP_BIAS_FLAG_C:
            notes.append(f"|bias| >= {TEMP_BIAS_FLAG_C:g} C")
        corr = record["corr"]
        if corr is not pd.NA and corr == corr and corr < CORRELATION_FLAG:
            notes.append(f"corr < {CORRELATION_FLAG:g}")
    if variable == "precip":
        ratio = record[f"ratio_{source_a}_over_{source_b}"]
        if ratio is not pd.NA and ratio == ratio:
            low, high = PRECIP_RATIO_RANGE
            if not low <= ratio <= high:
                notes.append(f"total ratio outside [{low:g}, {high:g}]")
    return "; ".join(notes)


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a DataFrame as a GitHub-flavoured Markdown table (no tabulate dep)."""
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = ["" if pd.isna(value) else str(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _ok_series(frame: pd.DataFrame, variable: str, location: str) -> pd.Series:
    rows = frame.loc[
        frame["quality_flag"].eq("ok")
        & frame["variable"].eq(variable)
        & frame["location"].eq(location),
        ["time", "value"],
    ]
    series = rows.set_index(pd.to_datetime(rows["time"]))["value"].sort_index()
    return series[~series.index.duplicated(keep="last")]


def collect_t2m_max_decomposition(
    era5: pd.DataFrame,
    ghcn: pd.DataFrame,
    region: dict[str, Any],
    *,
    fetch_elevation: Callable[..., float | None] = fetch_grid_elevation,
    fetch_hourly: Callable[..., pd.DataFrame] = fetch_hourly_t2m,
    sample_window_days: int = 21,
    pause_seconds: float = 2.0,
) -> pd.DataFrame:
    """Residual ERA5−station t2m_max bias after each sequential adjustment.

    Network calls (grid elevation, recent hourly t2m) are injectable for tests.
    """
    records: list[dict[str, Any]] = []
    era5_max = pd.to_datetime(era5["time"]).max()
    sample_end = (era5_max - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    sample_start = (
        pd.Timestamp(sample_end) - pd.Timedelta(days=sample_window_days)
    ).strftime("%Y-%m-%d")

    for station in region["stations"]:
        location = station["name"]
        era5_tmax = _ok_series(era5, "t2m_max", location)
        ghcn_tmax = _ok_series(ghcn, "t2m_max", location)
        if era5_tmax.empty or ghcn_tmax.empty:
            continue

        grid_el = fetch_elevation(
            station["lat"],
            station["lon"],
            timezone=region.get("timezone", "UTC"),
        )
        hourly = fetch_hourly(
            station["lat"],
            station["lon"],
            sample_start,
            sample_end,
            timezone=region.get("timezone", "UTC"),
            pause_seconds=pause_seconds,
        )
        sampling = hourly_sampling_correction(hourly)
        record = decompose_location(
            era5_tmax,
            ghcn_tmax,
            grid_elevation_m=grid_el,
            station_elevation_m=station.get("elevation_m"),
            sampling_correction_c=sampling,
        )
        record["location"] = location
        record["sample_window"] = f"{sample_start}..{sample_end}"
        records.append(record)
        time.sleep(pause_seconds)

    columns = [
        "location",
        "n_days",
        "bias_raw",
        "bias_after_elevation",
        "bias_after_sampling",
        "bias_after_day_convention",
        "best_day_lag",
        "grid_elevation_m",
        "station_elevation_m",
        "elevation_diff_m",
        "sampling_correction_c",
        "sample_window",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records)[columns]


def collect_precip_orography(
    era5: pd.DataFrame,
    ghcn: pd.DataFrame,
    region: dict[str, Any],
    *,
    locations: tuple[str, ...] = ("Salta Aero", "Ushuaia Malvinas Argentinas"),
    fetch_elevation: Callable[..., float | None] = fetch_grid_elevation,
    pause_seconds: float = 2.0,
) -> pd.DataFrame:
    """Orography context for the precip total ratio at the named locations."""
    by_name = {station["name"]: station for station in region["stations"]}
    records: list[dict[str, Any]] = []
    for location in locations:
        station = by_name.get(location)
        if station is None:
            continue
        era5_p = _ok_series(era5, "precip", location)
        ghcn_p = _ok_series(ghcn, "precip", location)
        pair = pd.DataFrame({"era5": era5_p, "station": ghcn_p}).dropna()
        if pair.empty:
            continue
        total_station = float(pair["station"].sum())
        ratio = float(pair["era5"].sum()) / total_station if total_station > 0 else None
        grid_el = fetch_elevation(
            station["lat"],
            station["lon"],
            timezone=region.get("timezone", "UTC"),
        )
        record = precip_orography_record(
            ratio,
            grid_el,
            station.get("elevation_m"),
        )
        record["location"] = location
        record["n_days"] = len(pair)
        records.append(record)
        time.sleep(pause_seconds)

    columns = [
        "location",
        "n_days",
        "precip_ratio_era5_over_station",
        "grid_elevation_m",
        "station_elevation_m",
        "elevation_diff_m",
        "note",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame.from_records(records)[columns]


def render_decomposition_section(
    t2m_table: pd.DataFrame,
    precip_table: pd.DataFrame,
) -> str:
    """Markdown section with residual bias after each adjustment step."""
    lines = [
        "",
        "## Bias decomposition — t2m_max (ERA5 vs GHCN)",
        "",
        "Sequential adjustments on the same overlapping days; each residual is "
        "the mean(ERA5 − station) after that step only:",
        "",
        "1. **raw** — unadjusted difference",
        "2. **elevation** — lapse-rate correction (6.5 °C/km) from grid-cell "
        "orography to station elevation",
        "3. **sampling** — constant mean correction from a parabolic peak fit "
        "to recent hourly ERA5 (sub-hourly max missing from hourly-sampled daily max)",
        "4. **day_convention** — best lag in {−1, 0, +1} days minimizing MAE",
        "",
    ]
    if t2m_table.empty:
        lines.append("_No overlapping t2m_max rows; decomposition skipped._")
    else:
        display = t2m_table.copy()
        for column in (
            "bias_raw",
            "bias_after_elevation",
            "bias_after_sampling",
            "bias_after_day_convention",
            "grid_elevation_m",
            "station_elevation_m",
            "elevation_diff_m",
            "sampling_correction_c",
            "lag_mae",
        ):
            if column in display.columns:
                display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
        lag = pd.to_numeric(display["best_day_lag"], errors="coerce").astype("Int64")
        display["best_day_lag"] = lag
        lines.append(_markdown_table(display))

    lines += [
        "",
        "## Orography check — precip (Salta, Ushuaia)",
        "",
        "Total ERA5/GHCN precip ratio with grid-vs-station elevation gap. "
        "A high ratio with a high grid cell is consistent with orographic "
        "enhancement; it does not prove it.",
        "",
    ]
    if precip_table.empty:
        lines.append("_No overlapping precip rows for the requested locations._")
    else:
        display = precip_table.copy()
        for column in (
            "precip_ratio_era5_over_station",
            "grid_elevation_m",
            "station_elevation_m",
            "elevation_diff_m",
        ):
            display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
        lines.append(_markdown_table(display))
    return "\n".join(lines)


def render_markdown(
    table: pd.DataFrame,
    *,
    source_a: str,
    source_b: str,
    period_start: pd.Timestamp,
    period_end: pd.Timestamp,
    generated_at: pd.Timestamp,
    decomposition_section: str = "",
) -> str:
    locations = table["location"].nunique()
    total_days = int(table["n_days"].sum())
    flagged = table.loc[table["flags"].ne(""), ["location", "variable", "flags"]]

    lines = [
        f"# Source discrepancy report — {source_a} vs {source_b}",
        "",
        f"Generated by `python -m prisma.report.discrepancies` on {generated_at} (UTC).",
        "",
        f"- Overlapping period: {period_start.date()} to {period_end.date()}",
        f"- Location × variable groups: {len(table)} across {locations} locations "
        f"({total_days} paired days in total)",
        "- Rows compared: `quality_flag == ok` only, joined on the same local-calendar day "
        "(`day_convention: local_calendar` for both sources)",
        f"- {source_a} is a grid value (nearest cell); {source_b} is a station observation. "
        "Some difference is expected; the flags below mark where it becomes suspicious.",
        "",
        "## Metrics",
        "",
    ]

    display = table.copy()
    for column in ("bias", "mae", "rmse", "p95_abs_diff"):
        if column in display:
            display[column] = display[column].round(2)
    ratio_column = next((c for c in display.columns if c.startswith("ratio_")), None)
    if ratio_column:
        display[ratio_column] = pd.to_numeric(display[ratio_column], errors="coerce").round(2)
    for column in (f"mean_{source_a}", f"mean_{source_b}", "corr"):
        if column in display:
            display[column] = pd.to_numeric(display[column], errors="coerce").round(2)

    lines.append(_markdown_table(display))
    lines += ["", "## Flags", ""]
    if flagged.empty:
        lines.append("No group crossed a flag threshold.")
    else:
        lines.append(
            "Flagged groups (thresholds: temperature "
            f"|bias| >= {TEMP_BIAS_FLAG_C:g} °C or corr < {CORRELATION_FLAG:g}; "
            f"precip total ratio outside [{PRECIP_RATIO_RANGE[0]:g}, {PRECIP_RATIO_RANGE[1]:g}]):"
        )
        lines.append("")
        for row in flagged.itertuples(index=False):
            lines.append(f"- **{row.location} / {row.variable}**: {row.flags}")

    lines += decomposition_section.splitlines(keepends=False) if decomposition_section else []

    lines += [
        "",
        "## What this does not show",
        "",
        "- No forecast is involved here: this compares two observational/reanalysis sources, "
        "not a prediction against what happened (that is verification, Phase 1).",
        "- SMN Argentina is not included yet; it joins this report once its connector lands.",
        "- A flag is a prompt to investigate, not proof of an error in either source.",
        "- No verification metric (CRPS, Brier, reliability) is quoted: archived forecasts "
        "have not yet reached the 15-day maturity gate in `docs/EVALUATION_PROTOCOL.md`.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    parser = argparse.ArgumentParser(prog="python -m prisma.report.discrepancies")
    parser.add_argument(
        "--era5",
        type=Path,
        default=root / "data" / "raw" / "openmeteo-era5.parquet",
        help="path to the normalized ERA5 Parquet",
    )
    parser.add_argument(
        "--ghcn",
        type=Path,
        default=root / "data" / "raw" / "ghcn-daily.parquet",
        help="path to the normalized GHCN-Daily Parquet",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "results" / "discrepancies",
        help="directory for the CSV and Markdown report",
    )
    parser.add_argument(
        "--region",
        default="argentina",
        help="region config stem used for elevations in the decomposition",
    )
    parser.add_argument(
        "--skip-decomposition",
        action="store_true",
        help="skip the network-backed t2m_max / precip orography sections",
    )
    args = parser.parse_args(argv)

    era5 = pd.read_parquet(args.era5)
    ghcn = pd.read_parquet(args.ghcn)
    era5["time"] = pd.to_datetime(era5["time"])
    ghcn["time"] = pd.to_datetime(ghcn["time"])

    table = compare(era5, ghcn, source_a="era5", source_b="ghcn")
    ok_columns = ["location", "variable", "time", "value"]
    overlap = era5.loc[era5["quality_flag"].eq("ok"), ok_columns].merge(
        ghcn.loc[ghcn["quality_flag"].eq("ok"), ok_columns],
        on=["location", "variable", "time"],
        suffixes=("_era5", "_ghcn"),
    )
    period_start = overlap["time"].min()
    period_end = overlap["time"].max()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    decomposition_section = ""
    if not args.skip_decomposition:
        region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
        print("collecting t2m_max bias decomposition (network)…")
        t2m_table = collect_t2m_max_decomposition(era5, ghcn, region)
        print("collecting precip orography check (network)…")
        precip_table = collect_precip_orography(era5, ghcn, region)
        decomposition_section = render_decomposition_section(t2m_table, precip_table)
        if not t2m_table.empty:
            t2m_table.to_csv(args.out_dir / "era5_vs_ghcn_t2m_max_decomposition.csv", index=False)
        if not precip_table.empty:
            precip_table.to_csv(args.out_dir / "era5_vs_ghcn_precip_orography.csv", index=False)

    csv_path = args.out_dir / "era5_vs_ghcn.csv"
    md_path = args.out_dir / "era5_vs_ghcn.md"
    table.to_csv(csv_path, index=False)
    md_path.write_text(
        render_markdown(
            table,
            source_a="era5",
            source_b="ghcn",
            period_start=period_start,
            period_end=period_end,
            generated_at=utc_now(),
            decomposition_section=decomposition_section,
        ),
        encoding="utf-8",
    )
    print(f"{len(table)} groups -> {csv_path.relative_to(root)}")
    print(f"report -> {md_path.relative_to(root)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
