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


def test_main_upload_requires_hf_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """When --upload is passed without HF_TOKEN or HF_DATASET_REPO, main must exit with code 2."""
    from prisma.ingest.metar_archive import main

    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)

    exit_code = main(["--upload", "--region", "south_america"])
    assert exit_code == 2


def test_upload_and_sync_helpers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test sync_existing_from_hf and upload_metar_to_hf helper behavior with mocked HfApi."""
    import sys
    from unittest.mock import MagicMock
    from prisma.ingest.metar_archive import sync_existing_from_hf, upload_metar_to_hf

    mock_api = MagicMock()
    mock_api.list_repo_files.return_value = [
        "observations/metar/south_america/2026/santiago_pudahuel.parquet",
        "forecasts/2026-11-19/model.parquet",
    ]

    mock_download = MagicMock(return_value="/tmp/test.parquet")
    mock_hf = MagicMock()
    mock_hf.HfApi = MagicMock(return_value=mock_api)
    mock_hf.hf_hub_download = mock_download

    monkeypatch.setitem(sys.modules, "huggingface_hub", mock_hf)

    # Test sync
    downloaded = sync_existing_from_hf(tmp_path, "repo/test", "mock_token")
    assert len(downloaded) == 1
    mock_download.assert_called_once()

    # Test upload with empty dir (should return False)
    assert not upload_metar_to_hf(tmp_path, "repo/test", "mock_token")

    # Create dummy observation file and test upload
    dummy_file = tmp_path / "observations" / "metar" / "south_america" / "2026" / "st1.parquet"
    dummy_file.parent.mkdir(parents=True, exist_ok=True)
    dummy_file.write_text("dummy")

    assert upload_metar_to_hf(tmp_path, "repo/test", "mock_token")
    mock_api.upload_folder.assert_called_once()

