# Evaluation protocol

Written before any calibration or training, as required by the project plan. Amendments must be appended with a date; the original thresholds are never silently edited.

Status: **Phase 0 — protocol frozen for Phase 1 verification.** The verification-metrics module exists as code and tests (`backend/src/prisma/verify/metrics.py`), but no metric number is published yet — nothing in `results/` claims a CRPS, Brier score or reliability number until the 15-issue-date gate opens.

## 1. Question

How reliable are open ensemble forecasts (GFS, ECMWF, …) over Argentina at 1–15 days, and how much does a local statistical post-processing step conditioned on slow signals (ENSO phase, SST anomaly) improve them?

## 2. Falsifiable hypothesis

Local calibration (EMOS / quantile mapping) conditioned on ENSO reduces CRPS for daily maximum temperature and daily precipitation versus the raw ensemble, at **X % or more** of the region's stations, while keeping 90 % nominal reliability with deviation below 0.05.

**X is fixed here before any calibration run: X = 60 %.** Rationale: a method that only helps a minority of stations is not worth the operational complexity of the app. If the result is below X, the hypothesis fails and that failure is reported, not re-thresholded.

## 3. Data splits

| Use | Period | Notes |
|---|---|---|
| Training / fitting | 1996-01-01 → (today − 400 days) | ERA5 history + archived forecasts once available |
| Calibration fitting window | rolling 400 days before each issue date | avoids using future observations to calibrate a past forecast |
| Final evaluation | last 400 days with both forecast and observation | never used for fitting |
| Slow signals | ONI/SAM as published at issue time | no retrospective revisions in the features |

Forecasts archived from Phase 0 onward are the only issue-dated samples; before-archive forecasts are not reconstructed from reanalysis.

## 4. Baselines (every score is reported against all three)

1. **Raw ensemble** (the control).
2. **Climatology** — empirical distribution of the observation over the training window, same calendar window (±15 days).
3. **Persistence** — the last observed value carried forward; only meaningful at short leads, reported as `n/a` beyond 3 days.

A calibration method is only interesting if it beats the raw ensemble; beating only climatology is not enough.

## 5. Metrics

| Target | Metric | Aggregation |
|---|---|---|
| Continuous (t2m_max, t2m_min, precip) | CRPS; skill score vs each baseline (CRPSS) | per station, per lead day, then area-weighted mean |
| Binary events (frost, heat wave, heavy rain) | Brier score; Brier skill score | per station, per threshold, per lead day |
| Probabilistic calibration | reliability diagram; empirical coverage of the 50 % and 90 % bands | pooled per lead day and per station |

Event thresholds are fixed before scoring:

- **Frost:** `t2m_min < 0 °C`
- **Heat wave:** `t2m_max ≥ 90th percentile` of the training-window calendar-day distribution
- **Heavy rain:** `precip ≥ 95th percentile` of the training-window calendar-day distribution

Percentile thresholds are computed once from the training window and frozen.

## 6. Statistical testing

- Paired bootstrap over issue dates (1000 resamples) for CRPS differences, raw vs calibrated.
- A station/lead-day cell counts as an improvement only if the 95 % bootstrap interval of the CRPS difference excludes zero in the improving direction.
- Multiple comparisons: report raw counts of improved cells; no Bonferroni correction, but the headline X % uses the same rule for every station so the threshold is not moved after the fact.

## 7. Reporting rules

- Every figure and table in `results/` is produced by a script in this repository; no hand-edited numbers.
- Negative results are published with the same prominence as positive ones. A phase gate that fails is documented, not hidden.
- No metric is quoted for a source or period that was not actually archived and verified.

## 8. Open decisions (to close before Phase 2 calibration)

1. Exact EMOS variant and predictor set (ENSO state in or out — decided by ablation on the training window only).
2. Precipitation handling: censored EMOS vs quantile mapping (decided by CRPS on the training window).
3. Whether station-level or pooled calibration is the app default (decided by the reliability deviation, not by aesthetics).


## Amendments

### 2026-11-11 — Archive maturity gate and hindcast labelling

