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
4. **Which series "the observation" is for the climatology baseline (§4) — OPEN OWNER DECISION, recorded 2026-11-13, nothing decided here.** §4 says "empirical distribution of the observation" without naming the series, and the candidates differ materially: the T26a discrepancy report (`results/discrepancies/era5_vs_ghcn.md`) shows ERA5 at −0.97 °C mean against SMN on t2m_max, while GHCN-Daily is sparse and stale (last valid rows 2025-08-24, about 50% daily coverage since 2005). **This must be closed by a dated amendment before the 15-issue-date gate (earliest 2026-11-25)** — earlier than the Phase 2 horizon of the other items in this list. No threshold, split, percentile or testing rule changes by recording it. **CLOSED 2026-11-13 by the dated amendment `### 2026-11-13 — Temperature observation reference and climatology baseline` below: SMN Argentina is the temperature observation reference and the climatology baseline is ERA5 adjusted to SMN.**


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

1. **Decision (project owner, instructed 2026-11-12): option (c) is adopted as the standing rule.** The precip arm of the Phase 2 hypothesis (label corrected 2026-11-13; it previously read "Phase 1 hypothesis") is **not verifiable on the operational archive (issue dates ≥ 2026-11-11)** until a fresh station precipitation reference exists. Re-checks on 2026-11-12 confirmed the premise: GHCN-Daily `PRCP` is still stale at source (all 19 configured stations re-fetched from `https://www.ncei.noaa.gov/pub/data/ghcn/daily/all/{station_id}.dly`, HTTP 200, aggregate latest valid PRCP = 2025-08-24, no station covers 2025-11-11 onward), SMN's `observaciones` payload still has no precipitation column (`https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=observaciones`, HTTP 200, 2026-11-12T16:07:21Z, fields `FECHA TMAX TMIN NOMBRE` only), and ERA5 is reanalysis, not station truth. The **temperature arm proceeds unchanged** under the same X and the same gate.
2. **Option (b) is not adopted at this time**: no precip scores on the historical GHCN period for now. It may be revisited only by a future dated amendment.
3. **IMERG and CHIRPS** (§3.8 verification on 2026-11-12, recorded in `docs/DATA_SOURCES.md` section "Tier 2 verification — 2026-11-12"): both passed the access + licence + day-convention check with plain documented clients. IMERG Late Run daily V07: observed lag 1 day (latest granule covers obs day 2026-11-11, ingested 2026-11-12T14:32:02Z; data files themselves require a free Earthdata Login — HTTP 302 to `urs.earthdata.nasa.gov`), licence "GPM and TRMM data are freely available…" with citation requested, day convention UTC. CHIRPS v2.0 daily: observed lag 2 days on the preliminary variant (through obs day 2026-11-10) and about 6 weeks on the final variant (through 2026-09-30), open HTTPS listings but HTTP 429 rate-limiting observed, licence public domain (copyright waiver), day convention UTC calendar-day label. Both are registered as **Tier 2 planned sources** and, having passed, as **candidate SECONDARY / spatial-proxy references only** — promotion to any reference role requires a future dated amendment that states explicitly what the hypothesis would then measure (a satellite/gridded estimate is not station truth).
4. **No precip number may appear in `results/` under any option before the 15-issue-date gate** (earliest 2026-11-25).

### 2026-11-13 — Pre-gate clarifications

Appended after the preceding amendments; the original thresholds above are untouched — **X = 60 %, the 400-day splits, the 90th/95th percentiles, the 1000-resample bootstrap, the 15-issue-date gate and the reporting rules remain frozen**. Recorded 2026-11-13 (UTC), project-owner instructions.

**3.1 — Two maturity milestones.** The reading below was verified against the exact §3 rows before writing: `| Calibration fitting window | rolling 400 days before each issue date | avoids using future observations to calibrate a past forecast |`, `| Final evaluation | last 400 days with both forecast and observation | never used for fitting |`, and "Forecasts archived from Phase 0 onward are the only issue-dated samples; before-archive forecasts are not reconstructed from reanalysis." The archive starts **2026-11-11**, so:

1. **First issue date with a complete fitting window: 2027-12-16** (2026-11-11 + 400 days; arithmetic re-checked). Before that date the rolling 400-day window cannot hold 400 issue-dated samples, so no calibrated number can be validly fitted from the operational archive alone.
2. **First date at which a fully held-out evaluation block exists: 2029-01-19** (2026-11-11 + 800 days = 400 fitting days + 400 evaluation days; an evaluation block starting 2027-12-16 runs through 2029-01-18).

Consequences, stated plainly:

- The **15-issue-date gate** (earliest 2026-11-25) opens publication of **raw-ensemble verification and the three baselines only** — the Phase 1 leaderboard (`docs/ROADMAP.md` Phase 1 exit gate: "Leaderboard of raw ensemble vs climatology vs persistence, generated by script").
- The **X = 60 % hypothesis test** (calibrated vs raw) *additionally* requires the fitting window to hold issue-dated samples — via archive maturity on the dates above, **or** via a hindcast built under the 2026-11-11 hindcast-labelling amendment. **No calibrated skill number before that, regardless of the 15-date gate.**
- Therefore a hindcast is **required** for any test inside the ROADMAP's Phase 2 indicative window (1–2 months), not merely an option.

**Label fix.** The hypothesis is tested in **Phase 2** per `docs/ROADMAP.md` exit gates (Phase 1 = raw vs climatology vs persistence; Phase 2 = "CRPSS > 0 of calibrated vs raw ensemble"). The literal "Phase 1 hypothesis" in the 2026-11-12 precipitation amendment above and in `docs/PLAN.md` §2 is corrected to **Phase 2 hypothesis** in the same commit; no gate's substance changes.

