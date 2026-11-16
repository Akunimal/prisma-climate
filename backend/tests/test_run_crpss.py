"""Tests for CRPSS scoring helpers — synthetic only, no network."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from prisma.calibrate.run_crpss import (
    CACHE_RULE,
    MIN_SAMPLE,
    ROLLING_WINDOW,
    aggregate_crpss,
    evaluate_rolling,
    fit_calibrators,
    load_stations,
    location_to_station_id,
    rolling_train_dates,
    run_synthetic,
    score_case,
    synthetic_dataset,
)
from prisma.hindcast.gefs import MEMBERS
from prisma.ingest.base import find_repo_root


def test_synthetic_dataset_shapes() -> None:
    tr_m, tr_o, ev_m, ev_o = synthetic_dataset(n_train=30, n_eval=20, n_stations=2)
    assert tr_m.shape[0] == 2
    assert tr_m.shape[1] == 30
    assert tr_m.shape[2] == 31
    assert ev_m.shape == (2, 20, 31)
    assert tr_o.shape == (2, 30)
    assert ev_o.shape == (2, 20)


def test_score_case_keys() -> None:
    rng = np.random.default_rng(0)
    # 12 training cases so EMOS clears MIN_TRAINING
    members = rng.normal(20, 2, size=(12, 31))
    obs = rng.normal(21, 1, size=12)
    emos, qm = fit_calibrators(members, obs)
    case = members[0]
    scored = score_case(case, float(obs[0]), emos_params=emos, qm=qm)
    assert set(scored) == {"crps_raw", "crps_emos", "crps_qm"}
    assert scored["crps_raw"] > 0
    assert np.isfinite(scored["crps_emos"])
    assert np.isfinite(scored["crps_qm"])


def test_aggregate_crpss_nan_safe() -> None:
    raw = np.array([2.0, 2.0, 2.0])
    cal = np.array([1.0, 1.0, 1.0])
    assert aggregate_crpss(raw, cal) == pytest.approx(0.5)
    assert np.isnan(aggregate_crpss(raw, np.array([np.nan, np.nan, np.nan])))


def test_run_synthetic_beats_raw() -> None:
    """Biased under-dispersed ensemble: EMOS should beat raw (CRPSS > 0)."""
    result = run_synthetic()
    cells = result["cells"]
    assert result["metadata"]["label"] == "hindcast"
    mean_emos = float(np.mean([c["crpss_emos_vs_raw"] for c in cells]))
    mean_qm = float(np.mean([c["crpss_qm_vs_raw"] for c in cells]))
    assert mean_emos > 0.0, mean_emos
    assert mean_qm > 0.0, mean_qm


def _rolling_fixture(
    n_dates: int, *, pivot_index: int | None = None
) -> tuple[object, list[date], pd.DataFrame, pd.DataFrame]:
    """One station, consecutive daily issue dates, lead 1, full 31-member cache."""
    root = find_repo_root()
    st = load_stations(root)[0]
    loc = {v: k for k, v in location_to_station_id(root).items()}[st.station_id]
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=i) for i in range(n_dates)]
    rng = np.random.default_rng(3)
    means = rng.normal(10.0, 2.0, size=n_dates)
    rows = []
    for i, d in enumerate(dates):
        vals = means[i] + rng.normal(0.0, 0.5, size=len(MEMBERS))
        for m, v in zip(MEMBERS, vals, strict=True):
            rows.append(
                {
                    "issue_date": d.isoformat(),
                    "lead_day": 1,
                    "member": m,
                    "station_id": st.station_id,
                    "value_c": float(v),
                }
            )
    cache = pd.DataFrame(rows)
    # obs before the pivot look like the forecast; from the pivot on they jump
    pivot = dates[pivot_index if pivot_index is not None else n_dates - 1]
    orng = np.random.default_rng(4)
    obs_days = [start + timedelta(days=i) for i in range(n_dates + 4)]
    obs = pd.DataFrame(
        {
            "location": loc,
            "variable": "t2m_max",
            "time": [pd.Timestamp(d) for d in obs_days],
            "value": [
                (10.0 if d < pivot else 50.0) + float(orng.normal(0.0, 0.3))
                for d in obs_days
            ],
        }
    )
    return st, dates, cache, obs


def test_rolling_no_leakage_from_future_or_same_day() -> None:
    """Fit for issue D must ignore local day D-1 and later: the cycle is 00Z
    on D = 21:00 local on D-1, so D-1 has not ended at issue time. Results
    match an independent re-derivation and diverge if that info leaks in."""
    st, dates, cache, obs = _rolling_fixture(13, pivot_index=11)
    issue = dates[12]
    cells = evaluate_rolling(cache, obs, [st], leads=[1])
    assert len(cells) == 1
    row = cells.iloc[0]

    # eligibility written independently of rolling_train_dates: t + L + 2 <= D
    lead = 1
    eligible = [d for d in dates if d + timedelta(days=lead + 2) <= issue]
    assert len(eligible) == MIN_SAMPLE

    # local day D-1 as a verifying day is excluded (its day has not ended)
    d_minus_1 = issue - timedelta(days=1 + lead)  # verifying local day = D-1
    assert d_minus_1 in dates
    assert d_minus_1 + timedelta(days=lead + 1) <= issue  # old naive rule kept it
    assert d_minus_1 not in eligible
    # last eligible date verifies on D-2, the last day ended before issue time
    assert eligible[-1] + timedelta(days=lead) == issue - timedelta(days=2)

    obs_map = {
        (str(r.location), str(r.variable), pd.Timestamp(r.time).date()): float(r.value)
        for r in obs.itertuples(index=False)
    }
    sid = st.station_id

    def members_of(day: date) -> np.ndarray:
        sub = cache[
            (cache["lead_day"] == 1)
            & (cache["station_id"] == sid)
            & (cache["issue_date"] == day.isoformat())
        ]
        by = {str(r.member): float(r.value_c) for r in sub.itertuples(index=False)}
        return np.asarray([by[m] for m in MEMBERS if m in by], dtype=float)

    sid_to_loc = {v: k for k, v in location_to_station_id(find_repo_root()).items()}[sid]

    def obs_on(day: date) -> float:
        return obs_map[(sid_to_loc, "t2m_max", day + timedelta(days=lead))]

    pairs = [(members_of(d), obs_on(d)) for d in eligible]
    train_m = np.stack([m for m, _ in pairs], axis=0)
    train_o = np.asarray([o for _, o in pairs], dtype=float)
    emos, qm = fit_calibrators(train_m, train_o)
    eval_m = members_of(issue)
    eval_o = obs_on(issue)
    expected = score_case(eval_m, eval_o, emos_params=emos, qm=qm)

    assert row["crps_raw"] == pytest.approx(expected["crps_raw"], abs=1e-12)
    assert row["crps_emos"] == pytest.approx(expected["crps_emos"], abs=1e-12)
    assert row["crps_qm"] == pytest.approx(expected["crps_qm"], abs=1e-12)
    assert row["n_train"] == pytest.approx(MIN_SAMPLE)
    assert row["n_eval"] == 1
    assert bool(row["insufficient"]) is True
    assert np.isnan(row["crpss_emos_vs_raw"])

    # Leaky contrast: adding the D-1-verifying training date (pivot jumps to
    # 50 K on D-1, so its observation only exists after issue time anyway)
    # changes the fit — future information would alter the result.
    assert d_minus_1 in dates
    leak_pairs = pairs + [(members_of(d_minus_1), obs_on(d_minus_1))]
    lm = np.stack([m for m, _ in leak_pairs], axis=0)
    lo = np.asarray([o for _, o in leak_pairs], dtype=float)
    lemos, lqm = fit_calibrators(lm, lo)
    leaky = score_case(eval_m, eval_o, emos_params=lemos, qm=lqm)
    assert abs(leaky["crps_emos"] - expected["crps_emos"]) > 1.0
    assert abs(row["crps_emos"] - leaky["crps_emos"]) > 1.0


def test_rolling_train_dates_caps_and_boundaries() -> None:
    start = date(2026, 1, 1)
    dates = [start + timedelta(days=i) for i in range(120)]
    lead = 3
    issue = dates[100]
    got = rolling_train_dates(dates, lead, issue)
    assert len(got) == ROLLING_WINDOW
    # independent expectation: last eligible = issue - lead - 2 (t + L + 2 <= D)
    last_ok = (issue - timedelta(days=lead + 2) - start).days
    expected = dates[last_ok - ROLLING_WINDOW + 1 : last_ok + 1]
    assert got == expected
    assert got[-1] == issue - timedelta(days=lead + 2)
    # the date whose verifying day is D-1 is excluded
    assert issue - timedelta(days=lead + 1) not in got
    # nothing eligible before the first issue date
    assert rolling_train_dates(dates, lead, dates[0]) == []


def test_rolling_cell_below_min_sample_never_raw() -> None:
    """Fewer than MIN_SAMPLE usable dates ⇒ insufficient, all scores NaN."""
    st, _dates, cache, obs = _rolling_fixture(8)
    cells = evaluate_rolling(cache, obs, [st], leads=[1])
    row = cells.iloc[0]
    assert row["label"] == "hindcast"
    assert row["n_eval"] == 0
    assert bool(row["insufficient"]) is True
    assert np.isnan(row["crps_raw"])
    assert np.isnan(row["crps_emos"])
    assert np.isnan(row["crpss_emos_vs_raw"])
    assert np.isnan(row["crpss_qm_vs_raw"])


def test_evaluate_rolling_rule_filter_and_t2m_min() -> None:
    """Only CACHE_RULE rows are scored; t2m_min comes from tmin_c.

    Corrected rows are placed first and legacy rows last: without the rule
    filter the legacy values would win by overwrite order and the scores
    would match the legacy-only run.
    """
    st, _dates, cache, obs = _rolling_fixture(13, pivot_index=11)
    corrected = cache.copy()
    corrected["rule"] = CACHE_RULE
    corrected["value_c"] = corrected["value_c"] + 1.5
    corrected["tmin_c"] = corrected["value_c"] - 12.0
    legacy = cache.copy()
    legacy["rule"] = np.nan
    mixed = pd.concat([corrected, legacy], ignore_index=True)

    obs2 = pd.concat(
        [obs, obs.assign(variable="t2m_min", value=obs["value"] - 12.0)],
        ignore_index=True,
    )

    cells = evaluate_rolling(mixed, obs2, [st], leads=[1])
    assert set(cells["variable"]) == {"t2m_max", "t2m_min"}

    only = evaluate_rolling(corrected, obs2, [st], leads=[1])
    merged = cells.merge(
        only, on=["variable", "lead_day", "station_id"], suffixes=("_mixed", "_only")
    )
    assert len(merged) == 2
    assert list(merged["crps_raw_mixed"]) == pytest.approx(
        list(merged["crps_raw_only"])
    )

    # t2m_min was read from tmin_c (= value_c − 12) and scored against the
    # −12 obs: CRPS is translation-invariant, so it equals the t2m_max CRPS.
    by_var = cells.set_index("variable")
    assert by_var.loc["t2m_max", "crps_raw"] == pytest.approx(
        by_var.loc["t2m_min", "crps_raw"]
    )
    assert by_var.loc["t2m_max", "n_eval"] == by_var.loc["t2m_min", "n_eval"]

    # legacy-only cache (no rule column) scores different numbers → the
    # mixed run above really did select the corrected rows.
    legacy_norule = cache.copy()
    cells_legacy = evaluate_rolling(legacy_norule, obs2, [st], leads=[1])
    cmp = cells.merge(
        cells_legacy,
        on=["variable", "lead_day", "station_id"],
        suffixes=("_mixed", "_legacy"),
    )
    assert len(cmp) == 1  # legacy cache has no tmin_c → t2m_max only
    assert not np.allclose(cmp["crps_raw_mixed"], cmp["crps_raw_legacy"])
