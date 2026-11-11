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
    fetch_dem_elevation,
    fetch_grid_elevation,
    fetch_hourly_t2m,
    fetch_raw_grid_t2m_max,
    hourly_sampling_correction,
    precip_orography_record,
)
from .station_crosscheck import render_markdown as crosscheck_markdown

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


WATER_CELL_EXCLUSION = (
    "elevation=nan returned grid-cell elevation 0.0 m: the selected ERA5 cell is "
    "water-masked (open-meteo/open-meteo#1155 documents that grid cells with more "
    "than 50 % water coverage store no elevation and report 0), so this raw series "
    "comes from a different, water-dominated cell than the land-preferred cell the "
    "downscaled track uses; with elevation=nan the cell_selection parameter does "
    "not change the selected cell (land/nearest/sea all return the same cell)"
)


def _track_status(series_label: str, source_elevation_m: float | None) -> tuple[str, str]:
    """Water-masked raw cells are excluded from track means, with the reason kept."""
    if series_label == "raw_grid" and source_elevation_m == 0.0:
        return "excluded", WATER_CELL_EXCLUSION
    return "ok", ""


def collect_t2m_max_decomposition(
    era5: pd.DataFrame,
    ghcn: pd.DataFrame,
    region: dict[str, Any],
    *,
    fetch_dem_elev: Callable[..., float | None] = fetch_dem_elevation,
    fetch_raw_grid: Callable[..., tuple[pd.Series, float | None]] = fetch_raw_grid_t2m_max,
    fetch_hourly: Callable[..., pd.DataFrame] = fetch_hourly_t2m,
    sample_window_days: int = 21,
    pause_seconds: float = 2.0,
) -> pd.DataFrame:
    """Residual ERA5−station t2m_max bias after each sequential adjustment.

    Two parallel tracks per location (Open-Meteo applies statistical
    downscaling to the 90 m DEM by default; ``elevation=nan`` disables it):

    - ``downscaled`` — the stored connector series; source elevation = DEM.
    - ``raw_grid`` — refetched with ``elevation=nan``; source elevation =
      average grid-cell orography.

    Network calls are injectable for tests.
    """
    records: list[dict[str, Any]] = []
    era5_max = pd.to_datetime(era5["time"]).max()
    sample_end = (era5_max - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    sample_start = (
        pd.Timestamp(sample_end) - pd.Timedelta(days=sample_window_days)
    ).strftime("%Y-%m-%d")
    history_start = str(region.get("history_start", "1996-01-01"))

    for station in region["stations"]:
        location = station["name"]
        era5_tmax = _ok_series(era5, "t2m_max", location)
        ghcn_tmax = _ok_series(ghcn, "t2m_max", location)
        if era5_tmax.empty or ghcn_tmax.empty:
            continue

        timezone = region.get("timezone", "UTC")
        raw_end = max(pd.Timestamp(ghcn_tmax.index.max()), pd.Timestamp(era5_tmax.index.max()))
        raw_series, grid_el = fetch_raw_grid(
            station["lat"],
            station["lon"],
            history_start,
            raw_end.strftime("%Y-%m-%d"),
            timezone=timezone,
            pause_seconds=pause_seconds,
        )
        dem_el = fetch_dem_elev(station["lat"], station["lon"], timezone=timezone)
        hourly = fetch_hourly(
            station["lat"],
            station["lon"],
            sample_start,
            sample_end,
            timezone=timezone,
            pause_seconds=pause_seconds,
        )
        sampling = hourly_sampling_correction(hourly)
        window = f"{sample_start}..{sample_end}"

        tracks = [
            ("downscaled", era5_tmax, dem_el),
            ("raw_grid", raw_series, grid_el),
        ]
        for series_label, series, source_el in tracks:
            if series.empty:
                continue
            record = decompose_location(
                series,
                ghcn_tmax,
                grid_elevation_m=source_el,
                station_elevation_m=station.get("elevation_m"),
                sampling_correction_c=sampling,
            )
            record["series"] = series_label
            record["location"] = location
            record["source_elevation_m"] = record.pop("grid_elevation_m")
            record["dem_elevation_m"] = dem_el
            record["grid_elevation_m"] = grid_el
            record["sample_window"] = window
            status, reason = _track_status(series_label, source_el)
            record["status"] = status
            record["exclusion_reason"] = reason
            records.append(record)
        time.sleep(pause_seconds)

    columns = [
        "series",
        "location",
        "status",
        "n_days",
        "bias_raw",
        "bias_after_elevation",
        "bias_after_sampling",
        "bias_after_day_convention",
        "best_day_lag",
        "source_elevation_m",
        "dem_elevation_m",
        "grid_elevation_m",
        "station_elevation_m",
        "elevation_diff_m",
        "sampling_correction_c",
        "sample_window",
        "exclusion_reason",
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


def _included(track: pd.DataFrame) -> pd.DataFrame:
    """Rows contributing to track means (``status`` column, when present)."""
    if "status" in track.columns:
        return track.loc[track["status"].eq("ok")]
    return track


def _excluded_track_lines(t2m_table: pd.DataFrame) -> list[str]:
    """Excluded tracks with their recorded reason, computed from the table."""
    if "status" not in t2m_table.columns:
        return []
    excluded = t2m_table.loc[t2m_table["status"].ne("ok")]
    if excluded.empty:
        return []
    lines = ["", "Excluded from track means:", ""]
    for row in excluded.itertuples(index=False):
        final = row.bias_after_day_convention
        final_text = f"{final:+.2f}" if final is not None and final == final else "n/a"
        lines.append(
            f"- `{row.series}` @ {row.location}: final residual {final_text} °C, "
            f"grid-cell elevation {row.source_elevation_m:g} m — excluded, reason: "
            f"{row.exclusion_reason}."
        )
    return lines


def _convergence_lines(t2m_table: pd.DataFrame) -> list[str]:
    """Track-agreement statement over included pairs, with exceptions spelled out."""
    final = "bias_after_day_convention"
    has_status = "status" in t2m_table.columns

    def by_location(series_label: str, included_only: bool) -> pd.Series:
        track = t2m_table.loc[t2m_table["series"].eq(series_label)]
        if included_only and has_status:
            track = track.loc[track["status"].eq("ok")]
        return track.set_index("location")[final].astype(float)

    downscaled = by_location("downscaled", True)
    raw = by_location("raw_grid", True)
    common = downscaled.index.intersection(raw.index)
    lines: list[str] = []
    if len(common):
        delta = (raw.loc[common] - downscaled.loc[common]).abs()
        lines.append(
            f"- Track convergence: at all {len(common)} location(s) with both tracks "
            f"included, the final residual agrees within {delta.max():.3f} °C "
            f"(mean |Δ| {delta.mean():.3f} °C)."
        )
    if not has_status:
        return lines
    excluded = t2m_table.loc[t2m_table["status"].ne("ok")]
    for row in excluded.itertuples(index=False):
        if row.series != "raw_grid":
            continue
        pair = downscaled.get(row.location)
        if pair is None:
            lines.append(
                f"- Exception: raw_grid excluded at {row.location} (no included "
                "downscaled pair to compare)."
            )
            continue
        delta = float(row.bias_after_day_convention) - pair
        lines.append(
            f"- Exception: raw_grid at {row.location} is NOT part of that agreement "
            f"(final {row.bias_after_day_convention:+.2f} °C vs {pair:+.2f} °C "
            f"downscaled, Δ {delta:+.2f} °C); its grid cell is water-masked "
            f"({row.source_elevation_m:g} m) so the tracks read different cells. "
            "It is excluded from the raw_grid mean above, not averaged in."
        )
    return lines


def render_decomposition_section(
    t2m_table: pd.DataFrame,
    precip_table: pd.DataFrame,
    crosscheck: pd.DataFrame | None = None,
    freshness: dict[str, pd.Timestamp] | None = None,
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
        "2. **elevation** — lapse-rate correction (6.5 °C/km) from the series' "
        "source elevation to station elevation",
        "3. **sampling** — constant mean correction from a parabolic peak fit "
        "to recent hourly ERA5 (sub-hourly max missing from hourly-sampled daily max)",
        "4. **day_convention** — best lag in {−1, 0, +1} days minimizing MAE",
        "",
        "Open-Meteo applies statistical downscaling to the 90 m DEM elevation "
        "of the requested point by default (docs: parameter `elevation`). Two "
        "tracks are therefore reported per location:",
        "",
        "- **downscaled** — the stored connector series; source elevation = "
        "the DEM elevation the downscaling targeted (`dem_elevation_m`).",
        "- **raw_grid** — refetched with `elevation=nan` (downscaling off); "
        "source elevation = average ERA5 grid-cell orography "
        "(`grid_elevation_m`).",
        "",
    ]
    if t2m_table.empty:
        lines.append("_No overlapping t2m_max rows; decomposition skipped._")
    else:
        display = t2m_table.copy()
        if "exclusion_reason" in display.columns:
            display = display.drop(columns=["exclusion_reason"])
        for column in (
            "bias_raw",
            "bias_after_elevation",
            "bias_after_sampling",
            "bias_after_day_convention",
            "source_elevation_m",
            "dem_elevation_m",
            "grid_elevation_m",
            "station_elevation_m",
            "elevation_diff_m",
            "sampling_correction_c",
            "lag_mae",
        ):
            if column in display.columns:
                display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
        if "best_day_lag" in display.columns:
            lag = pd.to_numeric(display["best_day_lag"], errors="coerce").astype("Int64")
            display["best_day_lag"] = lag
        lines.append(_markdown_table(display))
        lines += _excluded_track_lines(t2m_table)

    lines += [
        "",
        "## Orography check — precip (Salta, Ushuaia)",
        "",
        "Total ERA5/GHCN precip ratio with grid-vs-station elevation gap "
        "(grid elevation from an `elevation=nan` request, i.e. real ERA5 "
        "grid-cell orography). A high ratio with a high grid cell is "
        "consistent with orographic enhancement; it does not prove it.",
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

    lines += _crosscheck_section(crosscheck)
    lines.append(render_honest_reading(t2m_table, crosscheck, freshness=freshness))
    return "\n".join(lines)


def _crosscheck_section(crosscheck: pd.DataFrame | None) -> list[str]:
    if crosscheck is None or crosscheck.empty:
        return [
            "",
            "## Station cross-check (GHCN config vs SMN list)",
            "",
            "_SMN station list not available; cross-check skipped. Bias below "
            "is not attributed to ERA5 before this check._",
        ]
    if "flags" in crosscheck:
        flagged = crosscheck.loc[~crosscheck["flags"].eq("")]
    else:
        flagged = crosscheck.iloc[0:0]
    lines = [
        "",
        "## Station cross-check (GHCN config vs SMN list)",
        "",
        "Configured region stations matched against "
        "`data/smn_probe/estaciones/estaciones_smn.txt` (by SMN NRO found "
        "among the 5-digit windows of the GHCN id, rightmost first; fallback "
        "nearest by coordinates). "
        "Flag thresholds: |Δlat| or |Δlon| > 0.05°, |Δelev| > 50 m.",
        "",
    ]
    display = crosscheck.copy()
    for column in display.columns:
        if column.startswith(("delta_", "smn_lat", "smn_lon", "config_lat", "config_lon")):
            display[column] = pd.to_numeric(display[column], errors="coerce").round(4)
        if column in ("smn_elevation_m", "config_elevation_m", "delta_elevation_m"):
            display[column] = pd.to_numeric(display[column], errors="coerce").round(1)
    lines.append(_markdown_table(display))
    lines.append("")
    if flagged.empty:
        lines.append(
            f"All {len(crosscheck)} configured stations matched an SMN entry "
            "within thresholds — no coordinate/elevation mismatch to flag."
        )
    else:
        lines.append(f"**{len(flagged)} station(s) flagged:**")
        for row in flagged.itertuples(index=False):
            lines.append(f"- {row.location}: {row.flags}")
    return lines


def _freshness_line(freshness: dict[str, pd.Timestamp]) -> str:
    era5_last = freshness["era5_last"]
    ghcn_last = freshness["ghcn_last"]
    refreshed = freshness["refreshed"]
    as_of = freshness["as_of"]
    era5_days = int((as_of.normalize() - era5_last.normalize()).days)
    ghcn_days = int((as_of.normalize() - ghcn_last.normalize()).days)
    months = round(ghcn_days / 30.44)
    return (
        f"- Data freshness (ok rows, as of {as_of.date()}): ERA5 through "
        f"{era5_last.date()} ({era5_days} d old); GHCN through "
        f"{ghcn_last.date()} ({ghcn_days} d ≈ {months} months old) although "
        f"both stores were refreshed {refreshed.date()} — the gap is on the "
        "GHCN side, not a stale local cache. The overlap above ends at the "
        "GHCN end date, so recent-forecast verification in Phase 1 depends on "
        "the SMN Argentina connector until GHCN-Daily updates "
        "(audit: `results/qc/freshness.md`)."
    )


def render_honest_reading(
    t2m_table: pd.DataFrame,
    crosscheck: pd.DataFrame | None = None,
    freshness: dict[str, pd.Timestamp] | None = None,
) -> str:
    """Honest reading computed from the decomposition table (never hand-edited)."""
    lines = [
        "",
        "## Honest reading",
        "",
        "- An earlier version of this step used Open-Meteo's default "
        "`elevation` response field as \"grid orography\". That field is the "
        "90 m DEM elevation used for statistical downscaling, not ERA5 model "
        "orography, so the previous elevation gap was not an ERA5 orographic "
        "signal. This report uses `elevation=nan` requests for real "
        "grid-cell heights.",
    ]
    if freshness:
        lines.append(_freshness_line(freshness))
    if crosscheck is not None and not crosscheck.empty:
        if "flags" in crosscheck:
            flagged = crosscheck.loc[~crosscheck["flags"].eq("")]
        else:
            flagged = crosscheck.iloc[0:0]
        if flagged.empty:
            lines.append(
                "- All configured stations match the SMN list within "
                "0.05° / 50 m, so the residual below is not attributable to a "
                "misplaced station coordinate in the region config."
            )
        else:
            names = ", ".join(str(loc) for loc in flagged["location"])
            lines.append(
                f"- Station metadata mismatches flagged before interpreting "
                f"the bias: {names}. See the cross-check table above; residual "
                "bias at those stations may reflect metadata, not ERA5."
            )

    if (
        t2m_table.empty
        or "bias_after_day_convention" not in t2m_table.columns
        or "series" not in t2m_table.columns
    ):
        lines.append("- Decomposition table empty; no residual statement made.")
        return "\n".join(lines)

    for label in ("downscaled", "raw_grid"):
        track = t2m_table.loc[t2m_table["series"].eq(label)]
        if track.empty:
            continue
        included = _included(track)
        excluded_n = len(track) - len(included)
        if included.empty:
            lines.append(f"- **{label}**: all {len(track)} track rows excluded; no mean reported.")
            continue
        raw_mean = float(included["bias_raw"].mean())
        elev_mean = float(included["bias_after_elevation"].mean())
        final_mean = float(included["bias_after_day_convention"].mean())
        note = f"; {excluded_n} excluded" if excluded_n else ""
        lines.append(
            f"- **{label}** (n={len(included)} stations{note}): mean bias raw "
            f"{raw_mean:+.2f} °C → after elevation {elev_mean:+.2f} °C → after "
            f"sampling + day convention {final_mean:+.2f} °C."
        )

    lines += _convergence_lines(t2m_table)

    finals = pd.to_numeric(
        _included(t2m_table)["bias_after_day_convention"], errors="coerce"
    )
    if finals.notna().any() and float(finals.mean()) < -0.5:
        lines.append(
            "- The residual cold bias persists on both series after all three "
            "adjustments. It is reported as an **observed ERA5 bias of these "
            "grid values at these stations**; no causal claim is made here."
        )
    elif finals.notna().any():
        lines.append(
            "- After all adjustments the mean residual is within ±0.5 °C; no "
            "systematic cold bias statement is made."
        )
    return "\n".join(lines) + "\n"


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

    region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
    crosscheck: pd.DataFrame | None = None
    catalogue_path = root / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
    if catalogue_path.exists():
        from .station_crosscheck import crosscheck_region, parse_smn_estaciones

        print("cross-checking configured stations against SMN catalogue…")
        crosscheck = crosscheck_region(region, parse_smn_estaciones(catalogue_path))
        stations_dir = root / "results" / "stations"
        stations_dir.mkdir(parents=True, exist_ok=True)
        crosscheck.to_csv(stations_dir / "ghcn_vs_smn.csv", index=False)
        (stations_dir / "ghcn_vs_smn.md").write_text(
            crosscheck_markdown(
                crosscheck, generated_at=utc_now(), region_id=region["id"]
            ),
            encoding="utf-8",
        )
        print(f"{len(crosscheck)} stations, {int(crosscheck['flags'].ne('').sum())} flagged")

    decomposition_section = ""
    if not args.skip_decomposition:
        era5_last = era5.loc[era5["quality_flag"].eq("ok"), "time"].max()
        ghcn_last = ghcn.loc[ghcn["quality_flag"].eq("ok"), "time"].max()
        refreshed = max(
            pd.to_datetime(era5["retrieved_at"]).max(),
            pd.to_datetime(ghcn["retrieved_at"]).max(),
        )
        freshness: dict[str, pd.Timestamp] | None = None
        if pd.notna(era5_last) and pd.notna(ghcn_last) and pd.notna(refreshed):
            freshness = {
                "era5_last": era5_last,
                "ghcn_last": ghcn_last,
                "refreshed": refreshed,
                "as_of": utc_now(),
            }
        print("collecting t2m_max bias decomposition (network)…")
        t2m_table = collect_t2m_max_decomposition(era5, ghcn, region)
        print("collecting precip orography check (network)…")
        precip_table = collect_precip_orography(era5, ghcn, region)
        decomposition_section = render_decomposition_section(
            t2m_table, precip_table, crosscheck, freshness=freshness
        )
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
