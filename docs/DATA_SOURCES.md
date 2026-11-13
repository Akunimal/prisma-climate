# Data sources

Human-readable version of [`configs/sources.yaml`](../configs/sources.yaml). If the two differ, the YAML wins. Every source carries a `day_convention` (how a value is aggregated into a day) that is copied into every stored row:

| Value | Meaning |
|---|---|
| `utc` | Timestamped and aggregated in UTC |
| `local_calendar` | Aggregated over the local calendar day at the location |
| `obs_hour_XX` | Value taken at a fixed observation hour (XX, 0–23 UTC) |
| `unknown` | Not verified yet; forbidden for `status: active` |

## Tier 1 (active in Phase 0)

### Open-Meteo Ensemble API — `openmeteo-ensemble`

- **Endpoint:** `https://ensemble-api.open-meteo.com/v1/ensemble` (REST, no key)
- **Use:** multi-model ensemble forecast (GFS 30 members, ECMWF IFS 0.25° 50 members), 16 days
- **Cadence:** every 6 hours; latency hours
- **Day convention:** `local_calendar`
- **License:** Open-Meteo CC BY 4.0; the free tier is non-commercial only
- **Redistribution:** `derived_only` — derived values only, no bulk republishing of their API responses
- **Verified:** 2026-11-11
- **Notes:** the API does not expose the model cycle time; `issue_time` is recorded as the fetch time (UTC) as a proxy.

### Open-Meteo Historical Weather API (ERA5) — `openmeteo-era5`

- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive` (REST, no key)
- **Use:** 1996–present daily history for climatology and training
- **Cadence:** daily; ~5 days behind real time
- **Day convention:** `local_calendar`
- **License:** Open-Meteo CC BY 4.0; underlying ERA5 under the Copernicus licence
- **Redistribution:** `derived_only`
- **Verified:** 2026-11-11
- **Notes:** gridded reanalysis, not a station measurement. Values are the grid cell nearest each configured station.

### NOAA GHCN-Daily — `ghcn-daily`

- **Endpoint:** `https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station_id}.dly` (fixed-width files, no key)
- **Use:** primary station observations (TMAX, TMIN, PRCP)
- **Cadence:** daily; latency days
- **Day convention:** `local_calendar` (GHCN-Daily elements are local-calendar-day totals/extremes)
- **License:** public domain (NOAA/NCEI, U.S. Government)
- **Redistribution:** `yes`
- **Verified:** 2026-11-11 (inventory: all 19 configured stations report TMAX/TMIN/PRCP through 2025)

### NOAA ONI — `noaa-oni`

- **Endpoint:** `https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` (ASCII, no key)
- **Use:** ENSO state as a slow signal
- **Cadence:** monthly; latency weeks
- **Day convention:** `utc`
- **License:** public domain (NOAA/NWS)
- **Redistribution:** `yes`
- **Verified:** 2026-11-11
- **Notes:** 3-month running means; mapped to the centre month of each season.

### NOAA CPC Antarctic Oscillation (SAM) — `noaa-sam`

- **Endpoint:** `https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/aao/monthly.aao.index.b79.current.ascii.table` (ASCII, no key)
- **Use:** Southern Hemisphere slow signal
- **Cadence:** monthly; latency weeks
- **Day convention:** `utc`
- **License:** public domain (NOAA/NWS)
- **Redistribution:** `yes`
- **Verified:** 2026-11-11

## SMN Argentina — `smn-argentina` (active)

Core source for the region. Access, licence terms and day convention were verified on 2026-11-11 before the connector was written (verification-before-connector rule, §3.8 of the plan); the connector is `backend/src/prisma/ingest/smn.py`.

**What each host does:**

| Host | Behaviour | Usable? |
|---|---|---|
| `www.smn.gob.ar` | Cloudflare managed JS challenge (HTTP 403, `Cf-Mitigated: challenge`) for plain HTTP clients | Only with a real browser; do not scrape around it |
| `ssl.smn.gob.ar` | Plain HTTP, no challenge | **Yes — this is the open-data API** |
| `api.smn.gob.ar` | Cloudflare in front, origin returns HTTP 522 | No — origin is down |
| `apidatos.smn.gob.ar` | DNS does not resolve | No — domain is gone |

**Open-data endpoints (no auth, verified 200 on 2026-11-11):**

```
https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=estaciones      # station list
https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=observaciones  # daily min/max temperature
https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=tiepre         # current weather snapshot
```

Other catalogue parameters (from datos.gob.ar CKAN, probed 2026-11-11): `datohorario` (hourly T/wind/humidity/pressure), `regtemp` (365-day temperature), `radsolar`, `pron5d` (5-day forecast), `tiepre` (current weather snapshot). Responses are ZIP payloads containing one fixed-width text file each.

**Catalogue and metadata:** the authoritative dataset list is the datos.gob.ar CKAN package for org `servicio-meteorologico-nacional` (`https://datos.gob.ar/api/3/action/package_search?q=servicio%20meteorologico`). Landing page: `https://www.smn.gob.ar/descarga-de-datos`. Contact: `datosabiertos@smn.gob.ar`.

