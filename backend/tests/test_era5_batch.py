"""Deterministic offline unit tests for the Global ERA5 Batch Ingest module (Priority 2).

All tests run 100% offline with zero network calls and mocked HTTP / sleep hooks.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import pytest
import requests

from prisma.ingest.era5_batch import (
    EXPECTED_COLUMNS,
    CheckpointManager,
    Era5Chunk,
    fetch_chunk_with_retry,
    merge_and_save,
    parse_era5_payload,
    parse_retry_after,
    plan_chunks,
    run_batch_ingest,
    validate_era5_schema,
)
from prisma.report.metar_discrepancies import compare_metar_era5


def _make_dummy_station(idx: int, region: str = "south_america") -> dict[str, Any]:
    return {
        "id": f"station_{idx:03d}",
        "name": f"Station {idx:03d}",
        "lat": -34.0 + (idx * 0.1),
        "lon": -58.0 + (idx * 0.1),
        "icao": f"SA{idx:02d}",
        "region": region,
    }


def test_plan_chunks_113_stations_and_date_windows() -> None:
    stations = [_make_dummy_station(i) for i in range(113)]
    chunks = plan_chunks(
        stations,
        "2026-01-01",
        "2026-03-31",
        station_batch_size=10,
        chunk_days=30,
    )
    # 113 stations / 10 = 12 batches (11 of 10, 1 of 3)
    # 2026-01-01 to 2026-03-31 (90 days) / 30 = 3 slices
    assert len(chunks) == 12 * 3
    # Check remainder batch has 3 stations
    remainder_chunks = [c for c in chunks if "b011" in c.chunk_id]
    assert len(remainder_chunks) == 3
    for rc in remainder_chunks:
        assert len(rc.stations) == 3

    # Check IDs are unique
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_parse_retry_after() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("invalid") is None
    # HTTP date in the future
    future_date = "Wed, 21 Oct 2099 07:28:00 GMT"
    diff = parse_retry_after(future_date)
    assert diff is not None and diff > 0


def test_parse_era5_payload_multi_and_single_station() -> None:
    st1 = _make_dummy_station(1)
    st2 = _make_dummy_station(2)

    # Multi-station list response
    multi_payload = [
        {
            "latitude": st1["lat"],
            "longitude": st1["lon"],
            "daily": {
                "time": ["2026-11-01", "2026-11-02"],
                "temperature_2m_max": [25.0, 26.5],
                "temperature_2m_min": [15.0, 16.0],
                "precipitation_sum": [0.0, 2.5],
            },
        },
        {
            "latitude": st2["lat"],
            "longitude": st2["lon"],
            "daily": {
                "time": ["2026-11-01", "2026-11-02"],
                "temperature_2m_max": [22.0, 23.0],
                "temperature_2m_min": [12.0, 13.0],
                "precipitation_sum": [5.0, 0.0],
            },
        },
    ]

    df_multi = parse_era5_payload(multi_payload, [st1, st2])
    assert len(df_multi) == 2 * 2 * 3  # 2 stations * 2 days * 3 variables = 12 rows
    validate_era5_schema(df_multi)
    assert set(df_multi.columns) == set(EXPECTED_COLUMNS)
    assert set(df_multi["location"]) == {st1["name"], st2["name"]}
    assert set(df_multi["variable"]) == {"t2m_max", "t2m_min", "precip"}

    # Single-station dict response (e.g. remainder batch)
    single_payload = multi_payload[0]
    df_single = parse_era5_payload(single_payload, [st1])
    assert len(df_single) == 6
    validate_era5_schema(df_single)
    assert df_single["location"].iloc[0] == st1["name"]


def test_fetch_chunk_with_retry_pacing_and_backoff() -> None:
    chunk = Era5Chunk(
        chunk_id="test_chunk",
        stations=(_make_dummy_station(1),),
        start_date="2026-11-01",
        end_date="2026-11-02",
    )

    sleep_calls: list[float] = []

    def mock_sleep(sec: float) -> None:
        sleep_calls.append(sec)

    attempts = 0

    def mock_getter(url: str, params: dict[str, Any]) -> Any:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            # First attempt: 429 with Retry-After 5
            resp = requests.Response()
            resp.status_code = 429
            resp.headers["Retry-After"] = "5"
            err = requests.HTTPError("429 rate limit")
            err.response = resp
            err.retry_after = 5.0
            raise err
        if attempts == 2:
            # Second attempt: 503 transient
            resp = requests.Response()
            resp.status_code = 503
            err = requests.HTTPError("503 unavailable")
            err.response = resp
            raise err
        # Third attempt: success
        return {
            "latitude": chunk.stations[0]["lat"],
            "longitude": chunk.stations[0]["lon"],
            "daily": {
                "time": ["2026-11-01"],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [10.0],
                "precipitation_sum": [0.0],
            },
        }

    res = fetch_chunk_with_retry(
        chunk,
        http_get=mock_getter,
        sleep_fn=mock_sleep,
        max_retries=5,
    )
    assert attempts == 3
    assert len(sleep_calls) == 2
    assert sleep_calls[0] >= 5.0  # Honored Retry-After: 5
    assert "daily" in res


def test_fetch_chunk_fatal_400_no_retry() -> None:
    chunk = Era5Chunk(
        chunk_id="test_chunk_fatal",
        stations=(_make_dummy_station(1),),
        start_date="2026-11-01",
        end_date="2026-11-02",
    )

    attempts = 0

    def mock_fatal_getter(url: str, params: dict[str, Any]) -> Any:
        nonlocal attempts
        attempts += 1
        resp = requests.Response()
        resp.status_code = 400
        err = requests.HTTPError("400 Bad Request")
        err.response = resp
        raise err

    with pytest.raises(requests.HTTPError):
        fetch_chunk_with_retry(chunk, http_get=mock_fatal_getter, max_retries=5)
    # Should fail immediately on 400 without burning retries
    assert attempts == 1


def test_checkpoint_resume_skips_completed_chunks(tmp_path: Path) -> None:
    chk_dir = tmp_path / "checkpoint"
    mgr = CheckpointManager(chk_dir)

    st1 = _make_dummy_station(1)
    df_chunk = parse_era5_payload(
        {
            "latitude": st1["lat"],
            "longitude": st1["lon"],
            "daily": {
                "time": ["2026-11-01"],
                "temperature_2m_max": [20.0],
                "temperature_2m_min": [10.0],
                "precipitation_sum": [0.0],
            },
        },
        [st1],
    )

    assert not mgr.is_completed("chunk_001")
    mgr.record_completed_chunk("chunk_001", df_chunk)
    assert mgr.is_completed("chunk_001")

    # New manager instance with same dir reads manifest
    mgr2 = CheckpointManager(chk_dir)
    assert mgr2.is_completed("chunk_001")
    assert len(mgr2.get_staged_files()) == 1


def test_atomic_merge_and_deduplication(tmp_path: Path) -> None:
    target_parquet = tmp_path / "openmeteo-era5.parquet"
    st1 = _make_dummy_station(1)

    # 1. Seed existing parquet with older observation
    df_old = parse_era5_payload(
        {
            "latitude": st1["lat"],
            "longitude": st1["lon"],
            "daily": {
                "time": ["2026-11-01", "2026-11-02"],
                "temperature_2m_max": [19.0, 20.0],
                "temperature_2m_min": [9.0, 10.0],
                "precipitation_sum": [0.0, 0.0],
            },
        },
        [st1],
    )
    df_old.to_parquet(target_parquet, index=False)

    # 2. Staged chunk with updated 2026-11-02 and new 2026-11-03
    df_new = parse_era5_payload(
        {
            "latitude": st1["lat"],
            "longitude": st1["lon"],
            "daily": {
                "time": ["2026-11-02", "2026-11-03"],
                "temperature_2m_max": [22.0, 23.0],  # updated 2026-11-02 value
                "temperature_2m_min": [11.0, 12.0],
                "precipitation_sum": [1.0, 0.0],
            },
        },
        [st1],
    )
    staged_file = tmp_path / "stage_001.parquet"
    df_new.to_parquet(staged_file, index=False)

    # Merge
    out_path = merge_and_save([staged_file], target_parquet)
    assert out_path.is_file()

    merged_df = pd.read_parquet(out_path)
    validate_era5_schema(merged_df)

    # 3 distinct dates (Nov 1, 2, 3) * 3 variables = 9 rows
    assert len(merged_df) == 9
    t2m_nov2 = merged_df.loc[
        merged_df["time"].eq(pd.Timestamp("2026-11-02")) & merged_df["variable"].eq("t2m_max")
    ]
    # Kept latest updated value 22.0
    assert float(t2m_nov2["value"].iloc[0]) == 22.0


def test_era5_batch_joins_with_metar_discrepancies() -> None:
    """Verifies batch-produced ERA5 DataFrame joins cleanly with METAR in metar_discrepancies."""
    st = {
        "id": "cairo_intl",
        "name": "Cairo International",
        "lat": 30.122,
        "lon": 31.406,
        "icao": "HECA",
        "region": "africa",
    }

    era5_df = parse_era5_payload(
        {
            "latitude": st["lat"],
            "longitude": st["lon"],
            "daily": {
                "time": ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"],
                "temperature_2m_max": [25.0, 26.0, 27.0, 28.0, 29.0],
                "temperature_2m_min": [15.0, 16.0, 17.0, 18.0, 19.0],
                "precipitation_sum": [0.0, 0.0, 0.0, 0.0, 0.0],
            },
        },
        [st],
    )

    # Synthetic METAR frame with 3.5 C runway bias on t2m_max
    metar_rows: list[dict[str, Any]] = []
    for d_str, tmax, tmin in zip(
        ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21", "2026-11-22"],
        [28.5, 29.5, 30.5, 31.5, 32.5],  # exactly +3.5 C bias
        [15.1, 16.0, 17.2, 17.9, 19.0],  # near zero bias
        strict=True,
    ):
        metar_rows.append(
            {
                "location": st["name"],
                "variable": "t2m_max",
                "time": pd.Timestamp(d_str),
                "value": tmax,
                "quality_flag": "ok",
            }
        )
        metar_rows.append(
            {
                "location": st["name"],
                "variable": "t2m_min",
                "time": pd.Timestamp(d_str),
                "value": tmin,
                "quality_flag": "ok",
            }
        )
    metar_df = pd.DataFrame(metar_rows)

    report_table = compare_metar_era5(metar_df, era5_df, stations=[st])
    assert not report_table.empty
    assert len(report_table) == 2

    row_max = report_table.loc[report_table["variable"].eq("t2m_max")].iloc[0]
    assert row_max["location"] == st["name"]
    assert row_max["icao"] == "HECA"
    assert row_max["region"] == "africa"
    assert row_max["n_days"] == 5
    assert row_max["bias"] == 3.5
    assert "|bias| >= 3 C" in row_max["flags"]


def test_cli_dry_run_zero_network_calls(tmp_path: Path) -> None:
    res = run_batch_ingest(
        root=None,
        scope="global",
        start_date="2026-11-01",
        end_date="2026-11-05",
        station_batch_size=10,
        chunk_days=30,
        dry_run=True,
    )
    assert res["status"] == "dry_run"
    plan = res["plan"]
    assert plan["station_count"] == 113
    assert plan["scope"] == "global"
    assert plan["chunk_count"] > 0
