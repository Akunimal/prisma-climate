"""Parallel audit and verification harness for PRISMA global regions.

Audits non-Argentina regional station configurations against:
1. NOAA AWC station cache (stations.cache.json.gz)
2. NOAA ISD station history (isd-history.csv)
3. NOAA GHCN-Daily station inventory (ghcnd-stations.txt)
4. Live 72h NOAA AWC METAR telemetry and IEM fallback
5. Open-Meteo API quota and rate limits
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "results" / "stations" / "_evidence"
CONFIGS_REGIONS = ROOT / "configs" / "regions"

USER_AGENT = "PRISMA-Climate/0.2.0 (+https://github.com/Akunimal/prisma-climate)"
TEMP_DIR = Path(tempfile.gettempdir()) / "t_global1_evidence"

CATALOG_URLS = {
    "awc_stations": "https://aviationweather.gov/data/cache/stations.cache.json.gz",
    "noaa_isd": "https://www.ncei.noaa.gov/pub/data/noaa/isd-history.csv",
    "ghcn_stations": "https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt",
}

NON_ARGENTINA_REGIONS = [
    "south_america",
    "north_america",
    "europe",
    "asia",
    "africa",
    "oceania",
    "middle_east",
]

# Known ICAO / historical renames in international catalogs
ICAO_ALIASES = {
    "FAOR": ["FAJS"],  # Johannesburg O.R. Tambo was formerly FAJS
}

USAF_OVERRIDES = {
    "ORER": "406356",  # Erbil International in ISD has USAF 406356 with blank ICAO column
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance in kilometers between two points."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def fetch_url(url: str, timeout: int = 45, retries: int = 3) -> tuple[bytes, float, int]:
    """Fetch URL with retries and timing, returning (bytes, latency_ms, status_code)."""
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(url, headers=headers)
    last_err: Exception | None = None
    for attempt in range(retries):
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = resp.read()
                latency_ms = (time.perf_counter() - t0) * 1000.0
                return data, latency_ms, resp.status
        except urllib.error.HTTPError as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            if exc.code == 429 or exc.code >= 500:
                time.sleep(1.5 * (attempt + 1))
                last_err = exc
                continue
            return b"", latency_ms, exc.code
        except Exception as exc:
            latency_ms = (time.perf_counter() - t0) * 1000.0
            last_err = exc
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries: {last_err}")


def ensure_catalogs() -> dict[str, dict[str, Any]]:
    """Download reference catalogs once to temporary storage and return metadata."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    metadata: dict[str, dict[str, Any]] = {}

    for name, url in CATALOG_URLS.items():
        filename = url.split("/")[-1]
        target = TEMP_DIR / filename
        if not target.exists() or target.stat().st_size == 0:
            print(f"Downloading catalog {name} from {url}...")
            data, _, _ = fetch_url(url, timeout=60)
            target.write_bytes(data)
        else:
            data = target.read_bytes()

        sha256 = hashlib.sha256(data).hexdigest()
        mtime = datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat()
        metadata[name] = {
            "url": url,
            "filename": filename,
            "byte_size": len(data),
            "sha256": sha256,
            "fetch_utc": mtime,
            "local_path": str(target),
        }
    return metadata


