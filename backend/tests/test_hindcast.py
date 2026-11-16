"""Unit tests for hindcast helpers — synthetic / offline only."""

from __future__ import annotations

import re
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


def test_local_day_periods_labels() -> None:
    from prisma.hindcast.gefs import (
        LOCAL_DAY_TMIN_PERIODS,
        local_day_periods,
    )

    # lead 1: local day V = t+1 starts at forecast hour 24 (00Z of V)
    assert local_day_periods(1) == ((30, 36), (36, 42), (42, 48))
    assert local_day_periods(15) == ((366, 372), (372, 378), (378, 384))
    assert local_day_periods(1, LOCAL_DAY_TMIN_PERIODS) == ((30, 36), (36, 42))
    p = local_day_periods(3)
    # contiguous tiling of [24L+6, 24L+24) = local 03:00–21:00 of V
    assert p[0][0] == 24 * 3 + 6
    assert p[-1][1] == 24 * 3 + 24
    assert all(p[i][1] == p[i + 1][0] for i in range(len(p) - 1))
    # file hour (= label end) exists in GEFS ap5: multiple of 6, ≤ 384
    assert all(e % 6 == 0 for _, e in p)
    assert local_day_periods(15)[-1][1] == 384


def test_find_field_range_for_period_reads_label() -> None:
    from prisma.hindcast.gefs import find_field_range_for_period

    text = (
        "60:1000000:d=2026051200:TMAX:2 m above ground:30-33 hour max fcst:ENS=low-res ctl\n"
        "61:1100000:d=2026051200:TMAX:2 m above ground:30-36 hour max fcst:ENS=low-res ctl\n"
        "62:1200000:d=2026051200:TMIN:2 m above ground:30-36 hour min fcst:ENS=low-res ctl\n"
        "63:1300000:d=2026051200:UGRD:10 m above ground:30-36 hour avg fcst:ENS=low-res ctl\n"
    )
    recs = parse_idx(text)
    # exact label match — not the 3-hour neighbour, not the file hour alone
    assert find_field_range_for_period(recs, "TMAX", 30, 36, 5_000_000) == (
        1100000,
        1199999,
    )
    assert find_field_range_for_period(recs, "TMAX", 30, 33, 5_000_000) == (
        1000000,
        1099999,
    )
    assert find_field_range_for_period(recs, "TMAX", 31, 36, 5_000_000) is None
    assert find_field_range_for_period(recs, "TMAX", 30, 42, 5_000_000) is None
    # max/min kind follows the variable, not just the window
    assert find_field_range_for_period(recs, "TMIN", 30, 36, 5_000_000) == (
        1200000,
        1299999,
    )
    assert find_field_range_for_period(recs, "TMIN", 30, 33, 5_000_000) is None


def _fake_localday_http(
    files: dict[int, dict[str, int | None]],
    *,
    three_hour_tmax: frozenset[int] = frozenset(),
):
    """Synthetic S3: .idx text + byte ranges whose first message byte is °C."""

    def idx_text(hour: int) -> str:
        spec = files[hour]
        start = hour - 3 if hour in three_hour_tmax else hour - 6
        lines = [
            f"1:100:d=2026051200:UGRD:10 m above ground:"
            f"{start}-{hour} hour avg fcst:ENS=low-res ctl",
            f"2:5000:d=2026051200:TMAX:2 m above ground:"
            f"{start}-{hour} hour max fcst:ENS=low-res ctl",
        ]
        if spec["tmin"] is not None:
            lines.append(
                f"3:6000:d=2026051200:TMIN:2 m above ground:"
                f"{start}-{hour} hour min fcst:ENS=low-res ctl"
            )
        lines.append(
            f"4:7000:d=2026051200:PRMSL:mean sea level:"
            f"{start}-{hour} hour avg fcst:ENS=low-res ctl"
        )
        return "\n".join(lines) + "\n"

    def file_bytes(hour: int) -> bytes:
        spec = files[hour]
        buf = bytearray(8000)
        buf[5000] = int(spec["tmax"])
        if spec["tmin"] is not None:
            buf[6000] = int(spec["tmin"])
        return bytes(buf)

    def fake_http(
        url: str, headers: dict[str, str] | None = None
    ) -> tuple[int, bytes, dict[str, str]]:
        m = re.search(r"\.f(\d{3})(?:\.idx)?$", url)
        if m is None:
            return 404, b"", {}  # flat-layout probe never matches modern keys
        hour = int(m.group(1))
        if hour not in files:
            return 404, b"", {}
        if url.endswith(".idx"):
            return 200, idx_text(hour).encode(), {}
        rng = (headers or {}).get("Range", "")
        if rng == "bytes=0-0":
            return 206, b"\x00", {"Content-Range": "bytes 0-0/8000"}
        a, b = (int(x) for x in rng.removeprefix("bytes=").split("-"))
        content = file_bytes(hour)
        return 206, content[a : b + 1], {}

    return fake_http


def _fake_decode_marker(blob: bytes):
    """Fake GRIB decode: first byte of the message = degC."""
    k = 273.15 + float(blob[0])
    return np.array([[k]]), np.array([0.0]), np.array([0.0])


def test_fetch_member_local_day_combines_periods_and_beats_old_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local-day max comes from day V's periods; the legacy single-message
    rule (f024 = 18-24 UTC of V−1) reads a bigger spike on the wrong day."""
    from prisma.hindcast import gefs

    issue = date(2026, 5, 12)
    st = StationPoint("s1", -34.6, -58.4)
    # f024 (old rule): 45 °C spike on local May 12 (V−1) 15-21;
    # f036/f042/f048 cover local May 13 03-21 (day V): 25 / 28 / 30 °C
    files = {
        24: {"tmax": 45, "tmin": 20},
        36: {"tmax": 25, "tmin": 18},
        42: {"tmax": 28, "tmin": 16},
        48: {"tmax": 30, "tmin": None},
    }
    fake_http = _fake_localday_http(files)
    monkeypatch.setattr(gefs, "decode_tmax_from_grib_bytes", _fake_decode_marker)

    fc = gefs.fetch_member_local_day(issue, "gec00", 1, [st], http_get=fake_http)
    assert fc is not None
    # day V t2m_max = max(25, 28, 30); t2m_min = min(18, 16)
    assert fc.values_c["s1"] == pytest.approx(30.0)
    assert fc.values_min_c is not None
    assert fc.values_min_c["s1"] == pytest.approx(16.0)
    assert fc.key.count(";") == 2  # three files joined

    # old single-message rule (f024, period 18-24 of V−1) → 45 °C: wrong day
    legacy = gefs.fetch_member_tmax(issue, "gec00", 1, [st], http_get=fake_http)
    assert legacy is not None
    assert legacy.values_c["s1"] == pytest.approx(45.0)
    assert legacy.values_c["s1"] != fc.values_c["s1"]


def test_fetch_member_local_day_fails_on_missing_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 3-hour neighbour label must not be substituted for the 6-hour one."""
    from prisma.hindcast import gefs

    issue = date(2026, 5, 12)
    st = StationPoint("s1", -34.6, -58.4)
    files = {
        36: {"tmax": 25, "tmin": 18},
        42: {"tmax": 28, "tmin": 16},  # idx only states 39-42, not 36-42
        48: {"tmax": 30, "tmin": None},
    }
    fake_http = _fake_localday_http(files, three_hour_tmax=frozenset({42}))
    monkeypatch.setattr(gefs, "decode_tmax_from_grib_bytes", _fake_decode_marker)

    assert (
        gefs.fetch_member_local_day(issue, "gec00", 1, [st], http_get=fake_http)
        is None
    )
