"""Unit tests for hindcast helpers — synthetic / offline only."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest

from prisma.hindcast import (
    MEMBERS,
    N_MEMBERS,
    StationPoint,
    build_ensemble_matrix,
    candidate_keys,
    find_field_range,
    flat_key,
    hindcast_metadata,
    issue_dates_between,
    kelvin_to_celsius,
    lead_forecast_hour,
    modern_key,
    modern_sp25_key,
    parse_idx,
    required_members,
    sample_nearest,
    split_train_eval,
)


def test_member_count_is_31() -> None:
    assert N_MEMBERS == 31
    assert len(MEMBERS) == 31
    assert MEMBERS[0] == "gec00"
    assert MEMBERS[1] == "gep01"
    assert MEMBERS[-1] == "gep30"


def test_required_members_80_percent() -> None:
    # 31 * 0.8 = 24.8 → ceil 25
    assert required_members(31) == 25
    assert required_members(10) == 8


def test_flat_and_modern_keys() -> None:
    d = date(2017, 1, 1)
    assert flat_key(d, "gec00", 24) == "gefs.20170101/00/gec00.t00z.pgrb2af024"
    m = modern_key(d, "gep01", 72)
    assert m == "gefs.20170101/00/atmos/pgrb2ap5/gep01.t00z.pgrb2a.0p50.f072"
    s = modern_sp25_key(d, "gec00", 24)
    assert s == "gefs.20170101/00/atmos/pgrb2sp25/gec00.t00z.pgrb2s.0p25.f024"
    cands = candidate_keys(d, "gec00", 24)
    assert cands[0].layout == "flat"
    assert cands[1].layout == "modern_ap5"
    assert cands[2].layout == "modern_sp25"


def test_parse_idx_tmax_offset() -> None:
    text = (
        "62:3150000:d=2017010100:UGRD:10 m above ground:…\n"
        "63:3228934:d=2017010100:TMAX:2 m above ground:18-24 hour max fcst:ENS=low-res ctl\n"
        "64:3299196:d=2017010100:TMIN:2 m above ground:18-24 hour min fcst:ENS=low-res ctl\n"
    )
    recs = parse_idx(text)
    assert len(recs) == 3
    assert recs[1][1] == 3228934
    rng = find_field_range(recs, "TMAX", file_size=4_155_383)
    assert rng == (3228934, 3299195)
    rng_min = find_field_range(recs, "TMIN", file_size=4_155_383)
    assert rng_min is not None
    assert rng_min[0] == 3299196


def test_find_field_range_missing_returns_none() -> None:
    recs = parse_idx("1:0:d=x:SPD:surface:…\n")
    assert find_field_range(recs, "TMAX", 1000) is None


def test_lead_forecast_hour() -> None:
    assert lead_forecast_hour(1) == 24
    assert lead_forecast_hour(15) == 360


def test_sample_nearest_and_lon_conventions() -> None:
    # 3×3 grid
    lats = np.array([10.0, 0.0, -10.0])
    lons = np.array([0.0, 10.0, 20.0])
    field = np.arange(9, dtype=float).reshape(3, 3)
    # exact node
    assert sample_nearest(field, lats, lons, 0.0, 10.0) == 4.0
    # negative lon → 0–360 grid
    assert sample_nearest(field, lats, lons, 0.0, -350.0) == 4.0  # -350 % 360 = 10
    with pytest.raises(ValueError):
        sample_nearest(field, lats, lons, 0.0, 10.0) and sample_nearest(
            np.zeros((2, 2)), lats, lons, 0.0, 0.0
        )


def test_kelvin_to_celsius() -> None:
    assert kelvin_to_celsius(300.0) == pytest.approx(26.85)


def test_split_train_eval() -> None:
    dates = issue_dates_between(date(2024, 1, 1), date(2024, 1, 10))
    assert len(dates) == 10
    train, eval_ = split_train_eval(dates, 6)
    assert len(train) == 6
    assert len(eval_) == 4
    assert eval_[0] > train[-1]
    with pytest.raises(ValueError):
        split_train_eval(dates, 10)
    with pytest.raises(ValueError):
        split_train_eval(dates, 0)


def test_build_ensemble_matrix_requires_80_percent() -> None:
    from prisma.hindcast.gefs import MemberForecast

    stations = [StationPoint("ba", -34.5, -58.5), StationPoint("cb", -31.4, -64.2)]
    # only 10 members → below 25
    members = []
    for mid in MEMBERS[:10]:
        members.append(
            MemberForecast(
                issue_date=date(2024, 6, 1),
                lead_day=1,
                member=mid,
                values_c={"ba": 20.0, "cb": 18.0},
                layout="flat",
                key="x",
            )
        )
    with pytest.raises(ValueError, match="need"):
        build_ensemble_matrix(members, stations)

    # full 31
    members = [
        MemberForecast(
            issue_date=date(2024, 6, 1),
            lead_day=1,
            member=mid,
            values_c={"ba": 20.0 + i * 0.1, "cb": 18.0},
            layout="flat",
            key="x",
        )
        for i, mid in enumerate(MEMBERS)
    ]
    mat, ids = build_ensemble_matrix(members, stations)
    assert mat.shape == (31, 2)
    assert ids == ["ba", "cb"]


def test_hindcast_metadata_labels() -> None:
    meta = hindcast_metadata()
    assert meta["label"] == "hindcast"
    assert "GEFS" in meta["provider"]
    assert meta["retrieved_at"].endswith("Z")
    assert meta["n_members"] == 31
