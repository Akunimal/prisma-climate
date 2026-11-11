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

Other catalogue parameters (from datos.gob.ar CKAN, not all probed): `datohorario` (hourly T/P/wind/humidity), `regtemp` (365-day temperature), `radsolar`, `pron5d` (5-day forecast). Responses are ZIP payloads containing one fixed-width text file each.

**Catalogue and metadata:** the authoritative dataset list is the datos.gob.ar CKAN package for org `servicio-meteorologico-nacional` (`https://datos.gob.ar/api/3/action/package_search?q=servicio%20meteorologico`). Landing page: `https://www.smn.gob.ar/descarga-de-datos`. Contact: `datosabiertos@smn.gob.ar`.

**Catalogue count reconciliation (verified 2026-11-11):** the probe file `data/smn_probe/estaciones/estaciones_smn.txt` has **124 physical lines**, which is not a station count. Composition: 2 blank lines + 1 header + 1 units line + **118 station rows** + 2 orphan fragments. The two fragments (`ERO`, `RO`) are the wrapped tails of station names that overflow the 30-character name column (`PRESIDENCIA ROQUE SAENZ PEÑA AERO`, `ESCUELA DE AVIACION MILITAR AERO`); the same two rows are the ones whose name and province run together with a single space, and both parse as stations. So the catalogue holds **118 stations** (parser output), matching the 118 rows in the `observaciones` payload. Counts of 120 (all non-header lines, orphans included) and 124 (raw `wc -l`) both overcount stations.

**License:** confirmed 2026-11-11 from two documents:

1. `PAD_legales.pdf` (Términos y Condiciones de Uso, section *Propiedad Intelectual*): "El SMN licencia todos sus contenidos bajo la licencia Creative Commons Atribución 2.5 Argentina" ([legal code](https://creativecommons.org/licenses/by/2.5/ar/legalcode)).
2. Infoleg disp25.pdf — *Política de Datos del Servicio Meteorológico Nacional* (`https://servicios.infoleg.gob.ar/infolegInternet/anexos/360000-364999/361173/disp25.pdf`): §2 scopes the policy to "todo dato propio del SMN … en su formato crudo, postprocesados o en forma de producto … datos observacionales … y pronósticos"; §4.A classifies web-accessible data as *Datos Abiertos* shared "bajo la licencia Creative Commons Atribución 2.5 Argentina, la cual compromete a los usuarios a atribuir al SMN como fuente en caso de hacer públicos los datos"; Apéndice I.2.5 quotes the licence terms (share, adapt, even commercially, with attribution).

**Redistribution:** `yes`, with attribution — credit SMN as the source and link the CC BY 2.5 AR licence whenever the data are published.

**Day convention:** `local_calendar`, verified from the payloads (not guessed):

- `datohorarioYYYYMMDD.txt` carries `FECHA` as DDMMYYYY plus `HORA` in `[HOA]` (Hora Oficial Argentina, UTC−3, no DST since 2009); the probe file for 2026-11-10 contains exactly hours 0–23 of that local date, so a day is the local calendar day.
- `observacionesYYYYMMDD.txt` is one `TMAX`/`TMIN` row per `FECHA` (local calendar day). The `fecha` query parameter is ignored by the endpoint — requesting `fecha=20261105` still returns the latest completed day — so only the most recent day is served and the connector merges each fetched day into `data/raw/smn-argentina.parquet`.

**What the connector does not claim:** `observaciones` provides `t2m_max`/`t2m_min` only; other SMN variables (`datohorario` hourly fields, `tiepre`, forecasts) are not ingested yet. Live series for the configured stations are built only for stations that resolve by NRO in both catalogue and payload.

## Tier 2 / Tier 3 (planned)

Registered in [`configs/sources.yaml`](../configs/sources.yaml) with `status: planned` and `day_convention: unknown`: INTA, NASA IMERG, CHIRPS, NOAA OISST, NOAA GEFS, ECMWF open data, NOAA ISD, INA, Servicio de Hidrografía Naval, NASA FIRMS, NASA SMAP, GOES-19, CAMMESA, OpenAQ/CAMS. Each needs the §3.8 verification (access method, licence, redistribution) before its connector is written.

## Day-convention rule

A source may not move to `status: active` while its `day_convention` is `unknown`. Mixing conventions across sources is the classic source of silent bias in cross-source comparisons; the field is stored on every row so analyses can group or filter by it.
