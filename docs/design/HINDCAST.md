# Hindcast design — GEFS members for Phase 2 calibration

Status: design + implementation note. Records the source chosen for the
Phase 2 CRPSS test (calibrated vs raw ensemble) required by
`docs/EVALUATION_PROTOCOL.md` §3.1 before the operational archive holds a
400-day fitting window (first complete window 2027-12-16).

Every number produced from this source is labelled **`hindcast`** with
provider and retrieval date (protocol amendment 2026-11-11). Hindcast
scores are never mixed with operational-archive scores in one series.

## 1. Why a hindcast is required

The operational forecast archive starts **2026-11-11**. Rolling fitting
needs 400 issue-dated samples (§3), so a calibrated skill number cannot
be validly fitted from the archive alone until **2027-12-16**, and a
held-out evaluation block not until **2029-01-19** (§3.1). Phase 2’s
exit gate is **CRPSS > 0 of calibrated vs raw ensemble** inside a 1–2
month window — therefore a hindcast is mandatory, not optional.

Raw-ensemble CRPS needs **member values**, not a deterministic series.

## 2. Chosen source

| Field | Value |
|---|---|
| Provider | NOAA National Weather Service GEFS |
| Dataset | GEFS v12 (and earlier flat layout) on AWS Open Data |
| Bucket | `noaa-gefs-pds` (`https://noaa-gefs-pds.s3.amazonaws.com/`) |
| Access | unauthenticated HTTPS GET / S3 ListObjectsV2 |
| Members | 31: control `gec00` + perturbed `gep01`…`gep30` |
| Cycle used | 00Z only (one issue hour per day; see §6) |
| Variables | GRIB `TMAX` / `TMIN` at `heightAboveGround` level 2 (daily max/min fields shipped by NCEP) |
| Grid | regular lat-lon **1.0°** (181×360), lon 0…359, units K |
| History | keys from **2017-01-01** (verified listing) through present |

Retrieval date for the first build: recorded in the runner output
metadata (`retrieved_at` UTC) and in `results/hindcast/` manifests.

## 3. Key layouts (both supported)

NCEP changed the S3 layout; both are real and HEAD-verified (2026-11-15):

**Flat (observed for 2017-01-01):**

```
gefs.YYYYMMDD/00/gec00.t00z.pgrb2afHHH
gefs.YYYYMMDD/00/gep01.t00z.pgrb2afHHH
…
gefs.YYYYMMDD/00/gep30.t00z.pgrb2afHHH
(+ .idx sidecars)
```

`HHH` = forecast hour zero-padded (000, 006, …). File ≈ 4.1 MB.

**Modern (observed for 2025-11-15 and 2026-06-01):**

```
# Product A 0.50° — preferred: ships TMAX/TMIN at 2 m
gefs.YYYYMMDD/00/atmos/pgrb2ap5/gec00.t00z.pgrb2a.0p50.fHHH
gefs.YYYYMMDD/00/atmos/pgrb2ap5/gep01.t00z.pgrb2a.0p50.fHHH
…

# Product S 0.25° fallback — also has TMAX/TMIN at 2 m
gefs.YYYYMMDD/00/atmos/pgrb2sp25/gec00.t00z.pgrb2s.0p25.fHHH
```

**Product B (`pgrb2bp5`) is rejected for this use:** its idx has `TMP` /
`APTMP` but **no `TMAX`/`TMIN`** (verified 2026-06-01). The client tries
flat → modern ap5 → modern sp25 and records which layout answered.
Same members (`gec00`, `gep01`…`gep30`) and `.idx` sidecars throughout.

## 4. Bandwidth strategy: `.idx` + HTTP Range

Full GRIB is too large for an 800-day × 31-member window (tens of GB).
`.idx` files list `msg_no:byte_offset:time:VAR:level:…`. The client:

1. GET `{key}.idx`
2. Locate the `TMAX` (and optionally `TMIN`) record byte range
   (offset → next record offset, capped at 2 MB)
3. GET `{key}` with `Range: bytes=start-end` (~70 KB per field on the
   1° product, verified: TMAX slice 70 262 bytes for `gefs.20170101`)
4. Decode with `cfgrib` `filter_by_keys={"typeOfLevel":
   "heightAboveGround", "level": 2}` and read `variables["tmax"].data`
   via `OnDiskArray.build_array()` (cfgrib 0.9.15 is not xarray-backed
   in this environment)

Station values are bilinear-free nearest-grid-point samples at the 19
region stations; only those scalars are stored.

## 5. Pairing with observations

Corrected mapping (protocol amendment **2026-11-15 §2b**, `rule =
localday-3p-v1`; the pre-amendment single-message rule is what Run A used
and Run A stays frozen):

- Issue = GEFS cycle **00Z** on UTC date `t` (that instant is 21:00 local
  on `t − 1`, America/Argentina/Buenos_Aires, UTC−3). For lead L the
  verifying **local day is V = t + L**, which in UTC spans
  **`[03Z V, 03Z V+1)`**.