**Catalogue count reconciliation (verified 2026-11-11):** the probe file `data/smn_probe/estaciones/estaciones_smn.txt` has **124 physical lines**, which is not a station count. Composition: 2 blank lines + 1 header + 1 units line + **118 station rows** + 2 orphan fragments. The two fragments (`ERO`, `RO`) are the wrapped tails of station names that overflow the 30-character name column (`PRESIDENCIA ROQUE SAENZ PEÑA AERO`, `ESCUELA DE AVIACION MILITAR AERO`); the same two rows are the ones whose name and province run together with a single space, and both parse as stations. So the catalogue holds **118 stations** (parser output), matching the 118 rows in the `observaciones` payload. Counts of 120 (all non-header lines, orphans included) and 124 (raw `wc -l`) both overcount stations.

**License:** confirmed 2026-11-11 from two documents:

1. `PAD_legales.pdf` (Términos y Condiciones de Uso, section *Propiedad Intelectual*): "El SMN licencia todos sus contenidos bajo la licencia Creative Commons Atribución 2.5 Argentina" ([legal code](https://creativecommons.org/licenses/by/2.5/ar/legalcode)).
2. Infoleg disp25.pdf — *Política de Datos del Servicio Meteorológico Nacional* (`https://servicios.infoleg.gob.ar/infolegInternet/anexos/360000-364999/361173/disp25.pdf`): §2 scopes the policy to "todo dato propio del SMN … en su formato crudo, postprocesados o en forma de producto … datos observacionales … y pronósticos"; §4.A classifies web-accessible data as *Datos Abiertos* shared "bajo la licencia Creative Commons Atribución 2.5 Argentina, la cual compromete a los usuarios a atribuir al SMN como fuente en caso de hacer públicos los datos"; Apéndice I.2.5 quotes the licence terms (share, adapt, even commercially, with attribution).

**Redistribution:** `yes`, with attribution — credit SMN as the source and link the CC BY 2.5 AR licence whenever the data are published.

**Day convention:** `local_calendar`, verified from the payloads (not guessed):

- `datohorarioYYYYMMDD.txt` carries `FECHA` as DDMMYYYY plus `HORA` in `[HOA]` (Hora Oficial Argentina, UTC−3, no DST since 2009); the probe file for 2026-11-10 contains exactly hours 0–23 of that local date, so a day is the local calendar day.
- `observacionesYYYYMMDD.txt` is one `TMAX`/`TMIN` row per `FECHA` (local calendar day). The `fecha` query parameter is ignored by the endpoint — requesting `fecha=20261105` still returns the latest completed day — so only the most recent day is served and the connector merges each fetched day into `data/raw/smn-argentina.parquet`.

**What the connector does not claim:** `observaciones` provides `t2m_max`/`t2m_min` only; `tiepre` and `pron5d` are text products and are not ingested. Live series for the configured stations are built only for stations that resolve by NRO in both catalogue and payload.

**Precipitation — pending, not available through the open-data API (probed 2026-11-11):** there is no precipitation field to aggregate, so no value was guessed.

| Payload | Fields actually present | Precip? |
|---|---|---|
| `datohorarioYYYYMMDD.txt` | `FECHA HORA TEMP HUM PNM DD FF NOMBRE` — units `[HOA] [ºC] [%] [hPa] [gr] [km/hr]` | no column, no units |
| `observacionesYYYYMMDD.txt` | `FECHA TMAX TMIN NOMBRE` | no |
| `registro_temperatura365d_smn.txt` (`regtemp`) | `FECHA TMAX TMIN NOMBRE` | no |
| `tiepre` | free-text current-weather lines | no |

`dato=precipitacion`, `precipitaciones`, `precip`, `lluvia`, `precipitacion_diaria`, `precipitacion30d`, `precip30d` and `lluvias` all return HTTP 200 with an **empty ZIP** (zero members), so there is no precipitation series behind the API either. Until SMN publishes one, daily precipitation in Phase 1 comes from GHCN-Daily `PRCP` (ingested) and from the ensemble forecast's `precip`; SMN precip stays `pending` with this reason rather than being faked or silently omitted.

**Series accumulation and the `regtemp` opportunity:** `observaciones` serves only the latest completed local day and ignores `fecha`, so the SMN series **accumulates forward from the first run — no backfill through this endpoint**. However, `regtemp` was probed on 2026-11-11 and serves `registro_temperatura365d_smn.txt` (42,953 rows, `FECHA TMAX TMIN NOMBRE`, **365 distinct local days from 2025-11-11 to 2026-11-10**, **118 distinct station names** under fixed-column parsing). A whitespace `split()` parse inflated that to ~135 by inventing tokens from 2,329 rows with blank `TMAX`/`TMIN`; the script-generated table in [`results/regtemp_names/`](../results/regtemp_names/) shows **118/118 exact** catalogue matches, 6 stations with partial coverage (117 missing station-days) and **19/19 region stations resolved** via catalogue NRO. That is a candidate backfill for `t2m_max`/`t2m_min` over the GHCN staleness gap; it is recorded here as observed and **still not wired into the connector** (the connector keeps accumulating forward from `observaciones` only).

**Perishable `regtemp` capture (2026-11-12):** the endpoint serves a **rolling 365-day window** — older days roll off and are lost — so the raw ZIP was fetched and persisted under `data/smn_probe/regtemp/` (gitignored) with `manifest.json` recording `retrieved_at` (2026-11-12T01:41:32Z), the served window (2025-11-11 → 2026-11-10, 365 days, 42,953 rows), sha256, observed fields (`FECHA` as `DDMMYYYY`, `TMAX`, `TMIN`, `NOMBRE`) and the `local_calendar` day-convention evidence (date-only, no hour column). Capture does not imply ingest: the file is **read in place only** by the discrepancy script's SMN leg (below), never committed and never uploaded as an Actions artifact.

**SMN leg of the source-discrepancy report (since 2026-11-12):** `python -m prisma.report.discrepancies` loads the capture above as a data dependency when it is present (`--regtemp`, default `data/smn_probe/regtemp/registro_temperatura365d_smn.txt`) and appends an **SMN leg** to `results/discrepancies/era5_vs_ghcn.md`:

- **Comparison convention:** ERA5, GHCN-Daily and regtemp all store `day_convention: local_calendar`, so every join is on the same local calendar day — stated explicitly in the report.
- **Station identity:** each of the 19 configured region stations resolves GHCN id → SMN NRO (from `estaciones_smn.txt`) → catalogue name → regtemp name (exact, then fuzzy ≥ 0.85). The resolution table is part of the report output.
- **Provenance recorded in the report:** capture window, distinct days, data-row count, sha256, endpoint, retrieval timestamp and the day-convention evidence from `manifest.json`, plus per-station row-day/value coverage (`results/discrepancies/smn_regtemp_coverage.csv`).
- **Gaps, never filled:** absent station-days and blank `TMAX`/`TMIN` fields (including the known 117 missing station-days from partial-coverage stations) are reported as gaps; the leg emits no row for them and never interpolates or carries values forward.
- **Same flag scheme as the ERA5–GHCN leg:** temperature |bias| ≥ 3 °C or corr < 0.90. These are **cross-source discrepancy diagnostics, not skill metrics** — no CRPS/Brier/reliability/leaderboard number is computed before the 15-issue-date gate in [`docs/EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md).
- Outputs: `smn_vs_era5.csv` and `smn_vs_ghcn.csv` (only when overlapping days exist), `smn_regtemp_coverage.csv`, and the markdown section. Values are taken as served — no QC pass in this leg; the connector's live `smn-argentina.parquet` series is **not** merged in.

## Tier 2 verification — 2026-11-12

§3.8 verification (access, licence + redistribution, day convention, empirical latency) for the two option-(a) precipitation products of [`docs/PRECIP_REFERENCE_OPTIONS.md`](PRECIP_REFERENCE_OPTIONS.md). Probe-only: plain documented HTTP clients, no login, no challenge bypass, no bulk download. Both sources stay `status: planned` in [`configs/sources.yaml`](../configs/sources.yaml) — no connector was written. Citations below are URLs, HTTP codes, timestamps and observed dates only.

### NASA IMERG (GPM) — `imerg`

| Item | Finding |
|---|---|
| Product pinned | IMERG **Late Run**, L3 daily, 0.1°, collection `GPM_3IMERGDL` version `07` (granule algorithm id `V07C` observed). Early (`GPM_3IMERGDE.07`) and Final (`GPM_3IMERGDF.07`) were probed for the family picture. |
| Endpoints | Metadata (no auth): `https://cmr.earthdata.nasa.gov/search/granules.json?short_name=GPM_3IMERGDL&version=07&sort_key=-start_date&page_size=3`. Data file: `https://data.gesdisc.earthdata.nasa.gov/data/GPM_L3/GPM_3IMERGDL.07/{yyyy}/{mm}/{granule}.nc4`. Product directory: `https://gpm.nasa.gov/data/directory`. PPS near-real-time alternative: `https://jsimpsonhttps.pps.eosdis.nasa.gov/imerg/late/`. |
| Access | CMR metadata: plain HTTPS, **HTTP 200**, no auth (2026-11-12T16:12Z–16:50Z). Data file without credentials: **HTTP 302 → `https://urs.earthdata.nasa.gov/oauth/authorize?…`** (observed 2026-11-12T16:50Z) — **access requires a free Earthdata Login**; GES DISC states "Access to GES DISC data requires all users to be registered with the Earthdata Login system. Data continue to be free of charge and accessible via HTTPS." (`https://gpm1.gesdisc.eosdis.nasa.gov/data/`, HTTP 200, read 2026-11-12). PPS NRT returns **HTTP 401** (2026-11-12T16:09Z); the GPM directory page documents "Use of the PPS data servers and STORM requires you to first register your email address." Neither requirement was routed around. Migration note on the same GES DISC page: server access "will end no earlier than September 30th 2026. Users will need to transition to Earthdata Cloud for continued data access." |
| Observed lag | **Late daily:** latest granule covers obs day **2026-11-11**, CMR `updated` **2026-11-12T14:32:02Z** — as of the run (2026-11-12T16:50Z) the latest served day is 1 calendar day behind the run date (evidence: CMR URL above, HTTP 200). **Early daily:** obs day 2026-11-11, `updated` 2026-11-12T04:31:43Z (evidence: same CMR API with `short_name=GPM_3IMERGDE`; granule `time_start` 2026-11-11T00:00:00.000Z / `time_end` 2026-11-11T23:59:59.999Z). **Final daily:** latest obs day **2025-09-30**, `updated` 2026-02-02 — about 13.5 months behind at run time (evidence: `short_name=GPM_3IMERGDF`, HTTP 200, 2026-11-12T16:15Z). |
| Licence | "GPM and TRMM data are freely available at all levels for which the particular sensor or sensor combination has been processed by GPM." … "The data set source should be acknowledged when the data are used." — [Data Usage Policy & Citation Instructions](https://gpm.nasa.gov/data/policy), HTTP 200, read 2026-11-12. |
| Redistribution | `yes` — freely available, citation/attribution requested. |
| Day convention | `utc` — the pinned daily granule's CMR metadata is `time_start 2026-11-11T00:00:00.000Z` / `time_end 2026-11-11T23:59:59.999Z`, and the granule filename carries `-S000000-E235959` (00:00:00–23:59:59): one UTC calendar day. Evidence: CMR granule record (URL above), HTTP 200, 2026-11-12T16:50Z. |

### CHIRPS v2.0 daily (UCSB Climate Hazards Center) — `chirps`

| Item | Finding |
|---|---|
| Product pinned | CHIRPS **v2.0** daily, 0.05°, 50°S–50°N, in both the **preliminary** and **final** variants. |
| Endpoints | Final: `https://data.chc.ucsb.edu/products/CHIRPS/v2.0/global_daily/` (per-day GeoTIFFs under `tifs/p05/{yyyy}/`, yearly NetCDF under `netcdf/p05/chirps-v2.0.{yyyy}.days_p05.nc`). Preliminary: `https://data.chc.ucsb.edu/products/CHIRPS/v2.0/prelim/global_daily/`. The previously documented path `…/products/CHIRPS-2.0/` now returns **HTTP 404** (moved; 2026-11-12T16:09Z). |
| Access | Plain HTTPS directory listings, no auth: **HTTP 200** (2026-11-12T16:12Z–16:45Z). **Rate-limited:** repeated probes drew **HTTP 429** from the nginx front end (observed 2026-11-12T16:10Z–16:40Z) — any future connector must pace requests. The CHC FAQ wiki (`https://wiki.chc.ucsb.edu/CHIRPS_FAQ`) did not answer connections from this environment (connect timeout, 2026-11-12T16:10Z and 16:35Z) — recorded as a finding, not worked around. |
| Observed lag | **Preliminary daily:** latest file `chirps-v2.0.2026.11.10.tif.gz` → obs day **2026-11-10**, 2 calendar days behind the run date, as of 2026-11-12T16:40Z (evidence: `…/prelim/global_daily/tifs/p05/2026/`, HTTP 200). **Final daily:** latest per-day tif obs day **2026-09-30** as of 2026-11-12T16:51Z (evidence: `…/global_daily/tifs/p05/2026/`, HTTP 200); the final yearly NetCDF `chirps-v2.0.2026.days_p05.nc` reports `Last-Modified: Thu, 15 Oct 2026 18:29:17 GMT` (HEAD request, HTTP 200, 2026-11-12T16:33Z). |
| Licence | "To the extent possible under the law, Pete Peterson has waived all copyright and related or neighboring rights to CHIRPS. CHIRPS data is in the public domain as registered with Creative Commons." — [CHC CHIRPS page](https://www.chc.ucsb.edu/data/chirps), HTTP 200, read 2026-11-12. |
| Redistribution | `yes` — public domain. |
| Day convention | `utc` — "The date D of a daily value is a consistent UTC calendar-day label: the CFSv2 daily data are used on their standard UTC calendar days, without shifting, so a value labelled D uses disaggregation data from approximately 00:00 UTC on D to 00:00 UTC on D+1." … "The date should be read as a UTC day label, not as a uniform 24-hour observation window." — [README-CHIRPS2-Daily.txt](https://data.chc.ucsb.edu/products/CHIRPS/v2.0/README-CHIRPS2-Daily.txt), HTTP 200, read 2026-11-12. The same README states daily CHIRPS is a CFSv2 temporal disaggregation of the pentad totals ("there is no separate daily station-blending step … Daily CHIRPS is therefore not an independent daily product") — a limitation to carry into any future use. |
| Retirement notice | The same README: "CHIRPS v2 is being retired. Its last month of operation will be December 2026." The successor, CHIRPS v3 daily (`rnl`/`sat`), is already served at `https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/` (HTTP 200, 2026-11-12T16:35Z) and its readme repeats the UTC-day-label convention. Any future connector decision must plan the v2 → v3 transition. |

Both products remain **Tier 2, `status: planned`**: verification only, no connector, no ingest. Per the 2026-11-12 amendment in [`docs/EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md) they are registered as **candidate SECONDARY / spatial-proxy references only**; promotion to any reference role requires a future dated amendment.

## Tier 2 / Tier 3 (planned)

Registered in [`configs/sources.yaml`](../configs/sources.yaml) with `status: planned`: INTA, NOAA OISST, NOAA GEFS, ECMWF open data, NOAA ISD, INA, Servicio de Hidrografía Naval, NASA FIRMS, NASA SMAP, GOES-19, CAMMESA, OpenAQ/CAMS — all with `day_convention: unknown`, which each still needs the §3.8 verification (access method, licence, redistribution) before its connector is written. NASA IMERG and CHIRPS were verified on 2026-11-12 (section above) and also remain `status: planned`.

## Where the daily forecast archive lives

The archive written by [`.github/workflows/ingest.yml`](../.github/workflows/ingest.yml) is stored **outside git**, in two places:

- **Primary store — Hugging Face dataset [`Akunimal/prisma-climate`](https://huggingface.co/datasets/Akunimal/prisma-climate):** one file per issue date at `forecasts/<issue_date>/openmeteo-ensemble_<issue_date>.parquet`. Verified present on 2026-11-11 via the HF API (siblings list and repository sha change after upload). The issue date is read from the parquet's `issue_time` column, never from the runner clock, and an existing target path is skipped: the **first archive of an issue date is canonical and frozen**.
- **Fallback / provenance — GitHub Release `forecast-YYYY-MM-DD`:** used when `HF_TOKEN`/`HF_DATASET_REPO` are unconfigured **or** the Hugging Face upload step fails, so a transient Hugging Face error never loses a day. Releases are kept afterwards as provenance (for example [`forecast-2026-11-11`](https://github.com/Akunimal/prisma-climate/releases/tag/forecast-2026-11-11), whose asset is the canonical 2026-11-11 archive).

Schema, licences, attribution and the evaluation gate for that dataset are documented in [`docs/HF_DATASET_CARD.md`](HF_DATASET_CARD.md), which is mirrored to the dataset's `README.md`.

**Trigger provenance (as of 2026-11-12):** the schedule is **proven** — the first `event=schedule` run completed on 2026-11-12: [run 43249798026](https://github.com/Akunimal/prisma-climate/actions/runs/43249798026), `event=schedule`, conclusion `success`, created/started `2026-11-12T15:37:24Z`, updated `2026-11-12T15:46:20Z`, headSha `1e82b23` — the **12:17 UTC slot**, started ~3h20m late (GitHub documents scheduled runs as best-effort and subject to delay or drop under load; this was a delay, not a drop). It was a data no-op: `forecasts/2026-11-12/` was already canonical from the morning manual `workflow_dispatch` rescue ([run 43183607191](https://github.com/Akunimal/prisma-climate/actions/runs/43183607191)), which uploaded `forecasts/2026-11-12/openmeteo-ensemble_2026-11-12.parquet` (107,951 bytes, sha256 `689a013ffc6f23742a2728b1aefffc0c0733c533513e183ccd6b38209f10d2e5`) at dataset revision `7087bb0fb450c44b4547605857aced67189b4877`; the GitHub Release fallback was **not** used; the scheduled run only left the ingest status heartbeat commit `2838acd`. Before that, as recorded on the morning of 2026-11-12 (commit `5e3df3c`, 09:54 UTC), the first eligible slot — 06:47 UTC, the original single cron, the workflow having landed on the default branch on 2026-11-11 after that day's slot had passed — had produced no run, so the issue date was rescued by manual dispatch. Full observed schedule history for 2026-11-12 (all `event=schedule`, conclusion `success`): **15:37:24Z** (run 43249798026), **19:52:06Z** (run 43294532842), **23:44:27Z** (run 43331372851), against that day's three slots — 06:47 (the original cron) plus 12:17 and 18:31 (added 09:50:59Z by `cbd8676`). GitHub does not expose which cron produced which run; a run starts at or after its slot, which leaves exactly four one-to-one readings, with per-slot delays for (06:47, 12:17, 18:31) of **(8h50m, 7h35m, 5h13m)**, **(8h50m, 11h27m, 1h21m)**, **(13h05m, 3h20m, 5h13m)** or **(16h57m, 3h20m, 1h21m)** — in every reading every run was at least ~1h21m late and no run was on time (the usually cited pairing is the last one: 12:17→15:37 ~3h20m, 18:31→19:52 ~1h21m, 06:47→23:44 ~16h57m). On 2026-11-13 the schedule was redesigned to five daily slots — **06:47, 09:47, 12:17, 14:43, 18:31 UTC** — keeping the original 06:47 attempt for spread (for dropped rather than delayed slots, more spread-out attempts hedge better, and 06:47 plus a multi-hour delay still lands inside the same UTC day), weighting the remaining attempts into 09:00–15:00 UTC where a multi-hour delay still lands inside the same UTC day (the issue date is the fetch date), with 18:31 kept as the last chance; the same-day no-op test covers repeated same-day runs. **Residual risk:** GitHub schedules are best-effort — a slot can be delayed or dropped, a UTC day with no successful run is lost verification data, and nothing self-heals; `scripts/archive_watchdog.py` (run by the workflow) records missing days under `archive_watchdog` in `results/ingest_status.json` for visibility only and never repairs them; it reads the archive through an HF repository listing that can be cache-prone, so a reported missing day may be a false positive — verify against the dataset before acting. The 15-issue-date evaluation gate counts distinct issue dates regardless of trigger; this manual rescue is recorded here so it stays visible.

## Day-convention rule

A source may not move to `status: active` while its `day_convention` is `unknown`. Mixing conventions across sources is the classic source of silent bias in cross-source comparisons; the field is stored on every row so analyses can group or filter by it.
