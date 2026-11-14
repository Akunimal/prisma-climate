"""Tests for prisma.verify.run — synthetic fixtures only, never the real archive.

Every fabricated forecast/observation set lives inside this file; no test
lists, downloads or scores anything from Hugging Face (``main`` always gets an
injected listing), and no test writes under ``results/`` (``write_results``
runs against ``tmp_path``).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pandas as pd
import pytest

from prisma.verify.run import (
    GATE_ISSUE_DATES,
    MIN_SAMPLE,
    _norm_doy,
    _parse_payload_zip,
    climatology_samples,
    count_issue_dates,
    gate_message,
    issue_band,
    leaderboard,
    load_member_counts,
    main,
    observations_long,
    pair_forecasts_observations,
    persistence_value,
    run_above_gate,
    score_pairs,
    write_results,
)

# Synthetic nominal member counts for the 80% rule (rule 1); the real values
# (31 / 51) live in configs/sources.yaml and are only read by load_member_counts.
MEMBER_COUNTS = {"gfs_seamless": 5, "ecmwf_ifs025": 9}


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


def test_pairing_matches_on_local_calendar_day_and_keeps_all_members() -> None:
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
            # Suspect member of the same cell: joined here, excluded at
            # scoring (rule 1 decides member usability per case).
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
            dict(location="Alfa", variable="t2m_min", time="2026-11-12", value=-1.0),
        ]
    )
    paired = pair_forecasts_observations(forecasts, observations)
    assert len(paired) == 2  # both Alfa t2m_max members survive the join
    assert set(paired["quality_flag"]) == {"ok", "suspect"}
    # Scoring uses only the ok member (1.0); the suspect 9.0 never enters.
    scored = score_pairs(
        paired,
        pd.DataFrame(columns=["location", "variable", "time", "value"]),
        pd.DataFrame(columns=["location", "variable", "time", "value"]),
        pd.DataFrame(
            columns=["location", "variable", "calendar_month", "mean_diff_smn_minus_era5"]
        ),
        train_start="2025-01-01",
        train_end="2026-11-01",
        member_counts={"gfs_seamless": 1},  # 1 of 1 usable >= 80%
    )
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["case_status"] == "scored"
    assert row["n_present_members"] == 1
    # |1 - 2| = 1: the suspect member 9.0 is not part of the ensemble.
    assert row["raw_crps"] == pytest.approx(1.0)


def test_member_rule_scores_at_80_percent_and_marks_below_as_missing() -> None:
    # Rule 1: nominal 5 members -> 4 present+ok (80%) is scored, 3 is missing.
    forecasts = pd.DataFrame(
        [
            dict(
                issue_time="2026-11-11T02:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time="2026-11-12",
                lead_day=1,
                member=member,
                value=value,
                quality_flag=flag,
            )
            for member, value, flag in [
                (0, 1.0, "ok"),
                (1, 2.0, "ok"),
                (2, 3.0, "ok"),
                (3, 4.0, "ok"),
                (4, 9.0, "suspect"),
            ]
        ]
    )
    observations = pd.DataFrame(
        [dict(location="Alfa", variable="t2m_max", time="2026-11-12", value=2.0)]
    )
    paired = pair_forecasts_observations(forecasts, observations)
    empty_era5 = pd.DataFrame(columns=["location", "variable", "time", "value"])
    empty_adj = pd.DataFrame(
        columns=["location", "variable", "calendar_month", "mean_diff_smn_minus_era5"]
    )
    # 4 of 5 ok == 80%: scored on the four ok members only.
    scored = score_pairs(
        paired,
        observations,
        empty_era5,
        empty_adj,
        train_start="2025-01-01",
        train_end="2026-11-01",
        member_counts={"gfs_seamless": 5},
    )
    assert len(scored) == 1
    assert scored.iloc[0]["case_status"] == "scored"
    assert scored.iloc[0]["n_present_members"] == 4
    # The suspect member 9.0 never enters: fair CRPS of [1,2,3,4] vs 2
    # = 1.0 - 0.5*(20/16) = 0.375.
    assert scored.iloc[0]["raw_crps"] == pytest.approx(0.375)
    # Same case with one more member flagged suspect: 3 of 5 == 60% < 80%.
    forecasts.loc[forecasts["member"].eq(3), "quality_flag"] = "suspect"
    paired = pair_forecasts_observations(forecasts, observations)
    scored = score_pairs(
        paired,
        observations,
        empty_era5,
        empty_adj,
        train_start="2025-01-01",
        train_end="2026-11-01",
        member_counts={"gfs_seamless": 5},
    )
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["case_status"] == "missing_members"
    assert row["n_present_members"] == 3
    assert pd.isna(row["raw_crps"])
    assert pd.isna(row["climatology_crps"])
    assert pd.isna(row["persistence_crps"])


def test_climatology_window_wraps_the_year_boundary() -> None:
    # Rule 2: late December and early January are neighbours (circular doy).
    era5 = pd.DataFrame(
        [
            # doy 360 (2025-12-26), target 2026-01-02 (doy 2): circular
            # distance = min(358, 7) = 7 <= 15 -> inside.
            dict(location="Alfa", variable="t2m_max", time="2025-12-26", value=30.0),
            # Straight-line distance would be 358: excluded by a naive window.
            # 2025-12-01 (doy 335): circular distance to doy 2 = min(333, 32) = 32 > 15.
            dict(location="Alfa", variable="t2m_max", time="2025-12-01", value=50.0),
        ]
    )
    adjustment = pd.DataFrame(
        [
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=12,
                mean_diff_smn_minus_era5=0.0,
            )
        ]
    )
    samples = climatology_samples(
        era5,
        adjustment,
        "Alfa",
        "t2m_max",
        "2026-01-02",
        "2025-01-01",
        "2026-11-01",
    )
    assert samples.tolist() == [30.0]
    # 29 February is treated as 28 February: same normalized doy.
    assert _norm_doy(pd.Timestamp("2024-02-29")) == _norm_doy(pd.Timestamp("2024-02-28"))
    assert _norm_doy(pd.Timestamp("2024-02-29")) == 59
    # Normalized doys never exceed the 365-day scale.
    assert _norm_doy(pd.Timestamp("2024-03-01")) == 60
    assert _norm_doy(pd.Timestamp("2025-12-31")) == 365


def test_climatology_window_fold_of_leap_day_matches_feb_28() -> None:
    # Rule 2 second half: a 29-February target samples the same window as
    # 28 February (both normalize to doy 59 in a leap year).
    era5 = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2023-02-28", value=25.0),
            dict(location="Alfa", variable="t2m_max", time="2023-03-05", value=99.0),
        ]
    )
    adjustment = pd.DataFrame(
        [
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=2,
                mean_diff_smn_minus_era5=0.0,
            ),
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=3,
                mean_diff_smn_minus_era5=0.0,
            ),
        ]
    )
    samples = climatology_samples(
        era5,
        adjustment,
        "Alfa",
        "t2m_max",
        "2024-02-29",
        "2022-01-01",
        "2026-11-01",
    )
    # 2023-02-28 doy 59 vs target doy 59: distance 0. 2023-03-05 doy 64: 5.
    assert sorted(samples.tolist()) == [25.0, 99.0]


def test_observations_long_prefers_regtemp_and_reports_differences() -> None:
    # Rule 6: regtemp is primary per station-day; observaciones fills only
    # uncovered days; overlapping differences are counted and sized.
    region = {
        "id": "synth",
        "timezone": "America/Argentina/Buenos_Aires",
        "stations": [
            {
                "id": "alfa",
                "name": "Alfa",
                "lat": -24.0,
                "lon": -65.0,
                "ghcn_id": "AR000087007",
            }
        ],
    }
    catalogue = {"87007": "ALFA OBSERVATORIO"}
    regtemp = pd.DataFrame(
        [
            # Both products carry 11-12 with differing t2m_max.
            dict(smn_name="ALFA OBSERVATORIO", time="2026-11-12", t2m_max=30.0, t2m_min=15.0),
            # Covered by regtemp only.
            dict(smn_name="ALFA OBSERVATORIO", time="2026-11-13", t2m_max=31.0, t2m_min=16.0),
        ]
    )
    observ = pd.DataFrame(
        [
            dict(smn_name="ALFA OBSERVATORIO", time="2026-11-12", t2m_max=33.0, t2m_min=15.0),
            # observaciones-only day: kept as a fill row.
            dict(smn_name="ALFA OBSERVATORIO", time="2026-11-14", t2m_max=29.0, t2m_min=14.0),
        ]
    )
    out, diffs = observations_long(
        [
            ("observaciones", observ),
            ("regtemp", regtemp),
        ],
        region,
        catalogue,
    )
    assert set(out["location"]) == {"Alfa"}
    day12 = out.loc[(out["time"] == pd.Timestamp("2026-11-12")) & out["variable"].eq("t2m_max")]
    # regtemp wins the overlapping day even though observaciones came last.
    assert day12["value"].tolist() == [30.0]
    day14 = out.loc[(out["time"] == pd.Timestamp("2026-11-14")) & out["variable"].eq("t2m_max")]
    assert day14["value"].tolist() == [29.0]  # fill from observaciones
    # Differences: t2m_max on 11-12 differs by 3.0; t2m_min identical.
    assert diffs["n_comparable"] == 2
    assert diffs["n_differ"] == 1
    assert diffs["max_abs_diff"] == pytest.approx(3.0)
    assert diffs["mean_abs_diff"] == pytest.approx(3.0)


def test_parse_payload_zip_reads_both_fixed_width_layouts(tmp_path: Path) -> None:
    import zipfile

    observ_text = "\n".join(
        [
            " FECHA    TMAX  TMIN  NOMBRE",
            " -------- ----- ----- ----------------------------------------",
            " 12112026  30.0  15.0 ALFA OBSERVATORIO",
            "",
        ]
    )
    regtemp_text = "\n".join(
        [
            "FECHA    TMAX  TMIN  NOMBRE",
            "-------- ----- ----- ----------------------------------------",
            "12112026  31.0  16.0 ALFA OBSERVATORIO",
            "",
        ]
    )
    paths: dict[str, Path] = {}
    for kind, text in (("observaciones", observ_text), ("regtemp", regtemp_text)):
        path = tmp_path / f"{kind}.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(f"{kind}.txt", text.encode("latin-1"))
        paths[kind] = path

    observ = _parse_payload_zip(paths["observaciones"], "observaciones")
    assert list(observ.columns) == ["time", "smn_name", "t2m_max", "t2m_min"]
    assert observ.iloc[0]["t2m_max"] == pytest.approx(30.0)
    regtemp = _parse_payload_zip(paths["regtemp"], "regtemp")
    assert "regtemp_name" not in regtemp.columns
    assert regtemp.iloc[0]["t2m_max"] == pytest.approx(31.0)
    with pytest.raises(ValueError, match="unknown payload kind"):
        _parse_payload_zip(paths["regtemp"], "datohorario")


def test_load_member_counts_reads_the_nominal_counts_from_sources_yaml() -> None:
    from prisma.ingest.base import find_repo_root

    counts = load_member_counts(find_repo_root())
    assert counts["gfs_seamless"] == 31
    assert counts["ecmwf_ifs025"] == 51


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


def test_persistence_never_looks_back_past_a_missing_reference_day() -> None:
    # Rule 3: if the last completed local day (11-10) is missing, persistence
    # is n/a for that case — the 11-08 observation must NOT be carried forward.
    observations = pd.DataFrame(
        [
            dict(location="Alfa", variable="t2m_max", time="2026-11-08", value=5.0),
            dict(location="Alfa", variable="t2m_max", time="2026-11-09", value=9.0),
        ]
    )
    value = persistence_value(
        observations, "Alfa", "t2m_max", "2026-11-11T12:00:00Z"
    )
    assert pd.isna(value)


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
        member_counts={"gfs_seamless": 3},  # 3 of 3 present >= 80%
    )
    assert len(scored) == 1
    row = scored.iloc[0]
    assert row["case_status"] == "scored"
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
        member_counts={"gfs_seamless": 1},  # 1 of 1 usable: the case is scored
    )
    assert scored.iloc[0]["case_status"] == "scored"
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
                case_status="scored",
                n_present_members=5,
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
                case_status="scored",
                n_present_members=5,
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
    assert cell["n_missing"] == 0
    assert cell["n_climatology"] == 2
    assert cell["n_persistence"] == 1
    assert cell["crps_raw"] == pytest.approx(2.0)
    assert cell["crps_climatology"] == pytest.approx(2.0)
    assert cell["crps_persistence"] == pytest.approx(1.0)
    # Rule 4: n = 2 < 10 matured pairs -> flagged, skill scores blank.
    assert bool(cell["insufficient"]) is True
    assert pd.isna(cell["crpss_vs_climatology"])
    assert pd.isna(cell["crpss_vs_persistence"])


def test_leaderboard_flags_cells_below_ten_pairs_and_keeps_their_n() -> None:
    # Rule 4/5: 9 matured pairs -> insufficient; 10 -> scored. Per lead day,
    # nothing pooled across leads to reach the minimum.
    rows = []
    for i in range(9):
        rows.append(
            dict(
                issue_time=f"2026-11-{11 + i:02d}T02:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time=f"2026-11-{12 + i:02d}",
                lead_day=1,
                stratum="00:00-11:59",
                obs_value=2.0,
                case_status="scored",
                n_present_members=5,
                raw_crps=1.0,
                climatology_crps=2.0,
                persistence_crps=1.0,
            )
        )
    for i in range(10):
        rows.append(
            dict(
                issue_time=f"2026-11-{11 + i:02d}T02:00:00Z",
                model="gfs_seamless",
                location="Alfa",
                variable="t2m_max",
                time=f"2026-11-{12 + i:02d}",
                lead_day=2,
                stratum="00:00-11:59",
                obs_value=2.0,
                case_status="scored",
                n_present_members=5,
                raw_crps=1.0,
                climatology_crps=2.0,
                persistence_crps=1.0,
            )
        )
    board = leaderboard(pd.DataFrame(rows))
    by_lead = {int(row.lead_day): row for row in board.itertuples(index=False)}
    assert by_lead[1].n_pairs == 9
    assert bool(by_lead[1].insufficient) is True
    assert pd.isna(by_lead[1].crpss_vs_climatology)
    assert by_lead[2].n_pairs == 10
    assert bool(by_lead[2].insufficient) is False
    assert by_lead[2].crpss_vs_climatology == pytest.approx(0.5)


def test_leaderboard_counts_missing_member_cases_without_scoring_them() -> None:
    # Rule 1: a missing_members case contributes to n_missing, never to n_pairs.
    fixture = _scored_fixture()
    extra = fixture.iloc[0].copy()
    extra["case_status"] = "missing_members"
    extra["raw_crps"] = float("nan")
    extra["climatology_crps"] = float("nan")
    extra["persistence_crps"] = float("nan")
    board = leaderboard(pd.concat([fixture, pd.DataFrame([extra])], ignore_index=True))
    cell = board.iloc[0]
    assert cell["n_pairs"] == 2
    assert cell["n_missing"] == 1


def test_leaderboard_splits_by_issue_hour_stratum() -> None:
    strata = leaderboard(_scored_fixture(), by_stratum=True)
    assert sorted(strata["stratum"]) == ["00:00-11:59", "12:00-23:59"]
    morning = strata.loc[strata["stratum"].eq("00:00-11:59")].iloc[0]
    assert morning["n_pairs"] == 1
    assert pd.isna(morning["crps_persistence"])


def test_write_results_emits_three_files(tmp_path: Path) -> None:
    board = leaderboard(_scored_fixture())
    strata = leaderboard(_scored_fixture(), by_stratum=True)
    written = write_results(
        board,
        strata,
        tmp_path / "verification",
        issue_dates=15,
        product_diffs={
            "n_comparable": 4,
            "n_differ": 1,
            "max_abs_diff": 0.6,
            "mean_abs_diff": 0.6,
        },
    )
    assert [path.name for path in written] == [
        "leaderboard.csv",
        "leaderboard_by_issue_hour_stratum.csv",
        "leaderboard.md",
    ]
    reread = pd.read_csv(written[0])
    assert len(reread) == 1
    assert "insufficient" in reread.columns
    markdown = written[2].read_text(encoding="utf-8")
    assert "15 distinct issue dates archived" in markdown
    assert "flagged `insufficient`" in markdown
    assert "2026-11-14" in markdown
    # Rule 6 output: number and size of the regtemp/observaciones differences.
    assert "4 value pair(s), 1 differing" in markdown
    assert "0.600 degC" in markdown


# --- Part 3: end-to-end dry run on a synthetic archive -----------------------
#
# The whole gated path (listing -> download -> parquet/zips -> pairing ->
# scoring -> leaderboard -> written results) runs against a temp repository.
# Every input mirrors the real archive layout: forecast parquets carry the
# canonical COLUMNS, the SMN payloads use the exact fixed-width windows, and
# the HF listing/dowload calls are injected. Nothing real is read.

E2E_SPACING_DAYS = 5
E2E_MORNING_ISSUES = 10
E2E_STATION = "ALFA OBSERVATORIO"


def _e2e_issue_days() -> list[pd.Timestamp]:
    return [
        pd.Timestamp("2026-11-11") + pd.Timedelta(days=E2E_SPACING_DAYS * i)
        for i in range(GATE_ISSUE_DATES)
    ]


def _regtemp_line(day: pd.Timestamp, tmax: float, tmin: float) -> str:
    return f"{day.strftime('%d%m%Y')}  {tmax:>5.1f} {tmin:>5.1f} {E2E_STATION}"


def _observaciones_line(day: pd.Timestamp, tmax: float, tmin: float) -> str:
    return f" {day.strftime('%d%m%Y')} {tmax:>5.1f} {tmin:>5.1f} {E2E_STATION}"


def _write_payload_zip(path: Path, kind: str, lines: list[str]) -> None:
    import zipfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"{kind}.txt", ("\n".join(lines) + "\n").encode("latin-1"))


def _e2e_forecast_frame(rows: list[dict[str, object]]) -> pd.DataFrame:
    from prisma.ingest.base import COLUMNS

    frame = pd.DataFrame(rows)
    frame["source"] = "openmeteo-ensemble"
    frame["unit"] = "degC"
    frame["lat"] = -24.0
    frame["lon"] = -65.0
    frame["day_convention"] = "local_calendar"
    frame["retrieved_at"] = pd.Timestamp("2026-11-14T00:00:00")
    frame["member"] = frame["member"].astype("Int64")
    frame["lead_day"] = frame["lead_day"].astype("Int64")
    return frame[COLUMNS]


def _e2e_workspace(
    tmp_path: Path,
) -> tuple[Path, Callable[[], list[str]], Callable[[str, str], Path]]:
    root = tmp_path / "repo"
    days = _e2e_issue_days()

    (root / "configs" / "regions").mkdir(parents=True)
    (root / "configs" / "regions" / "argentina.yaml").write_text(
        "\n".join(
            [
                "id: synth",
                "timezone: America/Argentina/Buenos_Aires",
                "history_start: 2024-01-01",
                "stations:",
                "  - id: alfa",
                "    name: Alfa",
                "    lat: -24.0",
                "    lon: -65.0",
                "    ghcn_id: AR000087007",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "configs" / "sources.yaml").write_text(
        "\n".join(
            [
                "sources:",
                "  - id: openmeteo-ensemble",
                "    options:",
                "      member_counts:",
                "        gfs_seamless: 5",
                "        ecmwf_ifs025: 9",
                "",
            ]
        ),
        encoding="utf-8",
    )
    catalogue = root / "data" / "smn_probe" / "estaciones" / "estaciones_smn.txt"
    catalogue.parent.mkdir(parents=True)
    catalogue.write_text(
        E2E_STATION.ljust(30) + " " * 80 + "87007" + " \n", encoding="latin-1"
    )

    (root / "data" / "raw").mkdir(parents=True)
    era5 = pd.DataFrame(
        {
            "location": "Alfa",
            "variable": "t2m_max",
            "time": pd.date_range("2024-01-01", "2024-12-31", freq="D"),
            "value": 10.0,
            "source": "openmeteo-era5",
        }
    )
    era5.to_parquet(root / "data" / "raw" / "openmeteo-era5.parquet", index=False)
    adjustment = root / "results" / "climatology_adjustment" / "smn_era5_adjustment.csv"
    adjustment.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            dict(
                location="Alfa",
                variable="t2m_max",
                calendar_month=month,
                mean_diff_smn_minus_era5=2.0,
            )
            for month in range(1, 13)
        ]
    ).to_csv(adjustment, index=False)

    rows_by_day: dict[pd.Timestamp, list[dict[str, object]]] = {}
    target_days: set[pd.Timestamp] = set()
    reference_days: set[pd.Timestamp] = set()
    for i, day in enumerate(days):
        morning = i < E2E_MORNING_ISSUES
        issue_time = pd.Timestamp(
            f"{day.strftime('%Y-%m-%d')}T{'02:00:00' if morning else '15:00:00'}"
        )
        target = day + pd.Timedelta(days=1)
        target_days.add(target)
        day_rows = rows_by_day.setdefault(day, [])
        for model, members in (("gfs_seamless", 5), ("ecmwf_ifs025", 7)):
            for member in range(members):
                day_rows.append(
                    dict(
                        issue_time=issue_time,
                        model=model,
                        location="Alfa",
                        variable="t2m_max",
                        time=target,
                        lead_day=1,
                        member=member,
                        value=15.0,
                        quality_flag="ok",
                    )
                )
        if i < 3:
            target2 = day + pd.Timedelta(days=2)
            target_days.add(target2)
            for member in range(5):
                day_rows.append(
                    dict(
                        issue_time=issue_time,
                        model="gfs_seamless",
                        location="Alfa",
                        variable="t2m_max",
                        time=target2,
                        lead_day=2,
                        member=member,
                        value=15.0,
                        quality_flag="ok",
                    )
                )
        reference_days.add(day - pd.Timedelta(days=2 if morning else 1))

    # A day may not be both a scored target and a persistence reference.
    assert target_days.isdisjoint(reference_days)

    forecast_paths: list[str] = []
    for day, day_rows in rows_by_day.items():
        rel = (
            Path("forecasts")
            / day.strftime("%Y-%m-%d")
            / f"openmeteo-ensemble_{day.strftime('%Y-%m-%d')}.parquet"
        )
        local = root / rel
        local.parent.mkdir(parents=True, exist_ok=True)
        _e2e_forecast_frame(day_rows).to_parquet(local, index=False)
        forecast_paths.append(rel.as_posix())

    # Target days: regtemp carries 14.0/5.0, observaciones carries a differing
    # 17.0/5.0 for the same days (regtemp must win) and fills the reference
    # days no regtemp snapshot covers.
    regtemp_lines = ["FECHA    TMAX  TMIN  NOMBRE", "-------- ----- ----- -------------"]
    observ_lines = [" FECHA    TMAX  TMIN  NOMBRE", " -------- ----- ----- -------------"]
    for target in sorted(target_days):
        regtemp_lines.append(_regtemp_line(target, 14.0, 5.0))
        observ_lines.append(_observaciones_line(target, 17.0, 5.0))
    for reference in sorted(reference_days):
        observ_lines.append(_observaciones_line(reference, 10.0, 0.0))
    regtemp_rel = "observations/smn/regtemp/2026-11-25/regtemp.zip"
    observ_rel = "observations/smn/observaciones/2026-11-25/observaciones.zip"
    _write_payload_zip(root / regtemp_rel, "regtemp", regtemp_lines)
    _write_payload_zip(root / observ_rel, "observaciones", observ_lines)

    def list_files() -> list[str]:
        return [*forecast_paths, regtemp_rel, observ_rel, "README.md"]

    def download(repo_id: str, repo_path: str) -> Path:
        return root / repo_path

    return root, list_files, download


def test_run_above_gate_end_to_end_on_synthetic_archive(
    tmp_path: Path, capsys: pytest.CaptureFixture
) -> None:
    root, list_files, download = _e2e_workspace(tmp_path)
    assert not (root / "results" / "verification").exists()

    code = run_above_gate(
        GATE_ISSUE_DATES, list_files=list_files, download=download, root=root
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "gated run: 15 issue dates" in out
    assert "15 cases recorded as missing_members" in out
    assert "18 regtemp/observaciones difference(s) of 36 overlapping value(s)" in out
    assert "wrote results/verification/leaderboard.csv" in out

    board = pd.read_csv(root / "results" / "verification" / "leaderboard.csv")
    assert len(board) == 3

    # gfs_seamless, lead 1: 15 matured pairs, all analytic values exact.
    # raw CRPS |15-14| = 1; climatology |12-14| = 2; persistence |10-14| = 4.
    gfs_lead1 = board.loc[
        board["model"].eq("gfs_seamless") & board["lead_day"].eq(1)
    ].iloc[0]
    assert gfs_lead1["n_pairs"] == 15
    assert gfs_lead1["n_missing"] == 0
    assert gfs_lead1["n_climatology"] == 15
    assert gfs_lead1["n_persistence"] == 15
    assert bool(gfs_lead1["insufficient"]) is False
    assert gfs_lead1["crps_raw"] == pytest.approx(1.0)
    assert gfs_lead1["crps_climatology"] == pytest.approx(2.0)
    assert gfs_lead1["crps_persistence"] == pytest.approx(4.0)
    assert gfs_lead1["crpss_vs_climatology"] == pytest.approx(0.5)
    assert gfs_lead1["crpss_vs_persistence"] == pytest.approx(0.75)

    # gfs_seamless, lead 2: only 3 issues pair -> below MIN_SAMPLE, no skill.
    gfs_lead2 = board.loc[
        board["model"].eq("gfs_seamless") & board["lead_day"].eq(2)
    ].iloc[0]
    assert gfs_lead2["n_pairs"] == 3
    assert bool(gfs_lead2["insufficient"]) is True
    assert gfs_lead2["crps_raw"] == pytest.approx(1.0)
    assert pd.isna(gfs_lead2["crpss_vs_climatology"])

    # ecmwf_ifs025 delivers 7 of its nominal 9 members (78% < 80%): every case
    # is missing_members, never scored, but still counted.
    ecmwf = board.loc[board["model"].eq("ecmwf_ifs025")].iloc[0]
    assert ecmwf["lead_day"] == 1
    assert ecmwf["n_pairs"] == 0
    assert ecmwf["n_missing"] == 15
    assert bool(ecmwf["insufficient"]) is True
    assert pd.isna(ecmwf["crps_raw"])

    strata = pd.read_csv(
        root / "results" / "verification" / "leaderboard_by_issue_hour_stratum.csv"
    )
    morning = strata.loc[
        strata["model"].eq("gfs_seamless")
        & strata["lead_day"].eq(1)
        & strata["stratum"].eq("00:00-11:59")
    ].iloc[0]
    assert morning["n_pairs"] == 10
    assert bool(morning["insufficient"]) is False
    afternoon = strata.loc[
        strata["model"].eq("gfs_seamless")
        & strata["lead_day"].eq(1)
        & strata["stratum"].eq("12:00-23:59")
    ].iloc[0]
    assert afternoon["n_pairs"] == 5
    assert bool(afternoon["insufficient"]) is True

    markdown = (root / "results" / "verification" / "leaderboard.md").read_text(
        encoding="utf-8"
    )
    assert "15 distinct issue dates archived" in markdown
    assert f"fewer than {MIN_SAMPLE} matured pairs" in markdown
    assert "36 value pair(s), 18 differing" in markdown
    assert "3.000 degC" in markdown
    assert "2026-11-14" in markdown