**3.2 — `issue_time` handling (project owner decision, instructed 2026-11-13).**

1. Every verification output must carry `issue_time`. Headline numbers are pooled over the sample **with the issue-hour distribution disclosed**.
2. The issue-hour distribution table must be **generated by a repository script into `results/`** — not prose, not hand-written.
3. Results are also reported per issue-hour stratum (UTC bands 00:00–11:59 / 12:00–23:59; finer only where n allows) as a **sensitivity check**. At ~15–40 issue dates (~7–20 per band) the strata are **not powered comparisons**.
4. If strata disagree in sign, that is **reported as a limitation**. Never select the favourable stratum. No issue-dated sample may be excluded after seeing results.
5. Every headline number carries a **heterogeneous-cycle sample label** until a uniform-cycle hindcast exists. If one is adopted (labelled per the 2026-11-11 amendment), the hypothesis test uses it and the operational archive remains the forward-verification sample.

### 2026-11-13 — Temperature observation reference and climatology baseline

Appended after the preceding amendments; the original thresholds above are untouched — **X = 60 %, the 400-day splits, the 90th/95th percentiles, the 1000-resample bootstrap, the 15-issue-date gate (earliest 2026-11-25) and the reporting rules remain frozen**. Recorded 2026-11-13 (UTC), project-owner instruction; this closes §8 item 4.

1. **Temperature observation reference.** For Phase 1 verification of `t2m_max` and `t2m_min`, the observation reference is **SMN Argentina** daily temperature, ingested under `observations/smn/` and labelled by local calendar day.
2. **GHCN-Daily excluded from Phase 1 reference roles.** GHCN-Daily is not used as a verification reference, training target or climatology source in Phase 1: its last valid rows share the 2025-08-24 cutoff with ISD/GSOD (stale), and TMAX is 100 % S-flag (GSOD-derived) from 2005 onward (G share 73.9 % in 1996–2003, 39.2 % in 2004). GHCN remains only in the discrepancy diagnostics (`results/discrepancies/`).
3. **Climatology baseline for temperature** (§4 item 2) is the ERA5 series (`models=era5`) at the station points over the protocol training window, **adjusted to SMN** by a per-station, per-calendar-month mean difference (SMN − ERA5) estimated **only** on the overlapping regtemp window **2025-11-11 → 2026-11-10**. The §4 ±15-day calendar-window rule is unchanged; the adjustment shifts the ERA5 climatology onto the SMN reference scale.
4. **Fallback.** A station-calendar-month cell with fewer than 20 paired days uses the station's all-months mean difference instead, recorded in the table with its `n` and a fallback flag (observed case: Formosa `t2m_max` has zero paired days in September and October).
5. **Computed once and frozen.** The adjustment table is produced by `scripts/smn_era5_climatology_adjustment.py` into `results/climatology_adjustment/smn_era5_adjustment.{csv,md}` with the sha256 of every input file recorded in the output. The estimation window ends 2026-11-10, before the first issue date 2026-11-11, so no forecast-period observation enters the table. The table is frozen: regeneration requires an explicit `--force` and a new dated amendment.
6. **Stated limits.** One year of overlap; the correction is a mean shift only (no variance or quantile adjustment); station-month estimates rest on roughly 20–31 paired days each.
7. **Unchanged.** Precipitation handling stays as decided by the 2026-11-12 amendment (no precip reference yet; IMERG/CHIRPS remain Tier 2 candidate secondary references). No threshold, split, percentile or testing rule changes here.

### 2026-11-14 — Scoring rules: ensemble members, climatology window, persistence, minimum sample, lead days, SMN product precedence

Appended after the preceding amendments; the original thresholds above are untouched — **X = 60 %, the 400-day splits, the 90th/95th percentiles, the 1000-resample bootstrap, the 15-issue-date gate (earliest 2026-11-25) and the reporting rules remain frozen**. Recorded 2026-11-14 (UTC), project-owner decision. These six rules were fixed while the archive held **4 distinct issue dates, with no skill number computed, printed, logged or written on real data** (the gate guard reported `4 distinct issue dates archived; 15 required by the 15-issue-date gate` and computed nothing).

1. **Ensemble members.** A member value is used when its quality_flag is ok. A case (station, variable, model, issue date, lead day) is scored only if at least 80% of that model's nominal member count is present; otherwise it is recorded as missing.
2. **Climatology window.** The +/-15-day window uses circular day-of-year distance (late December and early January are neighbours); 29 February is treated as 28 February.
3. **Persistence.** The SMN observation of the last completed local calendar day strictly before the local date of issue_time (America/Argentina/Buenos_Aires). If that observation is missing, persistence is n/a for that case; no further look-back.
4. **Minimum sample.** Every cell is reported with its n. A cell with fewer than 10 matured forecast-observation pairs is flagged "insufficient" and excluded from skill scores, aggregates and the station count of the hypothesis test.
5. **Lead days.** A lead day is evaluated only on matured pairs; the same n >= 10 rule applies. Nothing is extrapolated or pooled across lead days to reach the minimum.
6. **SMN products for the same station-day.** The latest archived regtemp snapshot is the primary series (the frozen climatology adjustment was estimated on regtemp); `observaciones` fills only days not yet covered by any archived regtemp snapshot. When both exist and differ, regtemp is used and the number and size of the differences are reported in the output.

**Interactions with the text above (stated so nothing is silently edited):** rule 2 fixes how the distance of §4 item 2's ±15-day calendar window is measured, not its width; rule 3 anchors §4 item 3's "last observed value carried forward" to a specific day and leaves its `n/a` beyond 3 days unchanged; rule 6 selects between the two SMN products that both live under the `observations/smn/` temperature reference of the 2026-11-13 amendment. No threshold, split, percentile or testing rule changes here.