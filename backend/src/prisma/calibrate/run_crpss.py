"""Phase 2 CRPSS runner: calibrated vs raw GEFS ensemble (hindcast-labelled).

Usage::

    python -m prisma.calibrate.run_crpss            # full default window
    python -m prisma.calibrate.run_crpss --smoke    # tiny real-data path
    python -m prisma.calibrate.run_crpss --synthetic # offline synthetic only

Implements docs/design/HINDCAST.md and docs/EVALUATION_PROTOCOL.md as
amended. Every artifact is labelled ``hindcast`` with provider and
retrieval date (2026-11-11 amendment). This command does **not** write
operational-archive leaderboard numbers; the 15-issue-date gate still
gates Phase 1 publication and is not overridden here.

Train/eval are strictly split by issue date; EMOS and quantile mapping
are fitted on train only (protocol §3, §8 ablation on train window).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from ..hindcast.gefs import (
    HINDCAST_LABEL,
    LEAD_DAYS_DEFAULT,
    MEMBERS,
    PROVIDER,
    StationPoint,
    fetch_member_tmax,
    hindcast_metadata,
    issue_dates_between,
    split_train_eval,
)
from ..ingest.base import find_repo_root, load_yaml
from ..verify.metrics import crps_ensemble, crpss
from .emos import MIN_TRAINING, fit_emos_gaussian
from .quantile_mapping import fit_quantile_mapping

# regtemp capture: 365 local days ending 2026-11-10 (see HINDCAST.md §7).
# Train/eval must fit inside that observation window.
DEFAULT_N_TRAIN = 180
DEFAULT_N_EVAL = 180
OUT_DIR_REL = Path("results") / "hindcast"
CACHE_REL = Path("data") / "cache" / "hindcast"
REGTEMP_REL = Path("data") / "smn_probe" / "regtemp" / "registro_temperatura365d_smn.txt"
CATALOGUE_REL = Path("data") / "smn_probe" / "estaciones" / "estaciones_smn.txt"
REGION_REL = Path("configs") / "regions" / "argentina.yaml"


def load_stations(root: Path) -> list[StationPoint]:
    region = load_yaml(root / REGION_REL)
    return [
        StationPoint(station_id=str(s["id"]), lat=float(s["lat"]), lon=float(s["lon"]))
        for s in region["stations"]
    ]


def load_observations(root: Path) -> pd.DataFrame:
    """Long frame location × variable × time from the regtemp capture."""
    from ..report.smn_leg import (
        build_smn_frame,
        parse_catalogue_nro_names,
        parse_regtemp,
        resolve_region_stations,
    )

    regtemp_path = root / REGTEMP_REL
    catalogue_path = root / CATALOGUE_REL
    region = load_yaml(root / REGION_REL)
    if not regtemp_path.is_file():
        raise FileNotFoundError(f"regtemp capture missing: {regtemp_path}")
    if not catalogue_path.is_file():
        raise FileNotFoundError(f"SMN catalogue missing: {catalogue_path}")
    regtemp = parse_regtemp(regtemp_path)
    catalogue = parse_catalogue_nro_names(catalogue_path)
    resolution = resolve_region_stations(region, catalogue, set(regtemp["regtemp_name"]))
    frame = build_smn_frame(regtemp, resolution)
    if frame.empty:
        raise ValueError("no resolved station-days in regtemp capture")
    return frame


def obs_lookup(frame: pd.DataFrame) -> dict[tuple[str, str, date], float]:
    out: dict[tuple[str, str, date], float] = {}
    for row in frame.itertuples(index=False):
        key = (str(row.location), str(row.variable), pd.Timestamp(row.time).date())
        out[key] = float(row.value)
    return out


def location_to_station_id(root: Path) -> dict[str, str]:
    region = load_yaml(root / REGION_REL)
    return {str(s["name"]): str(s["id"]) for s in region["stations"]}


def score_case(
    members: np.ndarray,
    observation: float,
    *,
    emos_params: Any | None,
    qm: Any | None,
) -> dict[str, float]:
    """Raw fair CRPS + calibrated CRPS for one (members, obs) case."""
    raw = crps_ensemble(members, observation)
    out = {"crps_raw": raw}
    if emos_params is not None:
        ens_mean = float(members.mean())
        ens_std = float(members.std(ddof=1)) if members.size > 1 else 0.0
        mu, sigma = emos_params.predict(ens_mean, ens_std)
        from .emos import crps_gaussian

        out["crps_emos"] = crps_gaussian(observation, mu, sigma)
    if qm is not None:
        mapped = qm.apply(members)
        out["crps_qm"] = crps_ensemble(mapped, observation)
    return out


def aggregate_crpss(raw: np.ndarray, cal: np.ndarray) -> float:
    both = np.isfinite(raw) & np.isfinite(cal)
    if not both.any():
        return float("nan")
    return float(crpss(cal[both], raw[both]))


def fit_calibrators(
    train_members: np.ndarray,
    train_obs: np.ndarray,
) -> tuple[Any, Any]:
    """Fit EMOS on member matrix (n_cases, n_members) and QM on ens_mean."""
    emos = fit_emos_gaussian(train_members, train_obs)
    qm = fit_quantile_mapping(train_members.mean(axis=1), train_obs)
    return emos, qm


def synthetic_dataset(
    n_train: int = 120,
    n_eval: int = 120,
    n_members: int = 31,
    n_stations: int = 3,
    seed: int = 7,
    bias: float = 2.5,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Biased, under-dispersed ensemble → calibration should help (CRPSS > 0)."""
    rng = np.random.default_rng(seed)
    # obs: seasonal-ish + noise
    t = np.arange(n_train + n_eval)
    obs_all = 18.0 + 8.0 * np.sin(2 * np.pi * t / 365.0) + rng.normal(0, 2.0, size=t.size)
    # members around biased truth
    members_all = (
        obs_all[:, None]
        + bias
        + rng.normal(0.0, 1.0, size=(t.size, n_members))
        + rng.normal(0.0, 0.8, size=(t.size, 1))  # common under-dispersion noise
    )
    # tile stations with small offsets
    train_m = np.repeat(members_all[:n_train][None, :, :], n_stations, axis=0)
    eval_m = np.repeat(members_all[n_train:][None, :, :], n_stations, axis=0)
    train_o = np.repeat(obs_all[:n_train][None, :], n_stations, axis=0)
    eval_o = np.repeat(obs_all[n_train:][None, :], n_stations, axis=0)
    # station offsets on obs only (forecast already noisy)
    offsets = np.linspace(-1.0, 1.0, n_stations)[:, None]
    train_o = train_o + offsets
    eval_o = eval_o + offsets
    return train_m, train_o, eval_m, eval_o