Appended (original thresholds above unchanged; **X = 60 % remains frozen**):

1. **No leaderboard or skill numbers** (CRPS, CRPSS, Brier, BSS, reliability, coverage) may be published in `results/` until the daily forecast archive holds **at least 15 distinct issue dates**. Until then only code and unit tests may land; sample-size honesty applies even after day 15.
2. If a **historical-forecast API** is ever used to build a hindcast (forecasts not issued on that calendar day by our archive), every table, figure and docs mention must label the numbers **`hindcast`** explicitly, with the provider and retrieval date. Operational archive scores and hindcast scores are never mixed in one series without that label.
3. Climatology and persistence baselines are scored only on days that also have an archived forecast issue; no baseline is scored against reanalysis-only pseudo-forecasts.

### 2026-11-12 — Protocol body restoration after accidental truncation

On 2026-11-12 we verified this file after commit `8ebaba7` accidentally replaced the protocol body (§1–8) with only the Amendments appendix. The body was restored verbatim from `9661420` in `61018d6`.

Byte-level comparison (evidence under `results/protocol_integrity/`):

- `body_restore_9661420_vs_61018d6.diff` and `body_restore_9661420_vs_HEAD.diff` — body of `9661420` vs the restored body: identical except one extra trailing newline before `## Amendments`.
- `truncation_8ebaba7_vs_restore.diff` — full truncated (`8ebaba7`) vs restored (`61018d6`) file: the whole body is re-added; the Amendments appendix is preserved.

**No threshold, split, percentile or testing rule changed.** X = 60 %, the 400-day splits, the 90th/95th percentiles, the 1000-resample bootstrap and the reporting rules are unchanged.

### 2026-11-12 — Precipitation reference decision

Appended after the preceding amendments; the original thresholds above are untouched — **X = 60 % and the 15-issue-date gate (earliest 2026-11-25) are unchanged**.

1. **Decision (project owner, instructed 2026-11-12): option (c) is adopted as the standing rule.** The precip arm of the Phase 1 hypothesis is **not verifiable on the operational archive (issue dates ≥ 2026-11-11)** until a fresh station precipitation reference exists. Re-checks on 2026-11-12 confirmed the premise: GHCN-Daily `PRCP` is still stale at source (all 19 configured stations re-fetched from `https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station_id}.dly`, HTTP 200, aggregate latest valid PRCP = 2025-08-24, no station covers 2025-11-11 onward), SMN's `observaciones` payload still has no precipitation column (`https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=observaciones`, HTTP 200, 2026-11-12T16:07:21Z, fields `FECHA TMAX TMIN NOMBRE` only), and ERA5 is reanalysis, not station truth. The **temperature arm proceeds unchanged** under the same X and the same gate.
2. **Option (b) is not adopted at this time**: no precip scores on the historical GHCN period for now. It may be revisited only by a future dated amendment.
3. **IMERG and CHIRPS** (§3.8 verification on 2026-11-12, recorded in `docs/DATA_SOURCES.md` section "Tier 2 verification — 2026-11-12"): both passed the access + licence + day-convention check with plain documented clients. IMERG Late Run daily V07: observed lag 1 day (latest granule covers obs day 2026-11-11, ingested 2026-11-12T14:32:02Z; data files themselves require a free Earthdata Login — HTTP 302 to `urs.earthdata.nasa.gov`), licence "GPM and TRMM data are freely available…" with citation requested, day convention UTC. CHIRPS v2.0 daily: observed lag 2 days on the preliminary variant (through obs day 2026-11-10) and about 6 weeks on the final variant (through 2026-09-30), open HTTPS listings but HTTP 429 rate-limiting observed, licence public domain (copyright waiver), day convention UTC calendar-day label. Both are registered as **Tier 2 planned sources** and, having passed, as **candidate SECONDARY / spatial-proxy references only** — promotion to any reference role requires a future dated amendment that states explicitly what the hypothesis would then measure (a satellite/gridded estimate is not station truth).
4. **No precip number may appear in `results/` under any option before the 15-issue-date gate** (earliest 2026-11-25).