"""Decompose ERA5-vs-station t2m_max bias (plan section 3.6 follow-up).

Sequential adjustments, each reported with the residual bias that remains:

1. raw          — mean(ERA5 − station)
2. elevation    — lapse-rate correct the series from its source elevation to
                  station elevation (standard atmosphere, 6.5 °C/km)
3. sampling     — add the sub-hourly peak estimate missing from hourly-sampled
                  daily maxima (parabolic peak through the three hours around
                  the daily maximum of ERA5 hourly t2m)
4. day_convention — realign one series by the best lag in {−1, 0, +1} days

Step 2 must use the elevation the series actually represents:

- Open-Meteo's default response applies statistical downscaling to the 90 m
  DEM elevation at the requested point (``elevation`` field ≈ DEM, not model
  orography), so the stored connector data is a *downscaled* series.
- ``elevation=nan`` disables downscaling; the response elevation is then the
  average grid-cell height and the values are raw ERA5 grid output.

The collector therefore runs both series: ``downscaled`` (DEM as source
elevation) and ``raw_grid`` (grid-cell orography as source elevation).
Hourly sampling is estimated on a recent window only (rate limits) and
applied as a constant mean correction; the window is recorded in the output.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from ..ingest.base import utc_now
from ..ingest.openmeteo import ARCHIVE_URL, PAUSE_SECONDS, RETRIES, TIMEOUT

# Standard-atmosphere environmental lapse rate (positive: °C per km of height).
LAPSE_RATE_C_PER_KM = 6.5
DAY_LAGS = (-1, 0, 1)
HOURLY_PAUSE_SECONDS = PAUSE_SECONDS

# Persistent elevation=nan series cache, separate from the default downscaled
# archive (data/raw/openmeteo-era5.parquet), which the cron and notebook use.
RAW_GRID_CACHE_COLUMNS = ["location", "time", "value", "grid_elevation_m", "retrieved_at"]


def adjust_elevation(
    values: pd.Series,
    grid_elevation_m: float,
    station_elevation_m: float,
    lapse_rate_c_per_km: float = LAPSE_RATE_C_PER_KM,
) -> pd.Series:
    """Move grid-cell temperatures down (or up) to the station elevation."""
    delta_km = (float(grid_elevation_m) - float(station_elevation_m)) / 1000.0
    return values + lapse_rate_c_per_km * delta_km


def parabolic_peak(y_left: float, y_center: float, y_right: float) -> float | None:
    """Continuous peak of a parabola through three equally spaced samples.

    Returns None when the three points do not form a concave-down peak
    (denominator zero or non-negative curvature).
    """
    denom = y_left - 2.0 * y_center + y_right
    if denom >= 0:
        return None
    delta = 0.5 * (y_left - y_right) / denom
    if not -0.5 <= delta <= 0.5:
        return None
    return y_center - 0.25 * (y_left - y_right) * delta


def hourly_sampling_correction(hourly: pd.DataFrame) -> float | None:
    """Mean (parabolic peak − hourly max) over interior local days.

    ``hourly`` needs columns ``time`` (naive local timestamps) and ``value``.
    """
    frame = hourly.dropna(subset=["value"]).sort_values("time")
    if frame.empty:
        return None
    values = frame["value"].to_numpy(dtype=float)
    times = frame["time"].to_numpy()
    corrections: list[float] = []
    for i in range(1, len(values) - 1):
        # Only interior samples of the same local calendar day.
        day_prev = pd.Timestamp(times[i - 1]).date()
        day_here = pd.Timestamp(times[i]).date()
        day_next = pd.Timestamp(times[i + 1]).date()
        if not (day_prev == day_here == day_next):
            continue
        if not (values[i] >= values[i - 1] and values[i] >= values[i + 1]):
            continue
        peak = parabolic_peak(values[i - 1], values[i], values[i + 1])
        if peak is not None:
            corrections.append(peak - values[i])
    if not corrections:
        return None
    return float(pd.Series(corrections).mean())


def best_day_lag(
    era5: pd.Series,
    station: pd.Series,
    lags: tuple[int, ...] = DAY_LAGS,
) -> tuple[int, float]:
    """Lag (days) minimising mean absolute difference; returns (lag, mae)."""
    best_lag, best_mae = 0, float("inf")
    for lag in lags:
        shifted = station.shift(-lag)
        pair = pd.DataFrame({"a": era5.to_numpy(), "b": shifted.to_numpy()}, index=era5.index)
        pair = pair.dropna()
        if pair.empty:
            continue
        mae = float((pair["a"] - pair["b"]).abs().mean())
        if mae < best_mae:
            best_lag, best_mae = lag, mae
    return best_lag, best_mae


def bias_after_shift(era5: pd.Series, station: pd.Series, lag: int) -> float | None:
    """Mean(ERA5 − station) after shifting the station series by ``lag`` days."""
    shifted = station.shift(-lag)
    pair = pd.DataFrame({"a": era5.to_numpy(), "b": shifted.to_numpy()}, index=era5.index).dropna()
    if pair.empty:
        return None
    return float((pair["a"] - pair["b"]).mean())


def _retry_pause(exc: Exception, attempt: int) -> float:
    """Pause before the next attempt: 60 s on 429, 30 s on any 5xx.

    Open-Meteo answers heavy archive queries with transient 503s under
    load; a tight exponential backoff burns every retry in seconds.
    """
    code = getattr(getattr(exc, "response", None), "status_code", None)
    if code == 429:
        return 60.0
    if code is not None and 500 <= code < 600:
        return 30.0
    return float(2**attempt)


def fetch_grid_elevation(lat: float, lon: float, *, timezone: str) -> float | None:
    """Average ERA5 grid-cell orography (m) with downscaling disabled.

    Open-Meteo's default ``elevation`` field is the 90 m DEM at the requested
    point (used for statistical downscaling), not the model orography. Passing
    ``elevation=nan`` disables downscaling and the response ``elevation`` then
    reports the average grid-cell height.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2026-01-01",
        "end_date": "2026-01-01",
        "daily": "temperature_2m_max",
        "timezone": timezone,
        "models": "era5",
        "elevation": "nan",
    }
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            elevation = response.json().get("elevation")
            return float(elevation) if elevation is not None else None
        except (requests.RequestException, ValueError, TypeError) as exc:
            last_error = exc
            time.sleep(_retry_pause(exc, attempt))
    raise RuntimeError(f"grid elevation fetch failed for ({lat}, {lon}): {last_error}")


