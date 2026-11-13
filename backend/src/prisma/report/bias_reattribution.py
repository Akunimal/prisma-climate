"""Bias re-attribution across the GHCN and SMN legs (T26a steps 1.1–1.3).

Always produced by this script into ``results/discrepancies/``, never
hand-edited:

- ``bias_reattribution.{csv,md}`` — every region station × ``t2m_max`` /
  ``t2m_min`` with the ERA5−station bias of **both legs side by side**, each
  bias normalized to **ERA5 − station** (the committed ``smn_vs_era5.csv``
  stores SMN − ERA5; its sign is flipped here), plus n_days, paired window and
  correlation per leg and the cross-leg bias difference. The Markdown declares
  the period confounder (1.2) and re-derives the leg summary counts honestly.
- ``bias_per_year_ghcn.csv`` — ERA5−GHCN ``t2m_max`` bias per station per
  calendar year 1996–2025 (1.3a).
- ``bias_matched_calendar.csv`` — the matched-calendar adjacent control (1.3b):
  the same calendar span of the GHCN leg one year before the SMN capture
  window, both legs scored over their own window with n_days reported.

Diagnostic, not skill: no CRPS/Brier/reliability number exists here before
the 15-issue-date gate in ``docs/EVALUATION_PROTOCOL.md``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import pandas as pd

from ..ingest.base import find_repo_root, load_region, utc_now
from .discrepancies import CORRELATION_FLAG, TEMP_BIAS_FLAG_C
from .smn_leg import (
    build_smn_frame,
    parse_catalogue_nro_names,
    parse_regtemp,
    resolve_region_stations,
)

LEG_COLUMNS = [
    "location",
    "variable",
    "n_days",
    "first_day",
    "last_day",
    "bias_era5_minus_station",
    "corr",
    "mean_era5",
    "mean_station",
    "flags",
]

# 1.3b matched-calendar adjacent windows (fixed by protocol):
# GHCN-Daily's newest ok row is 2025-08-24, so the GHCN side of the matched
# test ends there; the SMN side uses the identical calendar span of the
# capture year. One year apart, same months and days.
GHCN_MATCHED_WINDOW = ("2024-11-11", "2025-08-24")
SMN_MATCHED_WINDOW = ("2025-11-11", "2026-08-24")

TEMP_VARIABLES = ("t2m_max", "t2m_min")


def _ok_values(frame: pd.DataFrame, value_name: str) -> pd.DataFrame:
    rows = frame.loc[
        frame["quality_flag"].eq("ok") & frame["variable"].isin(TEMP_VARIABLES),
        ["location", "variable", "time", "value"],
    ].copy()
    rows["time"] = pd.to_datetime(rows["time"]).dt.normalize()
    return rows.rename(columns={"value": value_name})


def pair_era5_station(
    era5: pd.DataFrame,
    station: pd.DataFrame,
    station_label: str,
) -> pd.DataFrame:
    """Inner-join ERA5 with a station frame on (location, variable, local day)."""
    left = _ok_values(era5, "era5")
    right = _ok_values(station, "station")
    paired = left.merge(right, on=["location", "variable", "time"], how="inner")
    paired.attrs["station_label"] = station_label
    return paired


def leg_table(paired: pd.DataFrame) -> pd.DataFrame:
    """Per (location, variable) leg stats; bias is ERA5 − station throughout."""
    if paired.empty:
        return pd.DataFrame(columns=LEG_COLUMNS)
    records: list[dict[str, Any]] = []
    for (location, variable), group in paired.groupby(["location", "variable"], sort=True):
        group = group.sort_values("time")
        diff = group["era5"] - group["station"]
        n_days = len(group)
        corr = group["era5"].corr(group["station"]) if n_days > 2 else float("nan")
        bias = float(diff.mean())
        flags: list[str] = []
        if abs(bias) >= TEMP_BIAS_FLAG_C:
            flags.append(f"|bias| >= {TEMP_BIAS_FLAG_C:g} C")
        if corr == corr and corr < CORRELATION_FLAG:
            flags.append(f"corr < {CORRELATION_FLAG:g}")
        records.append(
            {
                "location": location,
                "variable": variable,
                "n_days": n_days,
                "first_day": str(group["time"].iloc[0].date()),
                "last_day": str(group["time"].iloc[-1].date()),
                "bias_era5_minus_station": bias,
                "corr": float(corr) if corr == corr else float("nan"),
                "mean_era5": float(group["era5"].mean()),
                "mean_station": float(group["station"].mean()),
                "flags": "; ".join(flags),
            }
        )
    return pd.DataFrame.from_records(records)


def build_reattribution(ghcn_leg: pd.DataFrame, smn_leg: pd.DataFrame) -> pd.DataFrame:
    """Both legs side by side on (location, variable), signs normalized."""
    ghcn = ghcn_leg.rename(
        columns={
            "n_days": "n_days_ghcn",
            "first_day": "first_day_ghcn",
            "last_day": "last_day_ghcn",
            "bias_era5_minus_station": "bias_era5_minus_ghcn",
            "corr": "corr_ghcn",
            "mean_era5": "mean_era5_ghcn",
            "mean_station": "mean_ghcn",
            "flags": "flags_ghcn",
        }
    )
    smn = smn_leg.rename(
        columns={
            "n_days": "n_days_smn",
            "first_day": "first_day_smn",
            "last_day": "last_day_smn",
            "bias_era5_minus_station": "bias_era5_minus_smn",
            "corr": "corr_smn",
            "mean_era5": "mean_era5_smn",
            "mean_station": "mean_smn",
            "flags": "flags_smn",
        }
    )
    merged = ghcn.merge(smn, on=["location", "variable"], how="outer")
    merged["bias_diff_ghcn_minus_smn"] = (
        merged["bias_era5_minus_ghcn"] - merged["bias_era5_minus_smn"]
    )
    merged["mean_era5_diff_windows"] = merged["mean_era5_ghcn"] - merged["mean_era5_smn"]
    return merged.sort_values(["location", "variable"]).reset_index(drop=True)


def per_year_bias(paired_ghcn: pd.DataFrame) -> pd.DataFrame:
    """1.3a: ERA5−GHCN t2m_max bias per station per calendar year."""
    subset = paired_ghcn.loc[paired_ghcn["variable"].eq("t2m_max")].copy()
    subset["year"] = subset["time"].dt.year
    records: list[dict[str, Any]] = []
    for (location, year), group in subset.groupby(["location", "year"], sort=True):
        diff = group["era5"] - group["station"]
        records.append(
            {
                "location": location,
                "year": int(year),
                "n_days": int(len(group)),
                "bias_era5_minus_ghcn": float(diff.mean()),
                "first_day": str(group["time"].min().date()),
                "last_day": str(group["time"].max().date()),
            }
        )
    return pd.DataFrame.from_records(records)


def matched_calendar_table(
    paired_ghcn: pd.DataFrame,
    paired_smn: pd.DataFrame,
    *,
    ghcn_window: tuple[str, str] = GHCN_MATCHED_WINDOW,
    smn_window: tuple[str, str] = SMN_MATCHED_WINDOW,
) -> pd.DataFrame:
    """1.3b: both legs scored over the same calendar span, one year apart."""
    ghcn_span = paired_ghcn.loc[
        paired_ghcn["time"].between(pd.Timestamp(ghcn_window[0]), pd.Timestamp(ghcn_window[1]))
    ]
    smn_span = paired_smn.loc[
        paired_smn["time"].between(pd.Timestamp(smn_window[0]), pd.Timestamp(smn_window[1]))
    ]
    ghcn_stats = leg_table(ghcn_span).rename(
        columns={
            "n_days": "n_days_ghcn",
            "bias_era5_minus_station": "bias_era5_minus_ghcn",
            "corr": "corr_ghcn",
            "flags": "flags_ghcn",
        }
    )[
        [
            "location",
            "variable",
            "n_days_ghcn",
            "bias_era5_minus_ghcn",
            "corr_ghcn",
            "flags_ghcn",
        ]
    ]
    smn_stats = leg_table(smn_span).rename(
        columns={
            "n_days": "n_days_smn",
            "bias_era5_minus_station": "bias_era5_minus_smn",
            "corr": "corr_smn",
            "flags": "flags_smn",
        }
    )[
        [
            "location",
            "variable",
            "n_days_smn",
            "bias_era5_minus_smn",
            "corr_smn",
            "flags_smn",
        ]
    ]
    merged = ghcn_stats.merge(smn_stats, on=["location", "variable"], how="outer")
    merged["bias_diff_ghcn_minus_smn"] = (
        merged["bias_era5_minus_ghcn"] - merged["bias_era5_minus_smn"]
    )
    merged["ghcn_window"] = f"{ghcn_window[0]}..{ghcn_window[1]}"
    merged["smn_window"] = f"{smn_window[0]}..{smn_window[1]}"
    return merged.sort_values(["location", "variable"]).reset_index(drop=True)


def overlap_days(paired_ghcn: pd.DataFrame, paired_smn: pd.DataFrame) -> int:
    """Local-calendar days present in both legs' station data (1.2 evidence)."""
    if paired_ghcn.empty or paired_smn.empty:
        return 0
    ghcn_days = set(paired_ghcn["time"])
    smn_days = set(paired_smn["time"])
    return len(ghcn_days & smn_days)


