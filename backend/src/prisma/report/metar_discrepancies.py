"""METAR vs ERA5 observational discrepancy diagnostic (Horizon 2).

Quantifies observational discrepancy and systematic bias between aerodrome METAR
observations and the ERA5 reanalysis reference across configured worldwide stations:
- Station-level bias (mean difference METAR - ERA5), MAE, RMSE, Pearson correlation.
- Flags large temperature discrepancy (|bias| >= 3.0 C) and poor correlation (corr < 0.90).
- Regional breakdowns across active regions.
- Deterministic CSV, JSON summary, and Markdown report under results/discrepancies/.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..ingest.base import find_repo_root, load_all_regions

TEMP_BIAS_FLAG_C = 3.0
CORRELATION_FLAG = 0.90
MIN_SAMPLE_DAYS = 5
SCHEMA_VERSION = "1.0"
ROUND_DIGITS = 3


def _rounded(val: Any) -> float | None:
    if val is None or pd.isna(val):
        return None
    try:
        f = float(val)
        return round(f, ROUND_DIGITS) if np.isfinite(f) else None
    except (TypeError, ValueError):
        return None


def _flags(bias: float | None, corr: float | None, n_days: int) -> str:
    notes: list[str] = []
    if bias is not None and abs(bias) >= TEMP_BIAS_FLAG_C:
        notes.append(f"|bias| >= {TEMP_BIAS_FLAG_C:g} C")
    if corr is not None and np.isfinite(corr) and corr < CORRELATION_FLAG:
        notes.append(f"corr < {CORRELATION_FLAG:g}")
    if n_days < MIN_SAMPLE_DAYS:
        notes.append(f"n_days < {MIN_SAMPLE_DAYS}")
    return "; ".join(notes)


def _station_lookup(stations: Sequence[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    if not stations:
        return {}
    lookup: dict[str, dict[str, Any]] = {}
    for st in stations:
        name = str(st.get("name", ""))
        lookup[name] = st
        if "id" in st:
            lookup[str(st["id"])] = st
    return lookup


def compare_metar_era5(
    metar_frame: pd.DataFrame,
    era5_frame: pd.DataFrame,
    *,
    stations: Sequence[dict[str, Any]] | None = None,
) -> pd.DataFrame:
    """Compare METAR and ERA5 frames on (location, variable, time)."""
    columns_needed = ["location", "variable", "time", "value"]
    if metar_frame.empty or era5_frame.empty:
        return pd.DataFrame(
            columns=[
                "location",
                "region",
                "icao",
                "variable",
                "n_days",
                "bias",
                "mae",
                "rmse",
                "corr",
                "p95_abs_diff",
                "mean_metar",
                "mean_era5",
                "flags",
            ]
        )

    m_work = metar_frame.copy()
    if "quality_flag" in m_work.columns:
        m_valid = m_work["quality_flag"].isin(["ok", "valid"]) | m_work["quality_flag"].isna()
        m_work = m_work.loc[m_valid]
    e_work = era5_frame.copy()
    if "quality_flag" in e_work.columns:
        e_valid = e_work["quality_flag"].isin(["ok", "valid"]) | e_work["quality_flag"].isna()
        e_work = e_work.loc[e_valid]

    for df in (m_work, e_work):
        for col in columns_needed:
            if col not in df.columns:
                raise ValueError(f"required column '{col}' missing from frame")
        df["time"] = pd.to_datetime(df["time"]).dt.normalize()

    merged = m_work[columns_needed].merge(
        e_work[columns_needed],
        on=["location", "variable", "time"],
        how="inner",
        suffixes=("_metar", "_era5"),
    )

    if merged.empty:
        return pd.DataFrame(
            columns=[
                "location",
                "region",
                "icao",
                "variable",
                "n_days",
                "bias",
                "mae",
                "rmse",
                "corr",
                "p95_abs_diff",
                "mean_metar",
                "mean_era5",
                "flags",
            ]
        )

    st_map = _station_lookup(stations)

    records: list[dict[str, Any]] = []
    for (location, variable), group in merged.groupby(["location", "variable"], sort=True):
        m_vals = group["value_metar"].dropna().astype(float)
        e_vals = group["value_era5"].dropna().astype(float)
        valid = m_vals.index.intersection(e_vals.index)
        if len(valid) == 0:
            continue
        m_sub = m_vals.loc[valid]
        e_sub = e_vals.loc[valid]
        diff = m_sub - e_sub
        n = len(diff)

        bias = float(diff.mean())
        mae = float(diff.abs().mean())
        rmse = float((diff.pow(2).mean()) ** 0.5)
        has_std = m_sub.std() > 1e-6 and e_sub.std() > 1e-6
        corr = float(m_sub.corr(e_sub)) if n > 2 and has_std else None
        p95 = float(diff.abs().quantile(0.95)) if n > 0 else None

        st_info = st_map.get(str(location), {})
        region = st_info.get("region", "global")
        icao = st_info.get("icao", "")

        record = {
            "location": str(location),
            "region": str(region),
            "icao": str(icao) if icao else "",
            "variable": str(variable),
            "n_days": int(n),
            "bias": _rounded(bias),
            "mae": _rounded(mae),
            "rmse": _rounded(rmse),
            "corr": _rounded(corr),
            "p95_abs_diff": _rounded(p95),
            "mean_metar": _rounded(m_sub.mean()),
            "mean_era5": _rounded(e_sub.mean()),
            "flags": _flags(bias, corr, n),
        }
        records.append(record)

    out = pd.DataFrame.from_records(records)
    if out.empty:
        return pd.DataFrame(
            columns=[
                "location",
                "region",
                "icao",
                "variable",
                "n_days",
                "bias",
                "mae",
                "rmse",
                "corr",
                "p95_abs_diff",
                "mean_metar",
                "mean_era5",
                "flags",
            ]
        )
    return out.sort_values(["region", "location", "variable"]).reset_index(drop=True)


def summarize_discrepancies(table: pd.DataFrame) -> dict[str, Any]:
    """Calculate aggregated regional and global summary statistics."""
    if table.empty:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "total_pairs": 0,
            "n_stations": 0,
            "n_flagged": 0,
            "mean_bias": None,
            "mean_mae": None,
            "regions": {},
        }

    total_pairs = int(table["n_days"].sum())
    unique_stations = sorted(table["location"].unique())
    flagged_rows = table.loc[table["flags"].ne("")]
    flagged_stations = sorted(flagged_rows["location"].unique())

    region_stats: dict[str, Any] = {}
    for region_name, r_group in table.groupby("region"):
        r_stations = sorted(r_group["location"].unique())
        r_flagged = sorted(r_group.loc[r_group["flags"].ne(""), "location"].unique())
        region_stats[str(region_name)] = {
            "n_stations": len(r_stations),
            "n_flagged": len(r_flagged),
            "mean_bias": _rounded(r_group["bias"].mean()),
            "mean_mae": _rounded(r_group["mae"].mean()),
            "mean_rmse": _rounded(r_group["rmse"].mean()),
            "flagged_stations": r_flagged,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "total_pairs": total_pairs,
        "n_stations": len(unique_stations),
        "n_flagged": len(flagged_stations),
        "mean_bias": _rounded(table["bias"].mean()),
        "mean_mae": _rounded(table["mae"].mean()),
        "mean_rmse": _rounded(table["rmse"].mean()),
        "regions": region_stats,
    }


def render_markdown_report(
    table: pd.DataFrame,
    summary: dict[str, Any],
    *,
    period_start: str | None = None,
    period_end: str | None = None,
    generated_at: str | None = None,
) -> str:
    """Render structured Markdown discrepancy report."""
    stamp = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if period_start and period_end:
        period_text = f"{period_start} to {period_end}"
    else:
        period_text = "available archive period"

    lines = [
        "# METAR vs ERA5 Observational Discrepancy Report",
        "",
        f"Generated on {stamp} for {period_text}.",
        "",
        "## 1. Executive Summary",
        "",
        f"- **Evaluated stations:** {summary['n_stations']} stations "
        f"across {len(summary['regions'])} active regions.",
        f"- **Total paired station-days:** {summary['total_pairs']:,}.",
        f"- **Global mean bias (METAR − ERA5):** {summary['mean_bias']} °C.",
        f"- **Global mean MAE:** {summary['mean_mae']} °C.",
        f"- **Flagged stations (|bias| ≥ {TEMP_BIAS_FLAG_C} °C or "
        f"corr < {CORRELATION_FLAG}):** {summary['n_flagged']}.",
        "",
        "## 2. Regional Breakdown",
        "",
        "| Region | Stations | Flagged | Mean Bias (°C) | Mean MAE (°C) | Mean RMSE (°C) |",
        "|---|---:|---:|---:|---:|---:|",
    ]

    for reg, stats in summary["regions"].items():
        bias_repr = stats["mean_bias"] if stats["mean_bias"] is not None else "n/a"
        mae_repr = stats["mean_mae"] if stats["mean_mae"] is not None else "n/a"
        rmse_repr = stats["mean_rmse"] if stats["mean_rmse"] is not None else "n/a"
        lines.append(
            f"| `{reg}` | {stats['n_stations']} | {stats['n_flagged']} | "
            f"{bias_repr} | {mae_repr} | {rmse_repr} |"
        )

    lines.extend(
        [
            "",
            "## 3. Station Detail Table",
            "",
            "| Region | Location | ICAO | Variable | Days | Bias (°C) | MAE (°C) | "
            "Corr | Flags |",
            "|---|---|---|---|---:|---:|---:|---:|---|",
        ]
    )

    if table.empty:
        lines.append("| — | — | — | — | 0 | — | — | — | *No overlapping observations* |")
    else:
        for row in table.itertuples(index=False):
            bias_str = f"{row.bias:+.2f}" if row.bias is not None else "—"
            mae_str = f"{row.mae:.2f}" if row.mae is not None else "—"
            corr_str = f"{row.corr:.3f}" if row.corr is not None else "—"
            flags_str = f"`{row.flags}`" if row.flags else "✓ OK"
            lines.append(
                f"| `{row.region}` | {row.location} | `{row.icao}` | `{row.variable}` | "
                f"{row.n_days} | {bias_str} | {mae_str} | {corr_str} | {flags_str} |"
            )

    lines.extend(
        [
            "",
            "## 4. Methodological & Physical Commentary",
            "",
            "- **Observation protocol:** METAR observations are reported hourly/half-hourly "
            "at aerodromes. Daily aggregation extracts local calendar maximum and minimum "
            "temperatures.",
            "- **Reanalysis grid baseline:** ERA5 provides 0.25° grid estimates representing "
            "area-mean surface values rather than airport microclimate points.",
            "- **Known discrepancy factors:**",
            "  1. **Airport heat island / runway thermal absorption:** Aerodromes frequently "
            "exhibit positive daytime temperature offsets relative to regional grid averages.",
            "  2. **Topographic complexity:** Sub-grid elevation differences between aerodrome "
            "runways and smoothed ERA5 orography produce hydrostatic temperature offsets.",
            "  3. **Coastal marine layers:** Coastal airports often measure sharp sea breeze "
            "fronts attenuated in reanalysis models.",
            "",
            "---",
            "*Report generated by `prisma.report.metar_discrepancies`.*",
        ]
    )

    return "\n".join(lines) + "\n"


def write_metar_discrepancy_reports(
    table: pd.DataFrame,
    summary: dict[str, Any],
    out_dir: Path,
    *,
    period_start: str | None = None,
    period_end: str | None = None,
) -> list[Path]:
    """Write CSV, JSON and Markdown discrepancy reports to out_dir."""
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "metar_vs_era5.csv"
    json_path = out_dir / "metar_vs_era5_summary.json"
    md_path = out_dir / "metar_vs_era5.md"

    table.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(
        render_markdown_report(
            table,
            summary,
            period_start=period_start,
            period_end=period_end,
        ),
        encoding="utf-8",
    )
    return [csv_path, json_path, md_path]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="repository root path")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="output directory (default: results/discrepancies)",
    )
    parser.add_argument(
        "--metar-file",
        type=Path,
        default=None,
        help="path to local METAR parquet file",
    )
    parser.add_argument(
        "--era5-file",
        type=Path,
        default=None,
        help="path to local ERA5 parquet file",
    )
    args = parser.parse_args(argv)

    root = args.root if args.root else find_repo_root()
    out_dir = args.out_dir if args.out_dir else root / "results" / "discrepancies"

    region = load_all_regions(root)
    stations = region.get("stations", [])

    metar_path = (
        args.metar_file or (root / "data" / "observations" / "metar" / "metar-global.parquet")
    )
    era5_path = args.era5_file or (root / "data" / "raw" / "openmeteo-era5.parquet")

    if not metar_path.is_file() or not era5_path.is_file():
        print(
            f"notice: metar ({metar_path}) or era5 ({era5_path}) file absent on disk; "
            "skipping live report generation"
        )
        return 0

    metar_df = pd.read_parquet(metar_path)
    era5_df = pd.read_parquet(era5_path)

    table = compare_metar_era5(metar_df, era5_df, stations=stations)
    summary = summarize_discrepancies(table)
    written = write_metar_discrepancy_reports(table, summary, out_dir)
    print(f"wrote {len(written)} files under {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
