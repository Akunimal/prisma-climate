"""GEFS hindcast fetch: S3 keys, .idx Range slices, station-point t2m fields.

Implements docs/design/HINDCAST.md. Pure helpers are unit-testable without
network; network paths take injectable callables for tests.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import numpy as np

HINDCAST_LABEL = "hindcast"
PROVIDER = "NOAA GEFS (noaa-gefs-pds)"
DEFAULT_BUCKET = "https://noaa-gefs-pds.s3.amazonaws.com"
MEMBERS = tuple(["gec00", *[f"gep{i:02d}" for i in range(1, 31)]])  # 31
N_MEMBERS = len(MEMBERS)
MEMBER_FRACTION_NUM, MEMBER_FRACTION_DEN = 4, 5  # ≥ 80 % (2026-11-14 rule 1)
LEAD_DAYS_DEFAULT = (1, 3, 7, 10, 15)
CYCLE = "00"
TIMEOUT = 120

# eccodes MEMFS definition load races across threads → decode must be serial.
_DECODE_LOCK = threading.Lock()

# Nearest-neighbour station sampling on the 1° GEFS grid.
# Stations come from configs/regions/argentina.yaml at runtime; these are
# only used in unit tests.


@dataclass(frozen=True)
class StationPoint:
    station_id: str
    lat: float
    lon: float  # degrees east, may be negative (Argentina)


@dataclass(frozen=True)
class GefsKey:
    """One GRIB member forecast file key relative to the bucket root."""

    issue_date: date
    member: str  # gec00 / gep01 …
    forecast_hour: int
    key: str
    layout: str  # "flat" | "modern"


def _pad_hour(h: int) -> str:
    return f"{h:03d}"


def flat_key(issue: date, member: str, hour: int) -> str:
    return f"gefs.{issue:%Y%m%d}/{CYCLE}/{member}.t{CYCLE}z.pgrb2af{_pad_hour(hour)}"


def modern_key(issue: date, member: str, hour: int) -> str:
    """Product A 0.50° — ships TMAX/TMIN at 2 m (product B does not)."""
    return (
        f"gefs.{issue:%Y%m%d}/{CYCLE}/atmos/pgrb2ap5/"
        f"{member}.t{CYCLE}z.pgrb2a.0p50.f{_pad_hour(hour)}"
    )


def modern_sp25_key(issue: date, member: str, hour: int) -> str:
    """0.25° product S fallback — also has TMAX/TMIN at 2 m."""
    return (
        f"gefs.{issue:%Y%m%d}/{CYCLE}/atmos/pgrb2sp25/"
        f"{member}.t{CYCLE}z.pgrb2s.0p25.f{_pad_hour(hour)}"
    )


def candidate_keys(issue: date, member: str, hour: int) -> list[GefsKey]:
    """Layouts to try in order (flat first when present, then ap5, then sp25)."""
    return [
        GefsKey(issue, member, hour, flat_key(issue, member, hour), "flat"),
        GefsKey(issue, member, hour, modern_key(issue, member, hour), "modern_ap5"),
        GefsKey(issue, member, hour, modern_sp25_key(issue, member, hour), "modern_sp25"),
    ]


def parse_idx(text: str) -> list[tuple[int, int, str]]:
    """Parse GEFS .idx lines → (msg_no, byte_offset, rest).

    Format observed: ``63:3228934:d=2017010100:TMAX:2 m above ground:…``
    """
    out: list[tuple[int, int, str]] = []
    for line in text.splitlines():
        parts = line.split(":")
        if len(parts) < 4:
            continue
        try:
            msg_no = int(parts[0])
            offset = int(parts[1])
        except ValueError:
            continue
        out.append((msg_no, offset, ":".join(parts[2:])))
    return out


def find_field_range(
    records: Sequence[tuple[int, int, str]],
    var_name: str,
    file_size: int,
    cap_bytes: int = 2_000_000,
) -> tuple[int, int] | None:
    """Byte range [start, end_inclusive] for ``var_name`` (TMAX/TMIN/2T)."""
    target = var_name.upper()
    offsets = sorted({off for _, off, _ in records})
    for _, offset, rest in records:
        up = rest.upper()
        if target == "2T":
            hit = ":2T:" in up or "2 METRE TEMPERATURE" in up or "2M TEMPERATURE" in up
        else:
            hit = target in up
        if not hit:
            continue
        nxt = next((o for o in offsets if o > offset), file_size)
        end = min(nxt, offset + cap_bytes) - 1
        if end < offset:
            return None
        return offset, end
    return None


# --- local-day (UTC-3) period plan --------------------------------------------
# America/Argentina/Buenos_Aires = UTC−3, no DST: local day V runs
# [03Z V, 03Z V+1). GEFS TMAX/TMIN messages are period maxima/minima whose
# idx label states the exact period, e.g. ``30-36 hour max fcst`` (the
# 6-hour series at f006/f012/… tiles the whole timeline; a 3-hour series
# coexists at f003/f009/… but never tiles alone). The day value uses only
# periods fully inside the local day:
#
#   TMAX: 06-12, 12-18, 18-24 UTC of V → local 03-09, 09-15, 15-21
#   TMIN: 06-12, 12-18 UTC of V        → local 03-09, 09-15 (night/morning)
#
# The [00-06] UTC straddlers are excluded: they start before 03Z V, so they
# are not fully inside the local day. See docs/EVALUATION_PROTOCOL.md
# amendment §2b (2026-11-15).
LOCAL_DAY_TMAX_PERIODS = ((6, 12), (12, 18), (18, 24))  # UTC hours of day V
LOCAL_DAY_TMIN_PERIODS = ((6, 12), (12, 18))

_PERIOD_RE = re.compile(r"(\d+)-(\d+) hour (max|min) fcst")


def local_day_periods(
    lead_day: int,
    periods: Sequence[tuple[int, int]] = LOCAL_DAY_TMAX_PERIODS,
) -> tuple[tuple[int, int], ...]:
    """idx-label periods (forecast hours after the 00Z cycle) for local day t+lead.

    The local day V = t + lead starts at forecast hour 24·lead (00Z of V);
    a period (s, e) of V therefore has label hours (24·lead+s, 24·lead+e),
    and the message lives in file ``f{24·lead+e}`` (label end = file hour).
    """
    base = 24 * int(lead_day)
    return tuple((base + s, base + e) for s, e in periods)


def find_field_range_for_period(
    records: Sequence[tuple[int, int, str]],
    var_name: str,
    start_hour: int,
    end_hour: int,
    file_size: int,
    cap_bytes: int = 2_000_000,
) -> tuple[int, int] | None:
    """Byte range of the message whose idx label states exactly this period.

    The period is read from the label (``30-36 hour max fcst``), never
    inferred from the file's forecast hour: a 3-hour neighbour label, a
    different window or the wrong max/min kind returns None.
    """
    target = var_name.upper()
    kind = {"TMAX": "max", "TMIN": "min"}.get(target)
    if kind is None:
        return None
    offsets = sorted({off for _, off, _ in records})
    for _, offset, rest in records:
        # idx rest = "d=YYYYMMDDHH:VAR:level:period:…" — match VAR as a token
        if target not in rest.split(":"):
            continue
        m = _PERIOD_RE.search(rest)
        if m is None:
            continue
        if (int(m.group(1)), int(m.group(2))) != (start_hour, end_hour):
            continue
        if m.group(3) != kind:
            continue
        nxt = next((o for o in offsets if o > offset), file_size)
        end = min(nxt, offset + cap_bytes) - 1
        if end < offset:
            return None
        return offset, end
    return None


def lead_forecast_hour(lead_day: int) -> int:
    return 24 * int(lead_day)


def required_members(n_members: int = N_MEMBERS) -> int:
    """Minimum members present under the 80 % rule (rounds up)."""
    import math

    return math.ceil(n_members * MEMBER_FRACTION_NUM / MEMBER_FRACTION_DEN)


def sample_nearest(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
    lat: float,
    lon: float,
) -> float:
    """Nearest-grid-point sample; lon normalized to the grid's 0–360 convention."""
    if field.ndim != 2:
        raise ValueError("field must be 2-D")
    la = np.asarray(lats, dtype=float)
    lo = np.asarray(lons, dtype=float)
    if la.shape[0] != field.shape[0] or lo.shape[0] != field.shape[1]:
        raise ValueError("field shape must match lats × lons")
    lon360 = float(lon) % 360.0
    # grid lon may be 0..359 or -180..180
    if lo.min() < 0:
        lon_grid = ((lon360 + 180.0) % 360.0) - 180.0
    else:
        lon_grid = lon360
    iy = int(np.argmin(np.abs(la - float(lat))))
    ix = int(np.argmin(np.abs(lo - lon_grid)))
    value = float(field[iy, ix])
    if not np.isfinite(value):
        raise ValueError("sampled value is not finite")
    return value


