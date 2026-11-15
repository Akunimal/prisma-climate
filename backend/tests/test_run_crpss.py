"""Tests for CRPSS scoring helpers — synthetic only, no network."""

from __future__ import annotations

import numpy as np
import pytest

from prisma.calibrate.run_crpss import (
    aggregate_crpss,
    fit_calibrators,
    run_synthetic,
    score_case,
    synthetic_dataset,
)


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