def fetch_dem_elevation(lat: float, lon: float, *, timezone: str) -> float | None:
    """90 m DEM elevation Open-Meteo downscales to (default request)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": "2026-01-01",
        "end_date": "2026-01-01",
        "daily": "temperature_2m_max",
        "timezone": timezone,
        "models": "era5",
    }
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            elevation = response.json().get("elevation")
            return float(elevation) if elevation is not None else None
        except (requests.RequestException, ValueError, TypeError) as exc:
            last_error = exc
            time.sleep(_retry_pause(exc, attempt))
    raise RuntimeError(f"DEM elevation fetch failed for ({lat}, {lon}): {last_error}")


def fetch_raw_grid_t2m_max(
    lat: float,
    lon: float,
    start: str,
    end: str,
    *,
    timezone: str,
    pause_seconds: float = HOURLY_PAUSE_SECONDS,
) -> tuple[pd.Series, float | None]:
    """Daily t2m_max with Open-Meteo statistical downscaling disabled.

    Returns (series indexed by local dates, average grid-cell elevation m).
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": "temperature_2m_max",
        "timezone": timezone,
        "models": "era5",
        "elevation": "nan",
    }
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            payload = response.json()
            daily = payload.get("daily") or {}
            if "time" not in daily:
                return pd.Series(dtype=float), None
            series = pd.Series(
                pd.to_numeric(pd.Series(daily["temperature_2m_max"]), errors="coerce").to_numpy(),
                index=pd.to_datetime(daily["time"]),
            )
            series = series[~series.index.duplicated(keep="last")].sort_index()
            elevation = payload.get("elevation")
            grid_el = float(elevation) if elevation is not None else None
            time.sleep(pause_seconds)
            return series, grid_el
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(_retry_pause(exc, attempt))
    raise RuntimeError(f"raw-grid daily fetch failed for ({lat}, {lon}): {last_error}")