- Per member, **`t2m_max` = max over the three 6-hour TMAX messages of
  day V that lie fully inside the local day**: idx labels
  `(24L+6, 24L+12)`, `(24L+12, 24L+18)`, `(24L+18, 24L+24)`
  `hour max fcst`, read from files `f{24L+12}`, `f{24L+18}`,
  `f{24L+24}` respectively (a message lives in the file of its label's
  end hour) — local **03:00–09:00, 09:00–15:00, 15:00–21:00 of V**.
  Message selection is **by exact `.idx` label** (variable token,
  start/end hours and max/min kind must all match); a missing or
  mismatched label fails the whole member slot for that lead, never a
  fallback period. The 6-hour periods that straddle a local-day
  boundary — `[00Z V, 06Z V)` and `[00Z V+1, 06Z V+1)` — are excluded.
- The straddling 3-hour labels (GEFS v12 ships both series) are never
  substituted for a required 6-hour label; only the 6-hour series tiles
  the day.
- Valid time = local calendar day **V = t + L** for joining SMN
  (`valid = issue_date + timedelta(days=lead)` in `run_crpss`,
  unchanged — only the forecast messages change).
- Observation reference: SMN Argentina daily TMAX/TMIN
  (`observations/smn/`, 2026-11-13 amendment; regtemp precedence per
  2026-11-14 rule 6).
- **Stated limit:** this rule covers local **03:00–21:00 of V** for
  `t2m_max`; local **00:00–03:00 and 21:00–24:00 of V are uncovered**
  by construction — a stated limitation of the rule, not an assumption
  of completeness. `t2m_min` (secondary) would cover only
  03:00–15:00; **Run B computes `t2m_max` only** and fetches no TMIN.
  Operational archive scoring (Phase 1 leaderboard) uses the archive’s
  own daily aggregates.

## 6. Cycle / issue-hour choice

Only the **00Z** cycle is downloaded (one run per day). The protocol
still requires `issue_time` on every output and the 00–11:59 / 12–23:59
UTC strata (§3.2). With a single cycle, all hindcast issues fall in the
00:00–11:59 band; that is disclosed in the output, not hidden. A
multi-cycle hindcast is a future amendment if needed.

## 7. Split used for the Phase 2 gate

The SMN regtemp capture used as the observation reference covers
**365 local days: 2025-11-11 → 2026-11-10** (112 SMN stations; region
stations resolved via catalogue NRO). Train and eval must both fit in
that window:

| Slice | Role | Size |
|---|---|---|
| Train | fit EMOS / quantile mapping | **180** issue dates (00Z), 2025-11-11 → 2026-05-09 |
| Eval | score raw vs calibrated (held out) | **185** issue dates, 2026-05-10 → 2026-11-10, strictly after train |
| Leads | protocol leads | 1, 3, 7, 10, 15 (subset; `MIN_SAMPLE = 10` still applies per cell) |
| Members | all 31 | 80 % rule (2026-11-14 rule 1) → ≥ 25 present |
| Target | primary | `t2m_max` (precip arm suspended, 2026-11-12); Run B computes `t2m_max` only, no TMIN (2026-11-16) |

180+185 = 365 keeps every scored day inside observed SMN coverage
while clearing `MIN_SAMPLE = 10` for every reported cell. A full 400+400
window is the protocol ideal and is a straight constant change once a
longer observation capture exists; it is **not** claimed as done.

Held-out evaluation is never used for fitting (§3). §8 open decisions
(EMOS variant / ENSO predictor / station-level vs pooled) are closed by
ablation **on the train slice only**, then frozen before eval scores are
read.

## 8. Dependencies

Added to `backend/pyproject.toml`:

- `cfgrib>=0.9.15` — GRIB → structured fields
- `eccodes>=2.50` — native GRIB engine pulled in by cfgrib

`scipy` is **not** required: EMOS uses numpy least squares
(`calibrate/emos.py`); quantile mapping is pure numpy.

## 9. Rejected alternatives

| Candidate | Why rejected |
|---|---|
| Open-Meteo Ensemble API | ~90 days of history only (start_date window 2026-08-14…2026-12-20 probed); no 400-day fit window |
| Open-Meteo Historical Forecast API | deterministic only; `temperature_2m_max_member*` rejected (400); cannot score raw-ensemble CRPS |
| Open-Meteo Previous Runs API | lead-offset deterministic series (`_previous_day1..7`); no members |
| Open-Meteo Single Runs API | preserves run identity but no member keys (`gseamless` / `gfs_global` single series); member-named dailies rejected |
| ERA5 / reanalysis “pseudo-forecasts” | §3: before-archive forecasts are not reconstructed from reanalysis; §4.3: baselines not scored against reanalysis-only pseudo-forecasts |
| TIGGE / CDS ensemble | requires API credentials not in repo policy for unattended CI |

Deterministic-only sources can demonstrate bias correction but **cannot**
satisfy the Phase 2 gate “calibrated vs **raw ensemble**”.

## 10. Honesty checklist

- [x] Provider + retrieval date on every hindcast artifact
- [x] Label string `hindcast` in tables, figures, docs mentions
- [x] No operational-archive score mixed into hindcast series
- [x] No skill number published under the 15-issue-date gate for the
      operational archive (gate still applies to Phase 1 leaderboard)
- [x] Negative or partial results reported with equal prominence
- [x] `issue_time` (00Z) and UTC stratum recorded on every cell
- [x] Member 80 % rule and `MIN_SAMPLE = 10` unchanged