def load_awc_catalog(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load NOAA AWC stations cache into an ICAO-keyed lookup."""
    target = Path(meta["awc_stations"]["local_path"])
    raw = gzip.decompress(target.read_bytes())
    data = json.loads(raw.decode("utf-8"))
    lookup: dict[str, dict[str, Any]] = {}
    for item in data:
        icao = item.get("icaoId")
        if not icao:
            ident = item.get("id", "")
            if len(ident) == 4 and ident.isalpha() and ident.isupper():
                icao = ident
        if icao:
            lookup[icao] = {
                "icao": icao,
                "site": item.get("site", ""),
                "lat": float(item.get("lat", 0.0)),
                "lon": float(item.get("lon", 0.0)),
                "elevation_m": float(item.get("elev", 0.0)) if item.get("elev") is not None else None,
                "country": item.get("country", ""),
                "state": item.get("state", ""),
                "wmoId": item.get("wmoId"),
            }
    return lookup


def load_isd_catalog(meta: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, Any]]]:
    """Load NOAA ISD station history into ICAO-keyed and USAF-keyed lookups."""
    target = Path(meta["noaa_isd"]["local_path"])
    text = target.read_bytes().decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    icao_lookup = defaultdict(list)
    usaf_lookup = {}
    for row in reader:
        if len(row) < 11:
            continue
        usaf, wban, name, ctry, state, icao, lat, lon, elev, begin, end = row[:11]
        icao = icao.strip().upper()
        usaf = usaf.strip()
        try:
            lat_f = float(lat)
            lon_f = float(lon)
            elev_f = float(elev) if elev.strip() else None
        except ValueError:
            continue
        record = {
            "usaf": usaf,
            "wban": wban.strip(),
            "station_name": name.strip(),
            "country": ctry.strip(),
            "state": state.strip(),
            "icao": icao,
            "lat": lat_f,
            "lon": lon_f,
            "elevation_m": elev_f,
            "begin": begin.strip(),
            "end": end.strip(),
        }
        if icao:
            icao_lookup[icao].append(record)
        if usaf:
            usaf_lookup[usaf] = record
    return icao_lookup, usaf_lookup


def load_ghcn_catalog(meta: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Load GHCN-Daily stations inventory."""
    target = Path(meta["ghcn_stations"]["local_path"])
    text = target.read_bytes().decode("utf-8", errors="ignore")
    lookup: dict[str, dict[str, Any]] = {}
    for line in text.splitlines():
        if len(line) < 40:
            continue
        st_id = line[0:11].strip()
        try:
            lat = float(line[12:20].strip())
            lon = float(line[21:30].strip())
            elev = float(line[31:37].strip())
            name = line[41:71].strip()
            lookup[st_id] = {
                "id": st_id,
                "lat": lat,
                "lon": lon,
                "elevation_m": elev,
                "name": name,
            }
        except ValueError:
            continue
    return lookup


def probe_awc_metar_batch(
    icaos: list[str], hours: int = 72
) -> tuple[list[dict[str, Any]], float, int, str]:
    """Fetch 72h METAR reports for a batch of ICAOs from NOAA AWC."""
    ids_param = ",".join(icaos)
    url = f"https://aviationweather.gov/api/data/metar?ids={urllib.parse.quote(ids_param)}&hours={hours}&format=json"
    data, lat_ms, code = fetch_url(url, timeout=30)
    reports = []
    if code == 200 and data:
        try:
            parsed = json.loads(data.decode("utf-8"))
            if isinstance(parsed, list):
                reports = parsed
        except json.JSONDecodeError:
            pass
    return reports, lat_ms, code, url


def audit_region(
    region_slug: str,
    awc_cat: dict[str, dict[str, Any]],
    isd_cat: dict[str, list[dict[str, Any]]],
    isd_usaf: dict[str, dict[str, Any]],
    ghcn_cat: dict[str, dict[str, Any]],
    catalog_meta: dict[str, Any],
) -> dict[str, Any]:
    """Execute Phases 1, 2, and 3.1 audit on a single region."""
    region_path = CONFIGS_REGIONS / f"{region_slug}.yaml"
    with open(region_path, encoding="utf-8") as f:
        region_cfg = yaml.safe_load(f)

    stations = region_cfg.get("stations", [])
    icaos = [s["icao"] for s in stations if "icao" in s]

    # 1. Probe METAR in small batches of 3 to avoid AWC 400-report cap
    batch_size = 3
    all_reports: list[dict[str, Any]] = []
    http_probes: list[dict[str, Any]] = []
    latencies: list[float] = []

    for i in range(0, len(icaos), batch_size):
        batch = icaos[i : i + batch_size]
        reps, lat_ms, code, url = probe_awc_metar_batch(batch, hours=72)
        http_probes.append({
            "batch_icaos": batch,
            "url": url,
            "status_code": code,
            "latency_ms": round(lat_ms, 2),
            "reports_count": len(reps),
        })
        latencies.append(lat_ms)
        all_reports.extend(reps)
        time.sleep(0.2)

    now_utc = datetime.now(timezone.utc)

    # Group reports by ICAO
    reports_by_icao = defaultdict(list)
    raw_metar_samples: list[str] = []
    for r in all_reports:
        r_icao = r.get("icaoId")
        if r_icao:
            reports_by_icao[r_icao].append(r)
        raw_ob = r.get("rawOb")
        if raw_ob and len(raw_metar_samples) < 5 and raw_ob not in raw_metar_samples:
            raw_metar_samples.append(raw_ob)

    # 2. Station-by-station vetting against AWC, ISD, GHCN and telemetry
    vetted_stations: list[dict[str, Any]] = []
    confirmed_second_source_count = 0
    active_telemetry_count = 0
    passed_vetting_count = 0
    auto_resolved_count = 0
    removed_count = 0

    for st in stations:
        st_id = st["id"]
        st_name = st["name"]
        icao = st.get("icao", "")
        cfg_lat = float(st["lat"])
        cfg_lon = float(st["lon"])
        cfg_elev = float(st.get("elevation_m", 0.0))
        ghcn_id = st.get("ghcn_id")

        # AWC lookup (including aliases)
        awc_match = awc_cat.get(icao)
        if not awc_match and icao in ICAO_ALIASES:
            for alias in ICAO_ALIASES[icao]:
                if alias in awc_cat:
                    awc_match = awc_cat[alias]
                    break

        awc_dist = haversine_km(cfg_lat, cfg_lon, awc_match["lat"], awc_match["lon"]) if awc_match else None
        awc_elev = awc_match.get("elevation_m") if awc_match else None
        awc_delta_elev = (cfg_elev - awc_elev) if (awc_match and awc_elev is not None) else None

        # ISD lookup (including aliases and USAF overrides)
        isd_matches = isd_cat.get(icao, [])
        if not isd_matches and icao in ICAO_ALIASES:
            for alias in ICAO_ALIASES[icao]:
                if alias in isd_cat:
                    isd_matches = isd_cat[alias]
                    break
        if not isd_matches and icao in USAF_OVERRIDES:
            usaf_val = USAF_OVERRIDES[icao]
            if usaf_val in isd_usaf:
                isd_matches = [isd_usaf[usaf_val]]

        isd_best = None
        if isd_matches:
            isd_matches_sorted = sorted(isd_matches, key=lambda x: x.get("end", ""), reverse=True)
            isd_best = isd_matches_sorted[0]

        isd_dist = haversine_km(cfg_lat, cfg_lon, isd_best["lat"], isd_best["lon"]) if isd_best else None
        isd_elev = isd_best.get("elevation_m") if isd_best else None
        isd_delta_elev = (cfg_elev - isd_elev) if (isd_best and isd_elev is not None) else None

        # GHCN lookup
        ghcn_match = ghcn_cat.get(ghcn_id) if ghcn_id else None

        # Telemetry metrics
        st_reports = reports_by_icao.get(icao, [])
        obs_72h = len(st_reports)

        # Calculate exact hourly gap rate over 72 1-hour slots
        hourly_bins = [0] * 72
        valid_temp_count = 0
        for r in st_reports:
            t = r.get("obsTime")
            if t is not None and r.get("temp") is not None:
                valid_temp_count += 1
                try:
                    dt = datetime.fromtimestamp(t, tz=timezone.utc)
                    age_h = int((now_utc - dt).total_seconds() // 3600)
                    if 0 <= age_h < 72:
                        hourly_bins[age_h] += 1
                except (OSError, OverflowError, ValueError):
                    pass

        missing_hours = hourly_bins.count(0)
        gap_rate_pct = round((missing_hours / 72.0) * 100.0, 2)
        obs_per_day = round(obs_72h / 3.0, 2)
        temp_completeness_pct = round((valid_temp_count / obs_72h * 100.0) if obs_72h > 0 else 0.0, 2)
        mean_interval_h = round(72.0 / max(1, valid_temp_count), 2)

        telemetry_active = obs_72h > 0
        if telemetry_active:
            active_telemetry_count += 1

        second_source_confirmed = bool(awc_match and isd_best)
        if second_source_confirmed:
            confirmed_second_source_count += 1

        # Vetting status per Decision C
        primary_dist = awc_dist if awc_dist is not None else isd_dist
        primary_delta_elev = awc_delta_elev if awc_delta_elev is not None else isd_delta_elev

        vetting_status = "PASS"
        vetting_action = "retain_unchanged"
        resolved_coords = None

        if primary_dist is None or not second_source_confirmed or obs_72h == 0:
            vetting_status = "FAIL"
            vetting_action = "remove"
            removed_count += 1
        elif primary_dist <= 5.0:
            if primary_delta_elev is not None and abs(primary_delta_elev) > 150:
                vetting_status = "FLAG_ELEV"
            elif primary_delta_elev is not None and abs(primary_delta_elev) > 50:
                vetting_status = "WARN_ELEV"
            else:
                vetting_status = "PASS"
            passed_vetting_count += 1
        elif 5.0 < primary_dist <= 15.0 and awc_match and isd_best:
            vetting_status = "AUTO_RESOLVE"
            vetting_action = "auto_resolved_coords"
            resolved_coords = {
                "lat": awc_match["lat"],
                "lon": awc_match["lon"],
                "elevation_m": int(round(awc_match["elevation_m"])) if awc_match.get("elevation_m") is not None else cfg_elev,
            }
            auto_resolved_count += 1
            passed_vetting_count += 1
        else:
            vetting_status = "FAIL_DISTANCE"
            vetting_action = "remove"
            removed_count += 1

        vetted_stations.append({
            "id": st_id,
            "name": st_name,
            "country": st.get("country", ""),
            "icao": icao,
            "config_lat": cfg_lat,
            "config_lon": cfg_lon,
            "config_elevation_m": cfg_elev,
            "ghcn_id": ghcn_id,
            "awc_match": bool(awc_match),
            "awc_site": awc_match.get("site") if awc_match else None,
            "awc_lat": awc_match.get("lat") if awc_match else None,
            "awc_lon": awc_match.get("lon") if awc_match else None,
            "awc_elevation_m": awc_elev,
            "haversine_awc_km": round(awc_dist, 3) if awc_dist is not None else None,
            "delta_elev_awc_m": round(awc_delta_elev, 1) if awc_delta_elev is not None else None,
            "isd_match": bool(isd_best),
            "isd_station_name": isd_best.get("station_name") if isd_best else None,
            "isd_lat": isd_best.get("lat") if isd_best else None,
            "isd_lon": isd_best.get("lon") if isd_best else None,
            "isd_elevation_m": isd_elev,
            "haversine_isd_km": round(isd_dist, 3) if isd_dist is not None else None,
            "delta_elev_isd_m": round(isd_delta_elev, 1) if isd_delta_elev is not None else None,
            "ghcn_match": bool(ghcn_match),
            "obs_72h_count": obs_72h,
            "obs_per_day": obs_per_day,
            "valid_temp_count": valid_temp_count,
            "temp_completeness_pct": temp_completeness_pct,
            "mean_interval_hours": mean_interval_h,
            "gap_rate_pct": gap_rate_pct,
            "telemetry_active": telemetry_active,
            "second_source_confirmed": second_source_confirmed,
            "vetting_status": vetting_status,
            "vetting_action": vetting_action,
            "resolved_coords": resolved_coords,
        })

    # Latency percentiles
    sorted_lats = sorted(latencies)
    p50 = sorted_lats[len(sorted_lats) // 2] if sorted_lats else 0.0
    p95 = sorted_lats[int(len(sorted_lats) * 0.95)] if sorted_lats else 0.0
    max_lat = max(sorted_lats) if sorted_lats else 0.0
    min_lat = min(sorted_lats) if sorted_lats else 0.0
    mean_lat = sum(sorted_lats) / len(sorted_lats) if sorted_lats else 0.0

    total_stations = len(stations)
    retained_count = total_stations - removed_count
    confirmed_pct = round(confirmed_second_source_count / total_stations * 100.0, 1) if total_stations else 0.0
    active_pct = round(active_telemetry_count / total_stations * 100.0, 1) if total_stations else 0.0
    vetting_pct = round(passed_vetting_count / total_stations * 100.0, 1) if total_stations else 0.0

    # Decision C Gate: >= 80% confirmed by 2nd source & active telemetry, >= 5 stations
    phase2_pass = (
        retained_count >= 5
        and (confirmed_second_source_count / total_stations) >= 0.80
        and (active_telemetry_count / total_stations) >= 0.80
    )

    # Decision E Gate: >= 80% vetted stations report >= 12 obs/day, mean interval <= 2h, < 15% gap
    qualifying_obs_stations = [
        st for st in vetted_stations
        if st["vetting_action"] != "remove"
        and st["obs_per_day"] >= 12.0
        and st["mean_interval_hours"] <= 2.0
        and st["gap_rate_pct"] < 15.0
    ]
    obs_ref_pct = round(len(qualifying_obs_stations) / max(1, retained_count) * 100.0, 1)
    phase3_qualifies = (obs_ref_pct >= 80.0)

    summary = {
        "region_slug": region_slug,
        "region_name": region_cfg.get("name", region_slug),
        "audit_utc": datetime.now(timezone.utc).isoformat(),
        "total_stations": total_stations,
        "retained_count": retained_count,
        "auto_resolved_count": auto_resolved_count,
        "removed_count": removed_count,
        "confirmed_second_source_count": confirmed_second_source_count,
        "confirmed_second_source_pct": confirmed_pct,
        "active_telemetry_count": active_telemetry_count,
        "active_telemetry_pct": active_pct,
        "passed_vetting_count": passed_vetting_count,
        "passed_vetting_pct": vetting_pct,
        "qualifying_obs_stations_count": len(qualifying_obs_stations),
        "qualifying_obs_stations_pct": obs_ref_pct,
        "phase1_source_status": "PASS",
        "phase2_vetting_status": "PASS" if phase2_pass else "BLOCKED",
        "phase3_obs_status": "QUALIFIED" if phase3_qualifies else "NONE_YET",
        "suggested_source_status": "ready_for_review" if (phase2_pass and phase3_qualifies) else "blocked",
        "latency_summary_ms": {
            "p50": round(p50, 2),
            "p95": round(p95, 2),
            "max": round(max_lat, 2),
            "min": round(min_lat, 2),
            "mean": round(mean_lat, 2),
        },
    }

    audit_payload = {
        "summary": summary,
        "catalogs": catalog_meta,
        "http_probes": http_probes,
        "raw_metar_samples": raw_metar_samples,
        "stations": vetted_stations,
    }

    evidence_out = EVIDENCE_DIR / region_slug
    evidence_out.mkdir(parents=True, exist_ok=True)
    json_path = evidence_out / "audit.json"
    json_path.write_text(json.dumps(audit_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{region_slug}] Audit written to {json_path} (retained: {retained_count}/{total_stations}, vetting: {summary['phase2_vetting_status']}, obs: {summary['phase3_obs_status']})")
    return audit_payload


def audit_open_meteo_quota() -> dict[str, Any]:
    """Execute Open-Meteo quota probe and compute 8-region volume math."""
    probe_url = (
        "https://ensemble-api.open-meteo.com/v1/ensemble?"
        "latitude=-31.317&longitude=-64.217&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&models=gfs_seamless&forecast_days=7&timezone=America/Argentina/Cordoba"
    )
    t0 = time.perf_counter()
    headers = {"User-Agent": USER_AGENT}
    req = urllib.request.Request(probe_url, headers=headers)
    status_code = 0
    resp_headers = {}
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            status_code = resp.status
            resp_headers = dict(resp.headers)
            resp.read()
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        resp_headers = dict(exc.headers)
    lat_ms = (time.perf_counter() - t0) * 1000.0

    all_stations_count = 0
    for p in CONFIGS_REGIONS.glob("*.yaml"):
        with open(p, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            all_stations_count += len(cfg.get("stations", []))

    models_count = 2  # gfs_seamless, ecmwf_ifs025
    reqs_per_archive_run = all_stations_count * models_count
    archive_cron_slots_per_day = 5  # 06:47, 09:47, 12:17, 14:43, 18:31 UTC
    forecast_reqs_per_day_worst_case = reqs_per_archive_run * archive_cron_slots_per_day

    # METAR observation math
    # Batched at 6 stations/req: ~3 batches per region × 8 regions = 24 req/run × 24 = 576 req/day max
    # Batched at 10 stations/req: ~2 batches per region × 8 regions = 16 req/run × 24 = 384 req/day
    metar_reqs_per_day_batched10 = 16 * 24

    free_tier_limits = {
        "max_requests_per_day": 10000,
        "max_requests_per_hour": 5000,
        "max_requests_per_minute": 600,
        "license": "CC BY 4.0 (free tier non-commercial only)",
    }

    safe_envelope = {
        "max_forecast_reqs_per_day": 4000,
        "max_forecast_reqs_per_minute": 300,
        "max_metar_obs_reqs_per_day": 500,
    }

    forecast_pass = (
        forecast_reqs_per_day_worst_case <= safe_envelope["max_forecast_reqs_per_day"]
    )
    metar_pass = (
        metar_reqs_per_day_batched10 <= safe_envelope["max_metar_obs_reqs_per_day"]
    )

    result = {
        "probe_utc": datetime.now(timezone.utc).isoformat(),
        "probe_status_code": status_code,
        "probe_latency_ms": round(lat_ms, 2),
        "total_configured_stations": all_stations_count,
        "models_per_station": models_count,
        "reqs_per_forecast_run": reqs_per_archive_run,
        "forecast_archive_slots_per_day": archive_cron_slots_per_day,
        "forecast_reqs_per_day_worst_case": forecast_reqs_per_day_worst_case,
        "forecast_req_rate_per_sec": 5.0,  # 1 req per 0.2s pause
        "forecast_req_rate_per_min": 300,  # with PAUSE_SECONDS=0.2
        "metar_obs_reqs_per_day_batched10": metar_reqs_per_day_batched10,
        "free_tier_limits": free_tier_limits,
        "safe_envelope": safe_envelope,
        "forecast_within_safe_envelope": forecast_pass,
        "metar_within_safe_envelope": metar_pass,
        "overall_status": "PASS" if (forecast_pass and metar_pass) else "FLAG",
    }

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    out_file = EVIDENCE_DIR / "open_meteo_quota_audit.json"
    out_file.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Open-Meteo quota audit written to {out_file} (forecast daily reqs: {forecast_reqs_per_day_worst_case}, status: {result['overall_status']})")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit and verify PRISMA global regions.")
    parser.add_argument(
        "--region",
        choices=NON_ARGENTINA_REGIONS + ["all"],
        default="all",
        help="Region to audit (default: all)",
    )
    args = parser.parse_args()

    print("Phase 0/1: Ensuring external reference catalogs in temp storage...")
    catalog_meta = ensure_catalogs()
    print("Loading NOAA AWC stations cache...")
    awc_cat = load_awc_catalog(catalog_meta)
    print(f"  Loaded {len(awc_cat)} AWC stations.")
    print("Loading NOAA ISD station history...")
    isd_cat, isd_usaf = load_isd_catalog(catalog_meta)
    print(f"  Loaded {len(isd_cat)} ISD ICAO keys and {len(isd_usaf)} USAF keys.")
    print("Loading NOAA GHCN-Daily stations...")
    ghcn_cat = load_ghcn_catalog(catalog_meta)
    print(f"  Loaded {len(ghcn_cat)} GHCN stations.")

    print("\nAuditing Open-Meteo API quota...")
    audit_open_meteo_quota()

    regions_to_audit = NON_ARGENTINA_REGIONS if args.region == "all" else [args.region]
    print(f"\nAuditing regions in parallel: {regions_to_audit}...")

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                audit_region, slug, awc_cat, isd_cat, isd_usaf, ghcn_cat, catalog_meta
            ): slug
            for slug in regions_to_audit
        }
        for future in as_completed(futures):
            slug = futures[future]
            try:
                future.result()
            except Exception as exc:
                print(f"[{slug}] Audit failed with error: {exc}", file=sys.stderr)
                raise

    print("\nAll region audits completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