def missing_ranges(
    cached_times: pd.DatetimeIndex | pd.Series,
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> list[tuple[str, str]]:
    """Contiguous daily gaps inside [start, end] not present in ``cached_times``."""
    full = pd.date_range(pd.Timestamp(start), pd.Timestamp(end), freq="D")
    if len(cached_times) == 0:
        missing = full
    else:
        present = pd.DatetimeIndex(pd.to_datetime(cached_times)).normalize().unique()
        missing = full.difference(present)
    if len(missing) == 0:
        return []
    gaps: list[tuple[str, str]] = []
    run_start = previous = missing[0]
    for day in missing[1:]:
        if day == previous + pd.Timedelta(days=1):
            previous = day
            continue
        gaps.append((run_start.strftime("%Y-%m-%d"), previous.strftime("%Y-%m-%d")))
        run_start = previous = day
    gaps.append((run_start.strftime("%Y-%m-%d"), previous.strftime("%Y-%m-%d")))
    return gaps


def _load_raw_grid_cache(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=RAW_GRID_CACHE_COLUMNS)
    frame = pd.read_parquet(path)
    for column in RAW_GRID_CACHE_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[RAW_GRID_CACHE_COLUMNS]


def _save_raw_grid_cache(frame: pd.DataFrame, path: Path) -> None:
    """Atomic write (temp file + rename) so an interrupted run keeps a valid cache."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    frame.to_parquet(tmp, index=False)
    tmp.replace(path)


def fetch_raw_grid_cached(
    fetch: Callable[..., tuple[pd.Series, float | None]],
    *,
    cache_path: Path,
    location: str,
    lat: float,
    lon: float,
    start: str,
    end: str,
    timezone: str,
    pause_seconds: float = HOURLY_PAUSE_SECONDS,
) -> tuple[pd.Series, float | None]:
    """Raw-grid daily series served from a persistent cache (resumable).

    Only date ranges missing from ``cache_path`` are fetched, and the cache is
    rewritten after every successful fetch, so a 429 mid-run loses at most the
    request in flight — the next run resumes at the remaining gaps.
    """
    cache = _load_raw_grid_cache(cache_path)
    local = cache.loc[cache["location"].eq(location)].copy() if not cache.empty else cache
    if local.empty:
        cached = pd.Series(dtype=float)
        grid_el: float | None = None
    else:
        local["time"] = pd.to_datetime(local["time"])
        cached = pd.Series(
            pd.to_numeric(local["value"], errors="coerce").to_numpy(),
            index=local["time"],
        )
        cached = cached[~cached.index.duplicated(keep="last")].sort_index()
        elevs = pd.to_numeric(local["grid_elevation_m"], errors="coerce").dropna()
        grid_el = float(elevs.iloc[-1]) if not elevs.empty else None

    fetched_frames: list[pd.DataFrame] = []
    working = local
    for gap_start, gap_end in missing_ranges(cached.index, start, end):
        series, fetched_el = fetch(
            lat, lon, gap_start, gap_end, timezone=timezone, pause_seconds=pause_seconds
        )
        if fetched_el is not None:
            grid_el = fetched_el
        if series.empty:
            continue
        rows = pd.DataFrame(
            {
                "location": location,
                "time": pd.to_datetime(series.index),
                "value": series.to_numpy(dtype=float),
                "grid_elevation_m": grid_el,
                "retrieved_at": utc_now(),
            }
        )
        fetched_frames.append(rows)
        working = pd.concat([working, rows], ignore_index=True)
        working = working.drop_duplicates(subset=["location", "time"], keep="last")
        _save_raw_grid_cache(working[RAW_GRID_CACHE_COLUMNS], cache_path)

    if fetched_frames:
        added = pd.concat(fetched_frames, ignore_index=True)
        combined = pd.concat([local, added], ignore_index=True) if not local.empty else added
        combined = combined.drop_duplicates(subset=["location", "time"], keep="last")
        combined["time"] = pd.to_datetime(combined["time"])
        window = combined.loc[
            combined["time"].between(pd.Timestamp(start), pd.Timestamp(end))
        ].sort_values("time")
        out = pd.Series(
            pd.to_numeric(window["value"], errors="coerce").to_numpy(),
            index=window["time"],
        )
        out = out[~out.index.duplicated(keep="last")]
        return out, grid_el

    start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
    window = cached.loc[(cached.index >= start_ts) & (cached.index <= end_ts)]
    return window.copy(), grid_el


def fetch_hourly_t2m(
    lat: float,
    lon: float,
    start: str,
    end: str,
    *,
    timezone: str,
    pause_seconds: float = HOURLY_PAUSE_SECONDS,
) -> pd.DataFrame:
    """Hourly ERA5 t2m for one point (long frame: time, value)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": "temperature_2m",
        "timezone": timezone,
        "models": "era5",
    }
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            response = requests.get(ARCHIVE_URL, params=params, timeout=TIMEOUT)
            response.raise_for_status()
            hourly = response.json().get("hourly") or {}
            if "time" not in hourly:
                return pd.DataFrame(columns=["time", "value"])
            value = pd.to_numeric(pd.Series(hourly.get("temperature_2m")), errors="coerce")
            frame = pd.DataFrame({"time": pd.to_datetime(hourly["time"]), "value": value})
            time.sleep(pause_seconds)
            return frame
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            time.sleep(_retry_pause(exc, attempt))
    raise RuntimeError(f"hourly fetch failed for ({lat}, {lon}): {last_error}")