def run_synthetic() -> dict[str, Any]:
    train_m, train_o, eval_m, eval_o = synthetic_dataset()
    # train_m: (n_stations, n_train, n_members)
    rows = []
    for si in range(train_m.shape[0]):
        emos, qm = fit_calibrators(train_m[si], train_o[si])
        raw_scores = []
        emos_scores = []
        qm_scores = []
        for j in range(eval_m.shape[1]):
            members = eval_m[si, j]
            obs = float(eval_o[si, j])
            scored = score_case(members, obs, emos_params=emos, qm=qm)
            raw_scores.append(scored["crps_raw"])
            emos_scores.append(scored["crps_emos"])
            qm_scores.append(scored["crps_qm"])
        raw = np.asarray(raw_scores)
        rows.append(
            {
                "station_index": si,
                "n_eval": int(raw.size),
                "crps_raw": float(raw.mean()),
                "crps_emos": float(np.mean(emos_scores)),
                "crps_qm": float(np.mean(qm_scores)),
                "crpss_emos_vs_raw": aggregate_crpss(raw, np.asarray(emos_scores)),
                "crpss_qm_vs_raw": aggregate_crpss(raw, np.asarray(qm_scores)),
            }
        )
    df = pd.DataFrame(rows)
    meta = hindcast_metadata()
    meta["mode"] = "synthetic"
    meta["note"] = "synthetic biased ensemble — not a GEFS score; unit-path only"
    return {"metadata": meta, "cells": df.to_dict(orient="records")}


def _cache_path(root: Path) -> Path:
    return root / CACHE_REL / "gefs_tmax_station.parquet"


def load_cache(root: Path) -> pd.DataFrame:
    path = _cache_path(root)
    if path.is_file():
        return pd.read_parquet(path)
    return pd.DataFrame(
        columns=[
            "issue_date",
            "lead_day",
            "member",
            "station_id",
            "value_c",
            "layout",
            "key",
        ]
    )


