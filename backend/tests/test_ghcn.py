"""GHCN-Daily .dly parser tests — no network access."""

from __future__ import annotations

from prisma.ingest.ghcn import parse_dly

STATION = {"name": "Cordoba Aero", "lat": -31.317, "lon": -64.217}


def _day(value: str, qflag: str = " ") -> str:
    """One 8-byte GHCN-Daily day field: value(5) mflag(1) qflag(1) sflag(1)."""
    return f"{value:>5} {qflag} "


def _line(*, min_year: int = 1996, qflag_day1: str = " ") -> str:
    """Build a single TMAX monthly record for January of ``min_year``."""
    header = f"AR000087344{min_year}01TMAX"
    days = [
        _day("+305", qflag_day1),
        _day("+312"),
        _day("+298"),
        _day("+280"),
        *[_day("-9999")] * 27,
    ]
    return header + "".join(days)


def test_parse_dly_reads_values_and_flags() -> None:
    frame = parse_dly(_line(), STATION, min_year=1996)

    assert set(frame["variable"]) == {"t2m_max"}
    assert frame["value"].tolist() == [30.5, 31.2, 29.8, 28.0]
    assert frame["time"].dt.day.tolist() == [1, 2, 3, 4]
    assert frame["quality_flag"].unique().tolist() == ["ok"]
    assert frame["location"].unique().tolist() == ["Cordoba Aero"]
    assert frame["lat"].unique().tolist() == [-31.317]


def test_parse_dly_respects_min_year_and_missing_sentinel() -> None:
    frame = parse_dly(_line(min_year=2020), STATION, min_year=2021)
    assert frame.empty

    header = "AR000087344202001TMAX"
    only_sentinel = header + _day("-9999") * 31
    frame = parse_dly(only_sentinel, STATION, min_year=1996)
    assert frame.empty


def test_parse_dly_marks_non_blank_quality_flag_as_suspect() -> None:
    frame = parse_dly(_line(qflag_day1="D"), STATION, min_year=1996)
    day1 = frame.loc[frame["time"].dt.day == 1, "quality_flag"].item()
    assert day1 == "suspect"
    assert (frame["quality_flag"] == "suspect").sum() == 1