def decompose_location(
    era5_values: pd.Series,
    station_values: pd.Series,
    *,
    grid_elevation_m: float | None,
    station_elevation_m: float | None,
    sampling_correction_c: float | None,
) -> dict[str, Any]:
    """Run the four-stage bias decomposition for one location/variable pair.

    All series are indexed by naive local dates and aligned on their index.
    """
    aligned = pd.DataFrame({"era5": era5_values, "station": station_values}).dropna()
    if aligned.empty:
        raise ValueError("no overlapping era5/station rows after dropna")

    record: dict[str, Any] = {
        "n_days": len(aligned),
        "bias_raw": float((aligned["era5"] - aligned["station"]).mean()),
        "grid_elevation_m": grid_elevation_m,
        "station_elevation_m": station_elevation_m,
        "elevation_diff_m": (
            float(grid_elevation_m - station_elevation_m)
            if grid_elevation_m is not None and station_elevation_m is not None
            else None
        ),
        "sampling_correction_c": sampling_correction_c,
    }

    # (a) elevation
    if grid_elevation_m is not None and station_elevation_m is not None:
        era5_elev = adjust_elevation(aligned["era5"], grid_elevation_m, station_elevation_m)
    else:
        era5_elev = aligned["era5"]
    record["bias_after_elevation"] = float((era5_elev - aligned["station"]).mean())

    # (b) hourly sampling (constant mean correction over the estimate window)
    if sampling_correction_c is not None:
        era5_samp = era5_elev + sampling_correction_c
    else:
        era5_samp = era5_elev
    record["bias_after_sampling"] = float((era5_samp - aligned["station"]).mean())

    # (c) day convention: best lag in {-1, 0, 1}
    lag, lag_mae = best_day_lag(era5_samp, aligned["station"])
    record["best_day_lag"] = lag
    record["lag_mae"] = lag_mae
    residual = bias_after_shift(era5_samp, aligned["station"], lag)
    record["bias_after_day_convention"] = residual
    return record


def precip_orography_record(
    ratio: float | None,
    grid_elevation_m: float | None,
    station_elevation_m: float | None,
) -> dict[str, Any]:
    """Orography context for a precipitation total ratio (ERA5 / station)."""
    elev_diff = (
        float(grid_elevation_m - station_elevation_m)
        if grid_elevation_m is not None and station_elevation_m is not None
        else None
    )
    note = ""
    if elev_diff is not None and ratio is not None:
        if elev_diff > 200 and ratio > 1.2:
            note = "grid higher and wetter — orographic enhancement plausible"
        elif elev_diff < -200 and ratio < 0.8:
            note = "grid lower and drier — orographic enhancement plausible"
        else:
            note = "elevation gap alone does not explain the ratio"
    return {
        "precip_ratio_era5_over_station": ratio,
        "grid_elevation_m": grid_elevation_m,
        "station_elevation_m": station_elevation_m,
        "elevation_diff_m": elev_diff,
        "note": note,
    }
