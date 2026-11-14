"""Tests for prisma.verify.run — synthetic fixtures only, never the real archive.

Every fabricated forecast/observation set lives inside this file; no test
lists, downloads or scores anything from Hugging Face (``main`` always gets an
injected listing), and no test writes under ``results/`` (``write_results``
runs against ``tmp_path``).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prisma.verify.run import (
    GATE_ISSUE_DATES,
    climatology_samples,
    count_issue_dates,
    gate_message,
    issue_band,
    leaderboard,
    main,
    pair_forecasts_observations,
    persistence_value,
    score_pairs,
    write_results,
)


def _repo_listing(dates: list[str]) -> list[str]:
    """Synthetic HF-style file listing for the given forecast issue dates."""
    paths: list[str] = []
    for day in dates:
        paths.append(f"forecasts/{day}/openmeteo-ensemble_{day}.parquet")
        # Observation keys must not count toward the gate.
        paths.append(f"observations/smn/observaciones/{day}/observaciones.zip")
    paths.append("README.md")
    return paths


def _days(count: int) -> list[str]:
    base = pd.Timestamp("2026-11-11")
    return [(base + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(count)]


def test_count_issue_dates_counts_only_forecast_keys() -> None:
    paths = _repo_listing(["2026-11-11", "2026-11-12"]) + [
        "forecasts/",  # malformed, ignored
        "docs/forecasts/notes.md",  # not the dataset root
    ]
    assert count_issue_dates(paths) == 2
    assert count_issue_dates([]) == 0


def test_gate_message_states_count_and_nothing_more() -> None:
    message = gate_message(3)
    assert message.startswith("3 distinct issue dates archived")
    assert "No metric computed." in message
    assert str(GATE_ISSUE_DATES) in message


def test_main_below_gate_prints_count_and_refuses(capsys: pytest.CaptureFixture) -> None:
    runs: list[int] = []
    code = main(
        [],
        list_files=lambda: _repo_listing(_days(GATE_ISSUE_DATES - 1)),
        run=runs.append,
    )
    captured = capsys.readouterr()
    assert code == 1
    assert runs == []
    lines = captured.out.strip().splitlines()
    assert len(lines) == 1  # the count message and nothing else
    assert f"{GATE_ISSUE_DATES - 1} distinct issue dates" in lines[0]
    assert "No metric computed." in lines[0]


def test_main_at_gate_runs_the_pipeline(capsys: pytest.CaptureFixture) -> None:
    seen: list[int] = []
    code = main(
        [],
        list_files=lambda: _repo_listing(_days(GATE_ISSUE_DATES)),
        run=lambda n: seen.append(n) or 0,
    )
    assert code == 0
    assert seen == [GATE_ISSUE_DATES]
    assert capsys.readouterr().out == ""


def test_no_command_line_flag_can_override_the_gate() -> None:
    for flag in ("--force", "--ignore-gate", "--gate", "0"):
        with pytest.raises(SystemExit):
            main(
                [flag],
                list_files=lambda: _repo_listing(_days(3)),
                run=lambda n: pytest.fail("pipeline must not run below the gate"),
            )


def test_pairing_matches_on_local_calendar_day_and_filters() -> None:
    forecasts = pd.DataFrame(
        [
            # Paired (ok).
            dict(
                issue_time="2026-11-11T12:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=1,
                member=0,
                value=1.0,
                quality_flag="ok",
            ),
            # Suspect member of the same cell: excluded by policy.
            dict(
                issue_time="2026-11-11T12:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=1,
                member=1,
                value=9.0,
                quality_flag="suspect",
            ),
            # Precipitation: not verifiable, excluded.
            dict(
                issue_time="2026-11-11T12:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="precip",
                time="2026-11-12",
                lead_day=1,
                member=0,
                value=3.0,
                quality_flag="ok",
            ),
            # Station with no observation that day: dropped, never filled.
            dict(
                issue_time="2026-11-11T12:00:00Z",
                model="gfs_seamless",
                location="Beta",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=1,
                member=0,
                value=5.0,
                quality_flag="ok",
            ),
        ]
    )
    observations = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2026-11-12", value=2.0),
            # Same local day, different station, still unpaired for Beta? Beta has no row.
            dict(location="Alfa", variable="t2m_min", time="2026-11-12", value=-1.0),
        ]
    )
    paired = pair_forecasts_observations(forecasts, observations)
    assert len(paired) == 1
    row = paired.iloc[0]
    assert row["location"] == "Alfa"
    assert row["obs_value"] == 2.0
    assert row["value"] == 1.0
    assert str(row["time"]) == "2026-11-12"


def test_persistence_uses_last_local_day_before_the_issue() -> None:
    observations = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2026-11-10", value=5.0),
            dict(location="Alfa", variable="t2m_max", time="2026-11-12", value=2.0),
        ]
    )
    # Issued 2026-11-11 09:00 local: the last completed local day is 11-10.
    value = persistence_value(
        observations, "Alfa", "t2m_max", "2026-11-11T12:00:00Z"
    )
    assert value == 5.0
    # No earlier day in the archive: NaN, never a filled guess.
    assert pd.isna(persistence_value(observations, "Delta", "t2m_max", "2026-11-11T12:00:00Z"))


def test_climatology_samples_window_and_frozen_adjustment() -> None:
    era5 = pd.DataFrame(
        [
            # Inside +/-15-day circular window (doy distance 2), value 10.
            dict(location="Alfa", variable="t2m_max", time="2025-11-10", value=10.0),
            # Inside the window (distance 11), value 12.
            dict(location="Alfa", variable="t2m_max", time="2026-11-01", value=12.0),
            # June: far outside the window, must be excluded.
            dict(location="Alfa", variable="t2m_max", time="2026-06-15", value=50.0),
            # Other station: excluded by location.
            dict(location="Beta", variable="t2m_max", time="2025-11-10", value=99.0),
        ]
    )
    adjustment = pd.DataFrame(
        [
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=11,
                mean_diff_smn_minus_era5=0.0,
            ),
            dict(
                location="Beta",
                variable="t2m_max",
                calendar_month=11,
                mean_diff_smn_minus_era5=7.0,
            ),
        ]
    )
    samples = climatology_samples(
        era5,
        adjustment,
        "Alfa",
        "t2m_max",
        "2026-11-12",
        "2025-01-01",
        "2026-11-01",
    )
    assert sorted(samples.tolist()) == [10.0, 12.0]
    # Analytic CRPS of samples [10, 12] against obs 11: 1 - 0.5 = 0.5.
    from prisma.verify.metrics import crps_from_samples

    assert crps_from_samples(samples, 11.0) == pytest.approx(0.5)
    # Training-window end excludes the 2025 row entirely.
    empty = climatology_samples(
        era5,
        adjustment,
        "Alfa",
        "t2m_max",
        "2026-11-12",
        "2026-10-01",
        "2026-11-01",
    )
    assert empty.size == 1  # only 2026-11-01 remains inside the training window


def test_score_pairs_analytic_raw_climatology_persistence() -> None:
    forecasts = pd.DataFrame(
        [
            dict(
                issue_time="2026-11-11T12:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=0,
                member=member,
                value=value,
                quality_flag="ok",
            )
            for member, value in enumerate([1.0, 2.0, 3.0])
        ]
    )
    observations = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2026-11-10", value=5.0),
            dict(location="Alfa", variable="t2m_max", time="2026-11-12", value=2.0),
        ]
    )
    era5 = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2025-11-10", value=10.0),
            dict(location="Alfa", variable="t2m_max", time="2026-11-01", value=12.0),
        ]
    )
    adjustment = pd.DataFrame(
        [
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=11,
                mean_diff_smn_minus_era5=0.0,
            )
        ]
    )
    pairs = pair_forecasts_observations(forecasts, observations)
    scored = score_pairs(
        pairs,
        observations,
        era5,
        adjustment,
        train_start="2025-01-01",
        train_end="2026-11-01",
    )
    assert len(scored) == 1
    row = scored.iloc[0]
    # Fair CRPS of members [1, 2, 3] against 2: 2/3 - 0.5*(8/9) = 2/9.
    assert row["raw_crps"] == pytest.approx(2.0 / 9.0)
    # Climatology samples [10, 12] + 0 against 2: 9 - 0.5 = 8.5.
    assert row["climatology_crps"] == pytest.approx(8.5)
    # Persistence: last completed local day before the issue is 11-10 (5.0);
    # point-forecast CRPS is |5 - 2| = 3.
    assert row["persistence_crps"] == pytest.approx(3.0)
    assert row["stratum"] == "12:00-23:59"


def test_persistence_is_na_beyond_lead_three() -> None:
    forecasts = pd.DataFrame(
        [
            dict(
                issue_time="2026-11-11T02:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-17",
                lead_day=6,
                member=0,
                value=1.0,
                quality_flag="ok",
            )
        ]
    )
    observations = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2026-11-10", value=5.0),
            dict(location="Alfa", variable="t2m_max", time="2026-11-17", value=2.0),
        ]
    )
    pairs = pair_forecasts_observations(forecasts, observations)
    scored = score_pairs(
        pairs,
        observations,
        pd.DataFrame(columns=["location", "variable", "time", "value"]),
        pd.DataFrame(
            columns=["location", "variable", "calendar_month", "mean_diff_smn_minus_era5"]
        ),
        train_start="2025-01-01",
        train_end="2026-11-01",
    )
    assert pd.isna(scored.iloc[0]["persistence_crps"])  # n/a beyond lead 3
    assert scored.iloc[0]["stratum"] == "00:00-11:59"


def test_issue_band_matches_the_protocol_hours() -> None:
    assert issue_band("2026-11-11T00:00:00Z") == "00:00-11:59"
    assert issue_band("2026-11-11T11:59:00Z") == "00:00-11:59"
    assert issue_band("2026-11-11T12:00:00Z") == "12:00-23:59"
    assert issue_band("2026-11-11T23:59:00Z") == "12:00-23:59"
    # Naive timestamps are read as UTC.
    assert issue_band(pd.Timestamp("2026-11-11 08:00:00")) == "00:00-11:59"


def _scored_fixture() -> pd.DataFrame:
    return pd.DataFrame(
        [
            dict(
                issue_time="2026-11-11T02:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=0,
                stratum="00:00-11:59",
                obs_value=2.0,
                raw_crps=1.0,
                climatology_crps=2.0,
                persistence_crps=float("nan"),
            ),
            dict(
                issue_time="2026-11-12T15:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-13",
                lead_day=0,
                stratum="12:00-23:59",
                obs_value=3.0,
                raw_crps=3.0,
                climatology_crps=2.0,
                persistence_crps=1.0,
            ),
        ]
    )


def test_leaderboard_reports_counts_means_and_crpss() -> None:
    board = leaderboard(_scored_fixture())
    assert len(board) == 1
    cell = board.iloc[0]
    assert cell["n_pairs"] == 2
    assert cell["n_climatology"] == 2
    assert cell["n_persistence"] == 1
    assert cell["crps_raw"] == pytest.approx(2.0)
    assert cell["crps_climatology"] == pytest.approx(2.0)
    assert cell["crps_persistence"] == pytest.approx(1.0)
    # CRPSS vs climatology over the both-finite rows: 1 - mean(1, 3)/mean(2, 2).
    assert cell["crpss_vs_climatology"] == pytest.approx(0.0)
    # CRPSS vs persistence where both exist: 1 - 3/1.
    assert cell["crpss_vs_persistence"] == pytest.approx(-2.0)


def test_leaderboard_splits_by_issue_hour_stratum() -> None:
    strata = leaderboard(_scored_fixture(), by_stratum=True)
    assert sorted(strata["stratum"]) == ["00:00-11:59", "12:00-23:59"]
    morning = strata.loc[strata["stratum"].eq("00:00-11:59")].iloc[0]
    assert morning["n_pairs"] == 1
    assert pd.isna(morning["crps_persistence"])


def test_write_results_emits_three_files(tmp_path: Path) -> None:
    board = leaderboard(_scored_fixture())
    strata = leaderboard(_scored_fixture(), by_stratum=True)
    written = write_results(board, strata, tmp_path / "verification", issue_dates=15)
    assert [path.name for path in written] == [
        "leaderboard.csv",
        "leaderboard_by_issue_hour_stratum.csv",
        "leaderboard.md",
    ]
    reread = pd.read_csv(written[0])
    assert len(reread) == 1
    markdown = written[2].read_text(encoding="utf-8")
    assert "15 distinct issue dates archived" in markdown
    assert "no cell is suppressed" in markdown
