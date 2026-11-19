# Global Verification Plan (Task T-global1)

## 1. Owner Decision (2026-11-19)

> `2026-11-19 — Owner decision: global expansion to full verification. Scope: bring all 8 regions (Argentina, South America, North America, Europe, Asia, Africa, Oceania & Pacific, Middle East) to the same station-vetting and source-verification standard as Argentina, before any region's status may read 'active' or 'verified' in public-facing docs. Hindcast calibration stays Argentina-only until each region accumulates enough archived history to run it honestly.`

---

## 2. Quantitative Verification Gates & Methodology

### Phase 1 — Source Verification (§3.8)
- Real endpoint probing, HTTP status codes, p50/p95/max latency (ms).
- Licensing & WMO Resolution 40 Annex 1 redistribution evaluation (US NOAA public domain vs international aerodrome METARs for non-commercial research use).
- Open-Meteo API volume & rate-limit envelope audit across all 8 regions (`<= 4,000 req/day`, `<= 300 req/min`).

### Phase 2 — Station Vetting
- Offline bulk cross-check against NOAA AWC station catalog and NOAA ISD/GHCN inventory.
- Distance & elevation tolerances:
  - Haversine distance: $\le 5.0\text{ km}$ = `PASS`.
  - Elevation difference: $\le 50\text{ m}$ = `PASS` ($50\text{ m} < \Delta \le 150\text{ m}$ = `WARN`; $> 150\text{ m}$ = `FLAG`).
- Resolution:
  - $5.0\text{ km} < \Delta \le 15.0\text{ km}$ with verified ICAO aerodrome match: auto-resolve to primary aerodrome coordinates.
  - $\Delta > 15.0\text{ km}$, unconfirmed in catalogs, duplicate, or dead station (0 METAR in 72h): remove station.
- Pass threshold: $\ge 80\%$ retained stations confirmed by independent second source with active telemetry, $\ge 5$ stations remaining.

### Phase 3 — Observation Reference & Day-Boundary Convention
- Usability gate: $\ge 80\%$ of vetted stations report $\ge 12\text{ obs/day}$ (mean interval $\le 2\text{ h}$) with valid air temperature and $< 15\%$ gap rate.
- Day-boundary alignment: Local calendar day matching forecast verification window to eliminate day-shift bias.
- Discrete sampling caveats (instantaneous METAR vs extreme thermometers) documented.
- Isolated archive module with timestamp-derived keys (`obsTime`), zero wall-clock dependency, and zero backfill claims.

### Phase 4 — Daily Archive Audit & Staged Workflow
- Daily forecast archive audit (`openmeteo-ensemble`):
  - `OBSERVED`: `.github/workflows/ingest.yml` was upgraded to `--region all` in commit `d11528f` on 2026-11-18.
  - `OBSERVED`: Hugging Face dataset contains 9 archived issue dates (2026-11-11 through 2026-11-19). However, issue dates 2026-11-11 through 2026-11-17 contain ONLY Argentina stations. Global 140-station forecast archiving began on 2026-11-18 (`results/ingest_status.json` records 551,040 rows for 2026-11-19).
  - `OBSERVED`: No non-Argentina region has more than 2 days of archived forecast history.
- Staged METAR observation reference workflow:
  - Staged `.github/workflows/observations-metar.yml` with daily cron `15 5 * * *` and `workflow_dispatch`.
  - Runs `backend/src/prisma/ingest/metar_archive.py` with `--region all --hours 48`.
  - Concurrency group `observations-metar-archive`, read-only permissions, isolated from SMN archive.

### Phase 5A — Anti-Drift Integrity Tests & Deterministic Promotion Gate
- Executable anti-drift tests re-computing all metrics from committed evidence JSONs.
- Deterministic promotion CLI (`backend/scripts/promote_verified_regions.py`).
- Strict prohibition against writing `status: active` or claiming non-Argentina hindcast calibration during autonomous runs.

---

## 3. Per-Region Verification Status Table

| Region Slug | Region Name | Phase 1 (Source §3.8) | Phase 2 (Vetting) | Phase 3 (Obs Ref) | Phase 4 (Daily Arch) | Current Status | Vetted / Total Stns |
|---|---|---|---|---|---|---|---|
| `argentina` | Argentina | Complete (`OBSERVED`) | Complete (`OBSERVED`) | Complete (SMN, `OBSERVED`) | Complete (`OBSERVED`) | `active` | 19 / 19 |
| `south_america` | South America | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 17 / 17 |
| `north_america` | North America | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 18 / 18 |
| `europe` | Europe | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 18 / 18 |
| `asia` | Asia | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 18 / 19 |
| `africa` | Africa | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 14 / 17 |
| `oceania` | Oceania & Pacific | PASS (`OBSERVED`) | PASS (`OBSERVED`) | PASS (`OBSERVED`) | Staged (`OBSERVED`) | `ready_for_review` | 16 / 16 |
| `middle_east` | Middle East | BLOCKED (`OBSERVED`) | BLOCKED (`OBSERVED`) | BLOCKED (`OBSERVED`) | Staged (`OBSERVED`) | `blocked` | 12 / 16 |

---

## 4. Evidence Commit Rules

- Machine-verifiable evidence files written directly by audit scripts to `results/stations/_evidence/<region>/audit.json`.
- Catalog downloads stored out-of-git in temporary storage, recording URL, timestamp, size, and SHA-256 hash.
- Markdown vetting reports in `results/stations/<region>_vetting.md` generated from committed evidence JSON.
