"""Run B checkpoint report per docs/EVALUATION_PROTOCOL.md (§6 decision rule).

Computes:
1. Per-station table: pooled CRPSS EMOS & QM, 95% moving-block bootstrap CI
   (block length 7 days, 1000 resamples), improved yes/no, sufficient cells,
   and scored dates.
2. Count of improved stations / denominator (hypothesis holds/fails at X = 60%).
3. Secondary cell-mean CRPSS.
4. Comparison beside Run A.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
HINDCAST_DIR = ROOT / "results" / "hindcast"
REGION_YAML = ROOT / "configs" / "regions" / "argentina.yaml"
RUN_A_CSV = HINDCAST_DIR / "crpss_full_20261115T201137Z.csv"
RUN_A_META = HINDCAST_DIR / "crpss_full_20261115T201137Z.meta.json"


def find_latest_run_b() -> tuple[Path, Path, Path, Path]:
    """Find latest rolling-45 full run files: csv, meta.json, cases.parquet, md."""
    metas = sorted(HINDCAST_DIR.glob("crpss_full_*.meta.json"), key=lambda p: p.stat().st_mtime)
    for meta_path in reversed(metas):
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        if data.get("training") == "rolling-45":
            stem = meta_path.name[:-len(".meta.json")]
            csv_path = HINDCAST_DIR / f"{stem}.csv"
            cases_path = HINDCAST_DIR / f"{stem}.cases.parquet"
            md_path = HINDCAST_DIR / f"{stem}.md"
            if csv_path.exists() and cases_path.exists():
                return csv_path, meta_path, cases_path, md_path
    raise FileNotFoundError("no Run B (training=rolling-45) artifacts found")


def load_station_names() -> dict[str, str]:
    if not REGION_YAML.exists():
        return {}
    with open(REGION_YAML, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {str(s["id"]): str(s.get("name", s["id"])) for s in data.get("stations", [])}


def moving_block_bootstrap(
    dates: list[str],
    pairs_by_date: dict[str, list[tuple[float, float, float]]],
    *,
    block_length: int = 7,
    n_resamples: int = 1000,
    seed: int = 42,
) -> dict[str, tuple[float, float]]:
    """Moving-block bootstrap over issue dates (block length 7, 1000 resamples).

    Returns 95% CI for:
      - diff_emos: mean(crps_emos - crps_raw)
      - diff_qm: mean(crps_qm - crps_raw)
      - crpss_emos: 1 - mean(crps_emos) / mean(crps_raw)
      - crpss_qm: 1 - mean(crps_qm) / mean(crps_raw)
    """
    rng = np.random.default_rng(seed)
    T = len(dates)
    if T == 0:
        nan_ci = (float("nan"), float("nan"))
        return {"diff_emos": nan_ci, "diff_qm": nan_ci, "crpss_emos": nan_ci, "crpss_qm": nan_ci}

    # Construct all overlapping blocks of length block_length
    B = min(block_length, T)
    blocks: list[list[str]] = [dates[i : i + B] for i in range(T - B + 1)]
    if not blocks:
        blocks = [dates]

    n_blocks_to_draw = int(np.ceil(T / B))

    diff_emos_samples = np.empty(n_resamples, dtype=float)
    diff_qm_samples = np.empty(n_resamples, dtype=float)
    crpss_emos_samples = np.empty(n_resamples, dtype=float)
    crpss_qm_samples = np.empty(n_resamples, dtype=float)

    for b in range(n_resamples):
        chosen_indices = rng.integers(0, len(blocks), size=n_blocks_to_draw)
        sample_dates: list[str] = []
        for idx in chosen_indices:
            sample_dates.extend(blocks[idx])
        sample_dates = sample_dates[:T]

        raw_vals: list[float] = []
        emos_vals: list[float] = []
        qm_vals: list[float] = []

        for d in sample_dates:
            for r, e, q in pairs_by_date.get(d, []):
                raw_vals.append(r)
                emos_vals.append(e)
                qm_vals.append(q)

        r_arr = np.array(raw_vals)
        e_arr = np.array(emos_vals)
        q_arr = np.array(qm_vals)

        m_r = np.mean(r_arr)
        m_e = np.mean(e_arr)
        m_q = np.mean(q_arr)

        diff_emos_samples[b] = m_e - m_r
        diff_qm_samples[b] = m_q - m_r
        crpss_emos_samples[b] = 1.0 - m_e / m_r if m_r != 0 else np.nan
        crpss_qm_samples[b] = 1.0 - m_q / m_r if m_r != 0 else np.nan

    def ci(arr: np.ndarray) -> tuple[float, float]:
        valid = arr[np.isfinite(arr)]
        if len(valid) == 0:
            return (float("nan"), float("nan"))
        return (float(np.percentile(valid, 2.5)), float(np.percentile(valid, 97.5)))

    return {
        "diff_emos": ci(diff_emos_samples),
        "diff_qm": ci(diff_qm_samples),
        "crpss_emos": ci(crpss_emos_samples),
        "crpss_qm": ci(crpss_qm_samples),
    }


def analyze_run_b() -> dict[str, Any]:
    csv_path, meta_path, cases_path, md_path = find_latest_run_b()
    cells = pd.read_csv(csv_path)
    cases = pd.read_parquet(cases_path)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    station_names = load_station_names()

    # Identify sufficient cells
    sufficient_cells = set()
    for _, row in cells.iterrows():
        if not bool(row.get("insufficient", False)):
            sufficient_cells.add((str(row["station_id"]), int(row["lead_day"])))

    station_ids = sorted(cells["station_id"].unique())
    station_rows: list[dict[str, Any]] = []

    for sid in station_ids:
        st_cells = cells[cells["station_id"] == sid]
        n_sufficient = int((~st_cells["insufficient"]).sum())
        total_cells = len(st_cells)

        # Cases for sufficient cells only
        is_sufficient = cases.apply(
            lambda r: (str(r["station_id"]), int(r["lead_day"])) in sufficient_cells,
            axis=1,
        )
        st_cases = cases[(cases["station_id"] == sid) & is_sufficient]

        scored_dates = sorted(st_cases["issue_date"].unique())
        n_dates = len(scored_dates)
        n_pairs = len(st_cases)

        if n_pairs == 0 or n_sufficient == 0:
            station_rows.append({
                "station_id": sid,
                "name": station_names.get(sid, sid),
                "n_sufficient": n_sufficient,
                "total_cells": total_cells,
                "n_dates": 0,
                "n_pairs": 0,
                "crps_raw": np.nan,
                "crps_emos": np.nan,
                "crps_qm": np.nan,
                "crpss_emos": np.nan,
                "crpss_qm": np.nan,
                "ci_diff_emos": (np.nan, np.nan),
                "ci_crpss_emos": (np.nan, np.nan),
                "ci_diff_qm": (np.nan, np.nan),
                "ci_crpss_qm": (np.nan, np.nan),
                "improved": False,
            })
            continue

        raw_mean = float(st_cases["crps_raw"].mean())
        emos_mean = float(st_cases["crps_emos"].mean())
        qm_mean = float(st_cases["crps_qm"].mean())

        crpss_emos = 1.0 - emos_mean / raw_mean if raw_mean else np.nan
        crpss_qm = 1.0 - qm_mean / raw_mean if raw_mean else np.nan

        # Prepare dates and pairs
        pairs_by_date: dict[str, list[tuple[float, float, float]]] = {}
        for r in st_cases.itertuples(index=False):
            d = str(r.issue_date)
            pairs_by_date.setdefault(d, []).append(
                (float(r.crps_raw), float(r.crps_emos), float(r.crps_qm))
            )

        boot = moving_block_bootstrap(scored_dates, pairs_by_date)

        # Decision rule: station CRPSS > 0 AND 95% CI of (calibrated - raw)
        # excludes 0 in improving direction (upper bound < 0)
        ci_lower_e, ci_upper_e = boot["diff_emos"]
        improved = bool(crpss_emos > 0 and ci_upper_e < 0)

        station_rows.append({
            "station_id": sid,
            "name": station_names.get(sid, sid),
            "n_sufficient": n_sufficient,
            "total_cells": total_cells,
            "n_dates": n_dates,
            "n_pairs": n_pairs,
            "crps_raw": raw_mean,
            "crps_emos": emos_mean,
            "crps_qm": qm_mean,
            "crpss_emos": crpss_emos,
            "crpss_qm": crpss_qm,
            "ci_diff_emos": boot["diff_emos"],
            "ci_crpss_emos": boot["crpss_emos"],
            "ci_diff_qm": boot["diff_qm"],
            "ci_crpss_qm": boot["crpss_qm"],
            "improved": improved,
        })

    # Denominator: stations with >= 1 sufficient cell
    denom_stations = [s for s in station_rows if s["n_sufficient"] >= 1]
    n_denom = len(denom_stations)
    n_improved = sum(1 for s in denom_stations if s["improved"])
    pct_improved = (n_improved / n_denom * 100.0) if n_denom else 0.0
    holds = pct_improved >= 60.0

    # Secondary cell means
    suff_df = cells[~cells["insufficient"]]
    mean_cell_emos = float(suff_df["crpss_emos_vs_raw"].mean()) if not suff_df.empty else np.nan
    mean_cell_qm = float(suff_df["crpss_qm_vs_raw"].mean()) if not suff_df.empty else np.nan

    # Run A reference
    run_a_cell_emos = np.nan
    run_a_cell_qm = np.nan
    if RUN_A_CSV.exists():
        df_a = pd.read_csv(RUN_A_CSV)
        suff_a = df_a[~df_a["insufficient"]]
        if not suff_a.empty:
            run_a_cell_emos = float(suff_a["crpss_emos_vs_raw"].mean())
            run_a_cell_qm = float(suff_a["crpss_qm_vs_raw"].mean())

    return {
        "csv_path": str(csv_path),
        "meta_path": str(meta_path),
        "cases_path": str(cases_path),
        "meta": meta,
        "stations": station_rows,
        "n_denom": n_denom,
        "n_improved": n_improved,
        "pct_improved": pct_improved,
        "hypothesis_holds": holds,
        "mean_cell_emos": mean_cell_emos,
        "mean_cell_qm": mean_cell_qm,
        "run_a_cell_emos": run_a_cell_emos,
        "run_a_cell_qm": run_a_cell_qm,
    }


if __name__ == "__main__":
    res = analyze_run_b()
    print(f"Artifact: {res['csv_path']}")
    pct_str = f"{res['pct_improved']:.1f}%"
    print(f"Improved stations: {res['n_improved']} / {res['n_denom']} ({pct_str})")
    print(f"Hypothesis (X=60%): {'HOLDS' if res['hypothesis_holds'] else 'FAILS'}")
    emos_str = f"{res['mean_cell_emos']:.4f} (Run A: {res['run_a_cell_emos']:.4f})"
    print(f"Mean cell CRPSS EMOS: {emos_str}")
    qm_str = f"{res['mean_cell_qm']:.4f} (Run A: {res['run_a_cell_qm']:.4f})"
    print(f"Mean cell CRPSS QM:   {qm_str}")