def _md_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        cells = ["" if pd.isna(value) else str(value) for value in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _display(frame: pd.DataFrame, columns: list[str], round_cols: list[str]) -> pd.DataFrame:
    display = frame[columns].copy()
    for column in round_cols:
        display[column] = pd.to_numeric(display[column], errors="coerce").round(2)
    return display


def _leg_summary(table: pd.DataFrame, variable: str) -> list[str]:
    subset = table.loc[table["variable"].eq(variable)]
    if subset.empty:
        return [f"- {variable}: no paired rows in either leg."]
    ghcn = subset["bias_era5_minus_ghcn"].dropna()
    smn = subset["bias_era5_minus_smn"].dropna()
    return [
        f"- **{variable}** — GHCN leg: mean bias {ghcn.mean():+.2f} °C, "
        f"median {ghcn.median():+.2f} °C, "
        f"{int((ghcn.abs() >= TEMP_BIAS_FLAG_C).sum())}/{len(ghcn)} stations "
        f"with |bias| >= {TEMP_BIAS_FLAG_C:g} °C; SMN leg: mean bias "
        f"{smn.mean():+.2f} °C, median {smn.median():+.2f} °C, "
        f"{int((smn.abs() >= TEMP_BIAS_FLAG_C).sum())}/{len(smn)} stations "
        f"with |bias| >= {TEMP_BIAS_FLAG_C:g} °C.",
        f"- Cross-leg bias difference ({variable}, ghcn − smn): mean "
        f"{(subset['bias_diff_ghcn_minus_smn']).mean():+.2f} °C, "
        f"range {subset['bias_diff_ghcn_minus_smn'].min():+.2f} to "
        f"{subset['bias_diff_ghcn_minus_smn'].max():+.2f} °C — "
        "**period-confounded, not a like-for-like contrast** (see below).",
    ]


def render_markdown(
    reattribution: pd.DataFrame,
    per_year: pd.DataFrame,
    matched: pd.DataFrame,
    *,
    shared_days: int,
    generated_at: pd.Timestamp,
) -> str:
    ghcn_period = _leg_window(reattribution, "ghcn")
    smn_period = _leg_window(reattribution, "smn")
    flagged_ghcn = int(
        reattribution.loc[
            reattribution["flags_ghcn"].fillna("").ne("")  # type: ignore[union-attr]
            & reattribution["bias_era5_minus_ghcn"].notna()
        ].shape[0]
    )
    flagged_smn = int(
        reattribution.loc[
            reattribution["flags_smn"].fillna("").ne("")  # type: ignore[union-attr]
            & reattribution["bias_era5_minus_smn"].notna()
        ].shape[0]
    )

    lines = [
        "# Bias re-attribution — both legs, sign normalized to ERA5 − station",
        "",
        f"Generated by `python -m prisma.report.bias_reattribution` on "
        f"{generated_at} (UTC).",
        "",
        "- **Sign convention:** every bias is **ERA5 − station** (positive = "
        "ERA5 warmer). The committed `smn_vs_era5.csv` stores SMN − ERA5; "
        "its sign is flipped here. The GHCN leg (`era5_vs_ghcn.csv`) already "
        "uses ERA5 − station, so both legs are directly comparable in sign.",
        "- Means and biases are taken over each leg's own paired "
        "local-calendar days; no day is filled or carried forward.",
        "- Diagnostic, not skill: flags are |bias| >= "
        f"{TEMP_BIAS_FLAG_C:g} °C or corr < {CORRELATION_FLAG:g}; no "
        "CRPS/Brier/reliability number exists before the 15-issue-date gate "
        "(`docs/EVALUATION_PROTOCOL.md`).",
        "",
        "## The period confounder (declared, not waved away)",
        "",
        f"- GHCN leg: **{ghcn_period}** — 30 years of history ending when the "
        "GHCN-Daily source ends (newest ok row 2025-08-24; "
        "`results/qc/freshness.md`).",
        f"- SMN leg: **{smn_period}** — the gitignored regtemp capture window "
        "(retrieved 2026-11-12, served window 2025-11-11 → 2026-11-10).",
        f"- Station-days present in **both** legs: **{shared_days}** "
        "(the windows are disjoint: the SMN capture starts after the GHCN "
        "record ends).",
        "- Consequence: the two legs' biases are estimates of different "
        "periods. Any difference between them mixes source behaviour with "
        "whatever changed between the windows (climatology, station "
        "maintenance, source versioning). The controls below are the honest "
        "way to bound that; the raw cross-leg difference is reported but must "
        "not be read as 'source X improved'.",
        "",
        "## Re-attribution table (full precision in the CSV)",
        "",
    ]
    lines.append(
        _md_table(
            _display(
                reattribution,
                [
                    "location",
                    "variable",
                    "n_days_ghcn",
                    "bias_era5_minus_ghcn",
                    "corr_ghcn",
                    "n_days_smn",
                    "bias_era5_minus_smn",
                    "corr_smn",
                    "bias_diff_ghcn_minus_smn",
                    "flags_ghcn",
                    "flags_smn",
                ],
                [
                    "bias_era5_minus_ghcn",
                    "corr_ghcn",
                    "bias_era5_minus_smn",
                    "corr_smn",
                    "bias_diff_ghcn_minus_smn",
                ],
            )
        )
    )
    lines += [
        "",
        "## Leg summary (honest re-derivation)",
        "",
    ]
    lines += _leg_summary(reattribution, "t2m_max")
    lines += _leg_summary(reattribution, "t2m_min")
    lines += [
        "",
        f"- Flagged rows: **{flagged_ghcn}** in the GHCN leg, "
        f"**{flagged_smn}** in the SMN leg (row = location × variable; "
        "flags are listed per leg in the table).",
        "",
        "## Period control 1.3a — ERA5−GHCN t2m_max bias per calendar year",
        "",
        f"Per station per year in `bias_per_year_ghcn.csv` "
        f"({len(per_year)} rows, years "
        f"{int(per_year['year'].min())}–{int(per_year['year'].max())}, "
        "n_days per station-year reported — short years are source gaps, "
        "never filled).",
        "",
        _md_table(
            _display(
                per_year.groupby("year", as_index=False)
                .agg(
                    stations=("location", "nunique"),
                    mean_bias=("bias_era5_minus_ghcn", "mean"),
                    min_bias=("bias_era5_minus_ghcn", "min"),
                    max_bias=("bias_era5_minus_ghcn", "max"),
                )
                .round(2),
                [
                    "year",
                    "stations",
                    "mean_bias",
                    "min_bias",
                    "max_bias",
                ],
                [],
            )
        ),
        "",
        "## Period control 1.3b — matched-calendar adjacent",
        "",
        "Same calendar span on both legs, one year apart: GHCN "
        f"`{GHCN_MATCHED_WINDOW[0]}..{GHCN_MATCHED_WINDOW[1]}` vs SMN "
        f"`{SMN_MATCHED_WINDOW[0]}..{SMN_MATCHED_WINDOW[1]}` "
        "(GHCN's newest ok row is 2025-08-24, so the matched span stops "
        "there; n_days per station and leg are in the table — a station with "
        "fewer days shows the gap rather than a filled window).",
        "",
        _md_table(
            _display(
                matched,
                [
                    "location",
                    "variable",
                    "n_days_ghcn",
                    "bias_era5_minus_ghcn",
                    "n_days_smn",
                    "bias_era5_minus_smn",
                    "bias_diff_ghcn_minus_smn",
                ],
                [
                    "bias_era5_minus_ghcn",
                    "bias_era5_minus_smn",
                    "bias_diff_ghcn_minus_smn",
                ],
            )
        ),
        "",
        "## What this does not show",
        "",
        "- No forecast is involved: source-vs-source comparison only, not "
        "verification (Phase 1, 15-issue-date gate).",
        "- The matched-calendar control aligns the windows, not the "
        "instruments: GHCN is a station aggregate with its own QC, SMN "
        "regtemp is served as-is (no QC pass in this leg).",
        "- A flag is a prompt to investigate, not proof of an error in "
        "either source.",
        "",
    ]
    return "\n".join(lines)


def _leg_window(table: pd.DataFrame, leg: str) -> str:
    firsts = table[f"first_day_{leg}"].dropna()
    lasts = table[f"last_day_{leg}"].dropna()
    if firsts.empty:
        return "no paired days"
    return f"{min(firsts)} → {max(lasts)}"


def main(argv: list[str] | None = None) -> int:
    root = find_repo_root()
    parser = argparse.ArgumentParser(prog="python -m prisma.report.bias_reattribution")
    parser.add_argument(
        "--era5",
        type=Path,
        default=root / "data" / "raw" / "openmeteo-era5.parquet",
    )
    parser.add_argument(
        "--ghcn",
        type=Path,
        default=root / "data" / "raw" / "ghcn-daily.parquet",
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
    ghcn = pd.read_parquet(args.ghcn)
    era5["time"] = pd.to_datetime(era5["time"])
    ghcn["time"] = pd.to_datetime(ghcn["time"])

    region = load_region(root / "configs" / "regions" / f"{args.region}.yaml")
    smn_frame = pd.DataFrame(
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
    shared_days = 0
    if args.regtemp.is_file():
        regtemp = parse_regtemp(args.regtemp)
        catalogue_path = root / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
        catalogue = (
            parse_catalogue_nro_names(catalogue_path) if catalogue_path.exists() else {}
        )
        resolution = resolve_region_stations(region, catalogue, set(regtemp["regtemp_name"]))
        smn_frame = build_smn_frame(regtemp, resolution)

    paired_ghcn = pair_era5_station(era5, ghcn, "ghcn")
    paired_smn = pair_era5_station(era5, smn_frame, "smn")

    ghcn_leg = leg_table(paired_ghcn)
    smn_leg = leg_table(paired_smn)
    reattribution = build_reattribution(ghcn_leg, smn_leg)
    per_year = per_year_bias(paired_ghcn)
    matched = matched_calendar_table(paired_ghcn, paired_smn)
    shared_days = overlap_days(paired_ghcn, paired_smn)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    reattribution.to_csv(args.out_dir / "bias_reattribution.csv", index=False)
    per_year.to_csv(args.out_dir / "bias_per_year_ghcn.csv", index=False)
    matched.to_csv(args.out_dir / "bias_matched_calendar.csv", index=False)
    (args.out_dir / "bias_reattribution.md").write_text(
        render_markdown(
            reattribution,
            per_year,
            matched,
            shared_days=shared_days,
            generated_at=utc_now(),
        ),
        encoding="utf-8",
    )
    print(
        f"{len(reattribution)} reattribution rows, {len(per_year)} per-year rows, "
        f"{len(matched)} matched rows, shared days={shared_days} -> "
        f"{(args.out_dir / 'bias_reattribution.csv').relative_to(root)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