def save_cache(root: Path, frame: pd.DataFrame) -> None:
    path = _cache_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def fetch_window(
    root: Path,
    dates: Sequence[date],
    leads: Sequence[int],
    stations: Sequence[StationPoint],
    *,
    refresh: bool = False,
    progress: bool = True,
    max_workers: int = 8,
) -> pd.DataFrame:
    """Fetch (or reuse cache) member × station values for the window."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cache = pd.DataFrame() if refresh else load_cache(root)
    have = set()
    if not cache.empty:
        have = {
            (
                pd.Timestamp(r.issue_date).date(),
                int(r.lead_day),
                str(r.member),
                str(r.station_id),
            )
            for r in cache.itertuples(index=False)
        }
    jobs: list[tuple[date, int, str, list[StationPoint]]] = []
    for issue in dates:
        for lead in leads:
            for member in MEMBERS:
                needed = [
                    st
                    for st in stations
                    if (issue, lead, member, st.station_id) not in have
                ]
                if needed:
                    jobs.append((issue, lead, member, needed))
    total = len(jobs)
    if progress:
        print(f"  pending member-lead slots: {total}", flush=True)
    new_rows: list[dict[str, Any]] = []
    done = 0
    lock_free_append = new_rows.append

    def _one(job: tuple[date, int, str, list[StationPoint]]) -> list[dict[str, Any]]:
        issue, lead, member, needed = job
        fc = fetch_member_tmax(issue, member, lead, needed)
        if fc is None:
            return []
        return [
            {
                "issue_date": issue.isoformat(),
                "lead_day": lead,
                "member": member,
                "station_id": sid,
                "value_c": val,
                "layout": fc.layout,
                "key": fc.key,
            }
            for sid, val in fc.values_c.items()
        ]

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, job): job for job in jobs}
        for fut in as_completed(futures):
            rows = fut.result()
            for row in rows:
                lock_free_append(row)
            done += 1
            if progress and done % 50 == 0:
                print(f"  fetched {done}/{total} member-lead slots", flush=True)
    if new_rows:
        cache = pd.concat([cache, pd.DataFrame(new_rows)], ignore_index=True)
        cache = cache.drop_duplicates(
            subset=["issue_date", "lead_day", "member", "station_id"], keep="last"
        )
        save_cache(root, cache)
    return cache


def evaluate_from_cache(
    cache: pd.DataFrame,
    obs: pd.DataFrame,
    stations: Sequence[StationPoint],
    *,
    n_train: int,
    leads: Sequence[int],
) -> pd.DataFrame:
    """Fit on train dates, score eval dates; one row per station × lead."""
    if cache.empty:
        raise ValueError("empty hindcast cache — nothing to score")
    loc_map = location_to_station_id(find_repo_root())
    # invert: station_id -> location name (region station name)
    id_to_loc = {v: k for k, v in loc_map.items()}
    obs_idx = obs_lookup(obs)

    dates = sorted({pd.Timestamp(d).date() for d in cache["issue_date"].unique()})
    # restrict to dates that have observations for scoring
    train_dates, eval_dates = split_train_eval(dates, n_train)

    station_ids = [st.station_id for st in stations]
    records: list[dict[str, Any]] = []

    for lead in leads:
        for sid in station_ids:
            # build matrices over dates
            def members_on(day: date, _lead: int = lead, _sid: str = sid) -> np.ndarray | None:
                sub = cache[
                    (cache["lead_day"] == _lead)
                    & (cache["station_id"] == _sid)
                    & (cache["issue_date"] == day.isoformat())
                ]
                by = {str(r.member): float(r.value_c) for r in sub.itertuples(index=False)}
                if len(by) < int(np.ceil(len(MEMBERS) * 4 / 5)):
                    return None
                present = [by[m] for m in MEMBERS if m in by]
                return np.asarray(present, dtype=float)

            def obs_on(
                day: date,
                variable: str,
                _lead: int = lead,
                _sid: str = sid,
            ) -> float | None:
                loc = id_to_loc.get(_sid)
                if loc is None:
                    return None
                # valid time for lead L from issue D is D+L (local calendar day)
                valid = day + timedelta(days=_lead)
                return obs_idx.get((loc, variable, valid))

            # use t2m_max as primary target
            variable = "t2m_max"
            train_pairs: list[tuple[np.ndarray, float]] = []
            for day in train_dates:
                m = members_on(day)
                o = obs_on(day, variable)
                if m is None or o is None or not np.isfinite(o):
                    continue
                train_pairs.append((m, float(o)))
            if len(train_pairs) < MIN_TRAINING:
                records.append(
                    {
                        "label": HINDCAST_LABEL,
                        "station_id": sid,
                        "variable": variable,
                        "lead_day": lead,
                        "n_train": len(train_pairs),
                        "n_eval": 0,
                        "insufficient": True,
                        "crps_raw": np.nan,
                        "crps_emos": np.nan,
                        "crps_qm": np.nan,
                        "crpss_emos_vs_raw": np.nan,
                        "crpss_qm_vs_raw": np.nan,
                    }
                )
                continue

            # stack train to (n_cases, n_members) — members may differ in count if
            # some dates missing a few; require common length
            lengths = {m.shape[0] for m, _ in train_pairs}
            if len(lengths) != 1:
                # drop pairs that don't match the modal length
                def _count(L: int, pairs: list[tuple[np.ndarray, float]] = train_pairs) -> int:
                    return sum(1 for m, _ in pairs if m.shape[0] == L)

                modal = max(lengths, key=_count)
                train_pairs = [(m, o) for m, o in train_pairs if m.shape[0] == modal]
            train_members = np.stack([m for m, _ in train_pairs], axis=0)
            train_obs_arr = np.asarray([o for _, o in train_pairs], dtype=float)
            try:
                emos, qm = fit_calibrators(train_members, train_obs_arr)
            except ValueError:
                records.append(
                    {
                        "label": HINDCAST_LABEL,
                        "station_id": sid,
                        "variable": variable,
                        "lead_day": lead,
                        "n_train": len(train_pairs),
                        "n_eval": 0,
                        "insufficient": True,
                        "crps_raw": np.nan,
                        "crps_emos": np.nan,
                        "crps_qm": np.nan,
                        "crpss_emos_vs_raw": np.nan,
                        "crpss_qm_vs_raw": np.nan,
                    }
                )
                continue

            raw_list: list[float] = []
            emos_list: list[float] = []
            qm_list: list[float] = []
            for day in eval_dates:
                m = members_on(day)
                o = obs_on(day, variable)
                if m is None or o is None or not np.isfinite(o):
                    continue
                if m.shape[0] != train_members.shape[1]:
                    continue
                scored = score_case(m, float(o), emos_params=emos, qm=qm)
                raw_list.append(scored["crps_raw"])
                emos_list.append(scored["crps_emos"])
                qm_list.append(scored["crps_qm"])
            n_eval = len(raw_list)
            insufficient = n_eval < 10  # MIN_SAMPLE
            raw = np.asarray(raw_list, dtype=float)
            emos_s = np.asarray(emos_list, dtype=float)
            qm_s = np.asarray(qm_list, dtype=float)
            records.append(
                {
                    "label": HINDCAST_LABEL,
                    "station_id": sid,
                    "variable": variable,
                    "lead_day": lead,
                    "n_train": len(train_pairs),
                    "n_eval": n_eval,
                    "insufficient": insufficient,
                    "crps_raw": float(raw.mean()) if n_eval else np.nan,
                    "crps_emos": float(emos_s.mean()) if n_eval else np.nan,
                    "crps_qm": float(qm_s.mean()) if n_eval else np.nan,
                    "crpss_emos_vs_raw": (
                        np.nan if insufficient else aggregate_crpss(raw, emos_s)
                    ),
                    "crpss_qm_vs_raw": (
                        np.nan if insufficient else aggregate_crpss(raw, qm_s)
                    ),
                }
            )
    return pd.DataFrame.from_records(records)


def write_outputs(
    root: Path,
    cells: pd.DataFrame,
    meta: dict[str, Any],
    *,
    mode: str,
) -> list[Path]:
    out_dir = root / OUT_DIR_REL
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = out_dir / f"crpss_{mode}_{stamp}.csv"
    md_path = out_dir / f"crpss_{mode}_{stamp}.md"
    json_path = out_dir / f"crpss_{mode}_{stamp}.meta.json"
    cells.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    n_cells = len(cells)
    n_ok = (
        int((~cells.get("insufficient", pd.Series([False] * n_cells))).sum())
        if n_cells
        else 0
    )

    def _mean(col: str) -> float:
        if n_cells and col in cells.columns:
            return float(cells[col].mean(skipna=True))
        return float("nan")

    mean_emos = _mean("crpss_emos_vs_raw")
    mean_qm = _mean("crpss_qm_vs_raw")
    lines = [
        "# Phase 2 hindcast CRPSS — calibrated vs raw ensemble",
        "",
        f"**Label:** `{HINDCAST_LABEL}` — provider: {PROVIDER}; "
        f"retrieved_at: {meta.get('retrieved_at')}; mode: `{mode}`.",
        "",
        "Protocol: `docs/EVALUATION_PROTOCOL.md` as amended; source design "
        "`docs/design/HINDCAST.md`. These numbers are **not** operational-archive "
        "scores and must never be mixed with the Phase 1 leaderboard series.",
        "",
        f"- Cells: {n_cells} (sufficient: {n_ok})",
        f"- Mean CRPSS EMOS vs raw: **{mean_emos:.4f}**",
        f"- Mean CRPSS QM vs raw: **{mean_qm:.4f}**",
        "",
        "A positive mean CRPSS is the Phase 2 exit-gate direction "
        "(`docs/ROADMAP.md`: CRPSS > 0 of calibrated vs raw ensemble) **on this "
        "hindcast sample only**. Cell-level `n_eval` and `insufficient` flags "
        "follow MIN_SAMPLE = 10 (2026-11-14 rules 4–5).",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [csv_path, md_path, json_path]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthetic", action="store_true", help="offline synthetic path")
    parser.add_argument("--smoke", action="store_true", help="tiny real GEFS window")
    parser.add_argument("--refresh", action="store_true", help="ignore hindcast cache")
    parser.add_argument("--n-train", type=int, default=DEFAULT_N_TRAIN)
    parser.add_argument(
        "--n-eval",
        type=int,
        default=DEFAULT_N_EVAL,
        help="informational; eval uses remaining dates",
    )
    parser.add_argument(
        "--leads",
        type=int,
        nargs="+",
        default=list(LEAD_DAYS_DEFAULT),
        help="lead days to score",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.synthetic:
        result = run_synthetic()
        cells = pd.DataFrame(result["cells"])
        root = find_repo_root()
        paths = write_outputs(root, cells, result["metadata"], mode="synthetic")
        print(f"synthetic CRPSS written: {paths[0]}")
        print(cells[["station_index", "crpss_emos_vs_raw", "crpss_qm_vs_raw"]])
        # Phase 2 gate direction check on synthetic
        mean_e = float(cells["crpss_emos_vs_raw"].mean())
        print(f"mean crpss_emos_vs_raw={mean_e:.4f} (synthetic only)")
        return 0 if mean_e > 0 else 1

    root = find_repo_root()
    stations = load_stations(root)
    obs = load_observations(root)
    # observation window
    times = pd.to_datetime(obs["time"])
    obs_start, obs_end = times.min().date(), times.max().date()
    all_dates = issue_dates_between(obs_start, obs_end)
    if args.smoke:
        # 10 train + 10 eval from the middle of the window, lead 1 only
        mid = len(all_dates) // 2
        window = all_dates[mid : mid + 20]
        n_train = 10
        leads = [1]
        print(f"SMOKE window {window[0]} → {window[-1]} leads={leads}")
    else:
        window = all_dates
        n_train = min(args.n_train, len(window) - 20)
        leads = list(args.leads)
        print(
            f"window {window[0]} → {window[-1]} ({len(window)} days) "
            f"n_train={n_train} leads={leads}"
        )

    print(f"stations={len(stations)} members={len(MEMBERS)} provider={PROVIDER}")
    cache = fetch_window(root, window, leads, stations, refresh=args.refresh)
    print(f"cache rows={len(cache)}")
    cells = evaluate_from_cache(
        cache, obs, stations, n_train=n_train, leads=leads
    )
    meta = hindcast_metadata()
    meta["mode"] = "smoke" if args.smoke else "full"
    meta["n_train_dates"] = n_train
    meta["leads"] = list(leads)
    meta["window_start"] = window[0].isoformat()
    meta["window_end"] = window[-1].isoformat()
    meta["obs_source"] = "smn-regtemp capture (local_calendar)"
    meta["n_cells"] = int(len(cells))
    paths = write_outputs(root, cells, meta, mode=meta["mode"])
    print(f"wrote {paths[0]}")
    if not cells.empty and "crpss_emos_vs_raw" in cells:
        sufficient = cells.loc[~cells["insufficient"]]
        if not sufficient.empty:
            print(
                "sufficient cells:",
                len(sufficient),
                "mean crpss_emos",
                float(sufficient["crpss_emos_vs_raw"].mean()),
                "mean crpss_qm",
                float(sufficient["crpss_qm_vs_raw"].mean()),
            )
        else:
            print("all cells insufficient (MIN_SAMPLE)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