def kelvin_to_celsius(value: float) -> float:
    return value - 273.15


def decode_tmax_from_grib_bytes(blob: bytes) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Decode a GRIB byte slice that contains TMAX/TMIN/2t → (field, lats, lons).

    Uses cfgrib + OnDiskArray.build_array (cfgrib 0.9.15, no xarray).
    eccodes MEMFS definition loading is not thread-safe; a module lock
    serializes decode while HTTP fetches stay parallel.
    """
    import tempfile
    from pathlib import Path

    import cfgrib

    with _DECODE_LOCK:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "slice.grib"
            path.write_bytes(blob)
            ds = cfgrib.open_file(
                str(path),
                filter_by_keys={"typeOfLevel": "heightAboveGround", "level": 2},
            )
            variables = ds.variables
            name = None
            for candidate in ("tmax", "tmin", "t2m"):
                if candidate in variables:
                    name = candidate
                    break
            if name is None:
                raise ValueError(f"no tmax/tmin/t2m in decoded variables: {list(variables)}")
            var = variables[name]
            field = np.asarray(var.data.build_array(), dtype=float)
            lats = np.asarray(variables["latitude"].data, dtype=float)
            lons = np.asarray(variables["longitude"].data, dtype=float)
            return field, lats, lons


# --- injectable HTTP surface -------------------------------------------------

HttpGet = Callable[[str, Mapping[str, str] | None], tuple[int, bytes, Mapping[str, str]]]
"""Return (status, body, headers)."""


def default_http_get(
    url: str, headers: Mapping[str, str] | None = None
) -> tuple[int, bytes, Mapping[str, str]]:
    import requests

    r = requests.get(url, headers=dict(headers or {}), timeout=TIMEOUT)
    return r.status_code, r.content, dict(r.headers)


@dataclass(frozen=True)
class MemberForecast:
    issue_date: date
    lead_day: int
    member: str
    values_c: dict[str, float]  # station_id → degC (local-day t2m_max)
    layout: str
    key: str
    # station_id → degC (local-day t2m_min); None on the legacy single-message path
    values_min_c: dict[str, float] | None = None


# Last layout that answered (modern_ap5 after the flat era) — tried first.
_PREFERRED_LAYOUT: str | None = None


def resolve_key(
    issue: date,
    member: str,
    hour: int,
    http_get: HttpGet,
    bucket: str = DEFAULT_BUCKET,
) -> tuple[GefsKey, int] | None:
    """(key, file_size) — size from the successful Range probe, 0 if unknown."""
    global _PREFERRED_LAYOUT
    cands = candidate_keys(issue, member, hour)
    if _PREFERRED_LAYOUT:
        cands = sorted(cands, key=lambda c: c.layout != _PREFERRED_LAYOUT)
    for cand in cands:
        status, _, headers = http_get(f"{bucket}/{cand.key}", {"Range": "bytes=0-0"})
        if status in (200, 206):
            _PREFERRED_LAYOUT = cand.layout
            size = 0
            content_range = headers.get("Content-Range") or headers.get("content-range") or ""
            if "/" in content_range:
                try:
                    size = int(content_range.rsplit("/", 1)[-1])
                except ValueError:
                    size = 0
            return cand, size
        if status == 404:
            continue
    return None


def fetch_member_tmax(
    issue: date,
    member: str,
    lead_day: int,
    stations: Sequence[StationPoint],
    http_get: HttpGet = default_http_get,
    bucket: str = DEFAULT_BUCKET,
) -> MemberForecast | None:
    """Download TMAX for one member/lead and sample stations. None if missing.

    Legacy single-message path (Run A): one period, joined to local day
    ``issue + lead_day`` even when the period lies on the previous local day
    (defect (iii) of the 2026-11-15 amendment). Kept for provenance only —
    Run B scores use :func:`fetch_member_local_day`.
    """
    hour = lead_forecast_hour(lead_day)
    resolved = resolve_key(issue, member, hour, http_get, bucket)
    if resolved is None:
        return None
    key, probed_size = resolved
    base = f"{bucket}/{key.key}"
    status, idx_body, _ = http_get(f"{base}.idx")
    if status != 200 or not idx_body:
        return None
    records = parse_idx(idx_body.decode("utf-8", errors="replace"))
    file_size = probed_size if probed_size > 0 else 5_000_000
    rng = find_field_range(records, "TMAX", file_size)
    if rng is None:
        rng = find_field_range(records, "2T", file_size)
    if rng is None:
        return None
    start, end = rng
    status3, blob, _ = http_get(base, {"Range": f"bytes={start}-{end}"})
    if status3 not in (200, 206) or not blob:
        return None
    try:
        field, lats, lons = decode_tmax_from_grib_bytes(blob)
    except Exception:
        return None
    values: dict[str, float] = {}
    for st in stations:
        try:
            k = sample_nearest(field, lats, lons, st.lat, st.lon)
            values[st.station_id] = kelvin_to_celsius(k)
        except ValueError:
            continue
    if not values:
        return None
    return MemberForecast(
        issue_date=issue,
        lead_day=lead_day,
        member=member,
        values_c=values,
        layout=key.layout,
        key=key.key,
    )


def fetch_member_local_day(
    issue: date,
    member: str,
    lead_day: int,
    stations: Sequence[StationPoint],
    http_get: HttpGet = default_http_get,
    bucket: str = DEFAULT_BUCKET,
) -> MemberForecast | None:
    """Local-day t2m_max + t2m_min for V = issue + lead (UTC-3, label-verified).

    t2m_max = max of the TMAX periods fully inside [03Z V, 03Z V+1)
    (06-12, 12-18, 18-24 UTC of V); t2m_min = min of the TMIN periods
    covering local night/morning (06-12, 12-18 UTC of V). Every message is
    selected by its exact idx label — a missing or mismatched label fails
    the whole slot (None) rather than substituting another forecast hour.
    """
    tmax_plan = local_day_periods(lead_day, LOCAL_DAY_TMAX_PERIODS)
    tmin_plan = local_day_periods(lead_day, LOCAL_DAY_TMIN_PERIODS)
    tmax_by_end = {e: (s, e) for s, e in tmax_plan}
    tmin_by_end = {e: (s, e) for s, e in tmin_plan}
    file_hours = sorted(set(tmax_by_end) | set(tmin_by_end))

    period_values: dict[str, dict[tuple[int, int], dict[str, float]]] = {
        "TMAX": {},
        "TMIN": {},
    }
    keys: list[str] = []
    layout = ""
    for hour in file_hours:
        resolved = resolve_key(issue, member, hour, http_get, bucket)
        if resolved is None:
            return None
        key, probed_size = resolved
        base = f"{bucket}/{key.key}"
        status, idx_body, _ = http_get(f"{base}.idx")
        if status != 200 or not idx_body:
            return None
        records = parse_idx(idx_body.decode("utf-8", errors="replace"))
        file_size = probed_size if probed_size > 0 else 5_000_000
        wanted: list[tuple[str, tuple[int, int]]] = []
        if hour in tmax_by_end:
            wanted.append(("TMAX", tmax_by_end[hour]))
        if hour in tmin_by_end:
            wanted.append(("TMIN", tmin_by_end[hour]))
        ranges: dict[str, tuple[int, int, tuple[int, int]]] = {}
        for var, period in wanted:
            rng = find_field_range_for_period(
                records, var, period[0], period[1], file_size
            )
            if rng is None:
                return None
            ranges[var] = (rng[0], rng[1], period)
        # one Range request covering every wanted message of this file
        start = min(r[0] for r in ranges.values())
        end = max(r[1] for r in ranges.values())
        status2, blob, _ = http_get(base, {"Range": f"bytes={start}-{end}"})
        if status2 not in (200, 206) or not blob:
            return None
        for var, (r0, r1, period) in ranges.items():
            sub = blob[r0 - start : r1 - start + 1]
            if not sub:
                return None
            try:
                field, lats, lons = decode_tmax_from_grib_bytes(sub)
            except Exception:
                return None
            vals: dict[str, float] = {}
            for st in stations:
                try:
                    k = sample_nearest(field, lats, lons, st.lat, st.lon)
                    vals[st.station_id] = kelvin_to_celsius(k)
                except ValueError:
                    continue
            if not vals:
                return None
            period_values[var][period] = vals
        keys.append(key.key)
        layout = key.layout

    if len(period_values["TMAX"]) != len(tmax_plan):
        return None
    if len(period_values["TMIN"]) != len(tmin_plan):
        return None
    values_c: dict[str, float] = {}
    values_min_c: dict[str, float] = {}
    for st in stations:
        sid = st.station_id
        try:
            values_c[sid] = max(period_values["TMAX"][p][sid] for p in tmax_plan)
            values_min_c[sid] = min(period_values["TMIN"][p][sid] for p in tmin_plan)
        except KeyError:
            continue  # station not sampled in some period → slot incomplete
    if not values_c:
        return None
    return MemberForecast(
        issue_date=issue,
        lead_day=lead_day,
        member=member,
        values_c=values_c,
        layout=layout,
        key=";".join(keys),
        values_min_c=values_min_c,
    )


def issue_dates_between(start: date, end: date) -> list[date]:
    """Inclusive date range."""
    if end < start:
        raise ValueError("end before start")
    out = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur = cur + timedelta(days=1)
    return out


def split_train_eval(
    all_dates: Sequence[date], n_train: int
) -> tuple[list[date], list[date]]:
    """First n_train dates → train; the rest (strictly after) → eval."""
    dates = list(all_dates)
    if n_train <= 0 or n_train >= len(dates):
        raise ValueError("n_train must leave a non-empty eval slice")
    train = dates[:n_train]
    eval_ = dates[n_train:]
    if not eval_ or eval_[0] <= train[-1]:
        raise ValueError("eval must be strictly after train")
    return train, eval_


def build_ensemble_matrix(
    members: Sequence[MemberForecast],
    stations: Sequence[StationPoint],
) -> tuple[np.ndarray, list[str]]:
    """Stack member values into (n_members, n_stations) in MEMBERS order.

    Returns matrix and the station ids used (all stations present in every member).
    """
    by_member = {m.member: m for m in members}
    present = [mid for mid in MEMBERS if mid in by_member]
    if len(present) < required_members(len(MEMBERS)):
        raise ValueError(
            f"need ≥ {required_members(len(MEMBERS))} members, got {len(present)}"
        )
    station_ids = [st.station_id for st in stations]
    rows = []
    for mid in present:
        fc = by_member[mid]
        row = []
        for sid in station_ids:
            if sid not in fc.values_c:
                raise ValueError(f"member {mid} missing station {sid}")
            row.append(fc.values_c[sid])
        rows.append(row)
    return np.asarray(rows, dtype=float), station_ids


def hindcast_metadata(retrieved_at: datetime | None = None) -> dict[str, Any]:
    ts = retrieved_at or datetime.now(UTC)
    return {
        "label": HINDCAST_LABEL,
        "provider": PROVIDER,
        "retrieved_at": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cycle": CYCLE,
        "n_members": N_MEMBERS,
        "members": list(MEMBERS),
    }


def parse_issue_date(key: str) -> date | None:
    m = re.match(r"gefs\.(\d{8})/", key)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d").date()


__all__ = [
    "CYCLE",
    "DEFAULT_BUCKET",
    "HINDCAST_LABEL",
    "LEAD_DAYS_DEFAULT",
    "LOCAL_DAY_TMAX_PERIODS",
    "LOCAL_DAY_TMIN_PERIODS",
    "MEMBERS",
    "N_MEMBERS",
    "PROVIDER",
    "GefsKey",
    "MemberForecast",
    "StationPoint",
    "HttpGet",
    "build_ensemble_matrix",
    "candidate_keys",
    "decode_tmax_from_grib_bytes",
    "fetch_member_local_day",
    "fetch_member_tmax",
    "find_field_range",
    "find_field_range_for_period",
    "flat_key",
    "hindcast_metadata",
    "kelvin_to_celsius",
    "lead_forecast_hour",
    "local_day_periods",
    "modern_key",
    "parse_idx",
    "required_members",
    "resolve_key",
    "sample_nearest",
    "split_train_eval",
]
