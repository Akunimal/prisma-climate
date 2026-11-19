"""Tests for the isolated METAR observation reference archiver and SMN safeguards."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from prisma.ingest.metar_archive import (
    archive_metar_region,
    parse_raw_reports_to_frame,
    validate_retention_hours,
    validate_target_path,
    write_partitioned_observations,
)


def test_retention_hours_validation() -> None:
    """Archiver must enforce the sliding window constraint [24, 72] with zero backfill claims."""
    assert validate_retention_hours(24) == 24
    assert validate_retention_hours(48) == 48
    assert validate_retention_hours(72) == 72

    with pytest.raises(ValueError, match="sliding METAR retention window"):
        validate_retention_hours(12)

    with pytest.raises(ValueError, match="sliding METAR retention window"):
        validate_retention_hours(100)


def test_smn_isolation_safeguards() -> None:
    """Target paths must NEVER touch SMN stores or non-metar observation paths."""
    # Valid METAR paths
    validate_target_path(Path("observations/metar/south_america/2026/santiago_pudahuel.parquet"))
    validate_target_path(Path("data/test/observations/metar/europe/2025/paris_cdg.parquet"))

    # Forbidden SMN stores
    with pytest.raises(ValueError, match="touches forbidden store"):
        validate_target_path(Path("observations/smn/datohorario/2026-11-19"))

    with pytest.raises(ValueError, match="touches forbidden store"):
        validate_target_path(Path("observations/hourly/smn-argentina.parquet"))

    with pytest.raises(ValueError, match="touches forbidden store"):
        validate_target_path(Path("observations/daily/smn-argentina.parquet"))

    # Path outside observations/metar
    with pytest.raises(ValueError, match="must be rooted under 'observations/metar/'"):
        validate_target_path(Path("data/forecasts/openmeteo/2026-11-19.parquet"))


def test_timestamp_keying_from_metar_obstime() -> None:
    """Partition year and timestamps must be strictly derived from obsTime, NEVER system clock."""
    station_lookup = {
        "SCEL": {"id": "santiago_pudahuel", "region": "south_america"},
        "LFPG": {"id": "paris_cdg", "region": "europe"},
    }

    # ObsTime: 2024-06-15 12:00:00 UTC (epoch: 1718452800)
    # ObsTime: 2026-01-10 08:30:00 UTC (epoch: 1768033800)
    raw_reports = [
        {
            "icaoId": "SCEL",
            "obsTime": 1718452800,
            "rawOb": "SCEL 151200Z 18005KT 9999 FEW030 14/08 Q1018 NOSIG",
            "temp": 14.0,
            "precip": None,
        },
        {
            "icaoId": "LFPG",
            "obsTime": 1768033800,
            "rawOb": "LFPG 100830Z 27010KT 9999 BKN020 05/02 Q1020",
            "temp": 5.0,
            "precip": 0.0,
        },
    ]

    df = parse_raw_reports_to_frame(raw_reports, station_lookup, retrieved_at_utc="2026-11-19T08:00:00Z")
    assert len(df) == 2

    scel_row = df[df["icao"] == "SCEL"].iloc[0]
    assert scel_row["partition_year"] == 2024
    assert scel_row["obs_time_utc"] == "2024-06-15T12:00:00Z"
    assert scel_row["temperature_c"] == 14.0

    lfpg_row = df[df["icao"] == "LFPG"].iloc[0]
    assert lfpg_row["partition_year"] == 2026
    assert lfpg_row["obs_time_utc"] == "2026-01-10T08:30:00Z"
    assert lfpg_row["temperature_c"] == 5.0


def test_missing_values_not_imputed() -> None:
    """Missing temperature or precipitation must remain null/None without imputation."""
    station_lookup = {
        "SCEL": {"id": "santiago_pudahuel", "region": "south_america"},
    }

    # Report with nil/missing temp
    raw_reports = [
        {
            "icaoId": "SCEL",
            "obsTime": 1718452800,
            "rawOb": "SCEL 151200Z 18005KT 9999 ///// Q1018",
            "temp": None,
            "precip": None,
        }
    ]

    df = parse_raw_reports_to_frame(raw_reports, station_lookup, retrieved_at_utc="2026-11-19T08:00:00Z")
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["temperature_c"])
    assert pd.isna(df.iloc[0]["precip_mm"])


def test_partitioned_write_and_deduplication() -> None:
    """Test file writing into observations/metar/<region>/<year>/<station_id>.parquet and deduplication."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir)
        station_lookup = {
            "SCEL": {"id": "santiago_pudahuel", "region": "south_america"},
        }

        # First batch
        reports_1 = [
            {
                "icaoId": "SCEL",
                "obsTime": 1718452800,
                "rawOb": "SCEL 151200Z 18005KT 9999 FEW030 14/08 Q1018",
                "temp": 14.0,
                "precip": None,
            }
        ]
        df_1 = parse_raw_reports_to_frame(reports_1, station_lookup, "2026-11-19T08:00:00Z")
        written_1 = write_partitioned_observations(df_1, base_dir)

        assert len(written_1) == 1
        expected_path = base_dir / "observations" / "metar" / "south_america" / "2024" / "santiago_pudahuel.parquet"
        assert written_1[0] == expected_path
        assert expected_path.exists()

        saved_1 = pd.read_parquet(expected_path)
        assert len(saved_1) == 1
        assert saved_1.iloc[0]["obs_epoch"] == 1718452800

        # Second batch with 1 duplicate and 1 new record
        reports_2 = [
            {
                "icaoId": "SCEL",
                "obsTime": 1718452800,
                "rawOb": "SCEL 151200Z 18005KT 9999 FEW030 14/08 Q1018",
                "temp": 14.0,
                "precip": None,
            },
            {
                "icaoId": "SCEL",
                "obsTime": 1718456400,
                "rawOb": "SCEL 151300Z 18005KT 9999 FEW030 15/08 Q1018",
                "temp": 15.0,
                "precip": None,
            },
        ]
        df_2 = parse_raw_reports_to_frame(reports_2, station_lookup, "2026-11-19T09:00:00Z")
        written_2 = write_partitioned_observations(df_2, base_dir)

        assert len(written_2) == 1
        saved_2 = pd.read_parquet(expected_path)
        assert len(saved_2) == 2  # Deduplicated from 3 total records
        assert list(saved_2["obs_epoch"]) == [1718452800, 1718456400]
