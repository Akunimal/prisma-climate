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

### 2026-11-15 — Hindcast evaluation for the Phase 2 CRPSS gate

Appended after the preceding amendments; the original thresholds above are untouched — **X = 60 %, the 400-day operational splits, the 90th/95th percentiles, the 1000-resample bootstrap, the 15-issue-date gate (earliest 2026-11-25) and the reporting rules remain frozen**. Drafted 2026-11-15, approved by the project owner 2026-11-16 (UTC). This amendment specifies how the Phase 2 exit gate (“CRPSS > 0 of calibrated vs raw ensemble”) is tested on a **hindcast** while the operational archive cannot yet hold a fitting window (§3.1).

**0. Disclosure (required).** Two sets of real-data numbers and the diagnosis below were seen **before** this amendment was drafted; no threshold, split or method was changed because of them.

- **Smoke (not the gate).** mode `smoke`, window 2026-05-12 → 2026-05-31, `n_train = 10`, `n_eval = 10`, lead day 1 only, 19 stations, `t2m_max`, mean CRPSS EMOS vs raw **−0.0774**, mean CRPSS QM vs raw **+0.0002** (artifacts `results/hindcast/crpss_smoke_20261115T111706Z.*`, label `hindcast`). Not published as skill.
- **Full run — Run A (§5).** mode `full`, label `hindcast`, artifact `results/hindcast/crpss_full_20261115T201137Z.csv`: **95** station × lead cells, chronological split **180 train / 185 eval** issue dates (§4), leads 1, 3, 7, 10, 15, mean CRPSS EMOS vs raw **−0.0744**, mean CRPSS QM vs raw **+0.0838**.
- **Diagnosis (also seen before this amendment).** Performed after those numbers and before drafting, by synthetic unit cases and by month-by-month breakdown of the same run (scripts under `results/hindcast/diagnostics/`, uncommitted): (i) **variance-link defect of the two-stage OLS EMOS** — on a synthetic spread-skill case the fitted σ is ≈ 2.8× the residual spread, and on a synthetic regime-flip case the variance link collapses to the numerical floor (`c = 0.001`, `d = 0`) with evaluation CRPSS ≈ −1.68; on real data the fitted σ sits 1.1–1.6× the residual spread; (ii) **seasonal extrapolation of the chronological split** — training ends 2026-05-09, so austral winter appears only in eval; the cell-mean slope `b̄ = 0.772 < 1` over-corrects there, with eval mean μ error may/jun/jul = **+2.07 / +2.52 / +1.99 K** (sign inverted) and cell-mean monthly CRPSS exactly there (may **−0.21**, jun **−0.31**, jul **−0.20**, ago **−0.04**) against sep **+0.05**, oct **−0.09**, nov **+0.32**; (iii) **one-day offset and single 6-hour window of the forecast side** — for lead L the pre-amendment code read the **first `TMAX` record of file `f{24L}`** (label `(24L−6, 24L) hour max fcst` in the observed `.idx` files), i.e. the UTC interval `[18Z (t+L−1), 00Z (t+L))` = local **15:00–21:00 of day `t+L−1`**, and joined it to the observation local day **`t+L`** (evidence: `.idx` records for issue 2026-05-12, `f024` → `18-24 hour max fcst`, `f360` → `354-360 hour max fcst`); the value therefore verifies the previous local day and covers only one 6-hour window, which can miss the daily maximum when the local peak occurs before 15:00). Disclosed as seen before this amendment; **Run A stays frozen as published** with its numbers and this defect reported beside them; the corrected rule is §2b and is used by Run B only — no corrected Run A numbers are computed. Run A's negative global mean is attributable in part to defects (i), (ii) and (iii); their separate contributions are not quantified, because no corrected Run A numbers are computed.

**1. Data (forecast side).** NOAA GEFS on AWS Open Data (`noaa-gefs-pds`), cycle **00Z** only, members **31** (`gec00` + `gep01`…`gep30`), GRIB `TMAX`/`TMIN` at `heightAboveGround` 2 m, grid 1.0°, access via `.idx` + HTTP Range (design: `docs/design/HINDCAST.md`). Provider string: `NOAA GEFS (noaa-gefs-pds)`. Every artifact carries label **`hindcast`**, provider and `retrieved_at` (2026-11-11 amendment).

**2. Observation reference.** Station daily **SMN Argentina** `t2m_max` (and `t2m_min` if scored), local calendar day, from the regtemp capture under the **2026-11-13** temperature-reference amendment (regtemp primary / `observaciones` fill per 2026-11-14 rule 6). **Not** GHCN-Daily and **not** raw ERA5 as truth. Valid time = issue 00Z + lead day, mapped to America/Argentina/Buenos_Aires for the join. The forecast-side pairing is defined by **§2b**; its remaining limitation (local 21:00–03:00 not covered for `t2m_max`; only 03:00–15:00 for `t2m_min`) is stated there, not assumed away.

**2b. Lead → local-day mapping (exact rule as implemented; Run B uses it).** Issue = GEFS cycle **00Z** on UTC date `t` (that instant is 21:00 local on `t − 1`, America/Argentina/Buenos_Aires, UTC−3). For lead L the verifying **local day is V = t + L**, which in UTC spans **`[03Z V, 03Z V+1)`**. Per member, the forecast values for V are combined from the NCEP period-max/min messages as follows (this corrects §0 defect (iii); the pre-amendment single-message rule is what Run A used and Run A stays frozen — no corrected Run A numbers are computed):

- **`t2m_max` = max over the three 6-hour TMAX messages of day V that lie fully inside the local day**: idx labels `(24L+6, 24L+12)`, `(24L+12, 24L+18)`, `(24L+18, 24L+24)` `hour max fcst`, read from files `f{24L+12}`, `f{24L+18}`, `f{24L+24}` respectively (a message lives in the file of its label's end hour). UTC intervals `[06Z V, 12Z V)`, `[12Z V, 18Z V)`, `[18Z V, 24Z V)` = local **03:00–09:00, 09:00–15:00, 15:00–21:00 of V**.
- **`t2m_min` = min over the two earliest 6-hour TMIN messages of day V that lie fully inside the local day**: labels `(24L+6, 24L+12)`, `(24L+12, 24L+18)` `hour min fcst` from files `f{24L+12}`, `f{24L+18}` (local 03:00–09:00 and 09:00–15:00 of V — the local night/morning span available inside the day; the 18–24 UTC period, local 15:00–21:00, is not used for the minimum). `t2m_min` is **secondary** and cannot change the decision (§4); **Run B does not compute it** (§5).

Message selection is **by exact `.idx` label** — variable token, start/end hours and max/min kind must all match (`find_field_range_for_period`); the period is never inferred from the file's forecast hour alone, and a 3-hour label is never substituted for a required 6-hour one (GEFS v12 ships both: 6-hour labels at forecast hours ≡ 0 or 6 mod 12, 3-hour labels at ≡ 3 or 9 mod 12; only the 6-hour series tiles the day and is used). A missing or mismatched label, an undecodable slice or a missing file fails the **whole member slot** for that lead (no value), never a fallback period. The 6-hour periods that straddle a local-day boundary — `[00Z V, 06Z V)` and `[00Z V+1, 06Z V+1)` — are **excluded**, because they are not fully inside `[03Z V, 03Z V+1)`. Consequently this rule covers local **03:00–21:00 of V** for `t2m_max` and **03:00–15:00 of V** for `t2m_min`; local **00:00–03:00 and 21:00–24:00 of V are uncovered** by construction — a stated limitation of the rule, not an assumption of completeness. The combined values are joined to SMN on local calendar day **V = t + L** (`valid = issue_date + timedelta(days=lead)` in `run_crpss`, unchanged — only the forecast messages change). Cache rows written with this mapping carry `rule = localday-3p-v1`; the cache keeps the pre-amendment rows for Run A reproduction. The issue label stays the UTC date of the 00Z cycle, not its local date.

**3. Stations.** The **19** region stations in `configs/regions/argentina.yaml`, resolved to SMN via catalogue NRO.

**4. Split (held out).** Inside the 365-day regtemp window **2025-11-11 → 2026-11-10**: **train = the first 180 issue dates (2025-11-11 → 2026-05-09)**, **eval = the remaining 185 issue dates (2026-05-10 → 2026-11-10)**; 180 + 185 = 365, strictly ordered, no overlap. (Corrects the earlier “180 + 180” phrasing; `docs/design/HINDCAST.md` §7 has been corrected to match, same amendment round.) Leads for the gate run: **1, 3, 7, 10, 15** (subset of protocol leads). Member rule: ≥ 80 % of 31 (2026-11-14 rule 1). Primary target: **`t2m_max` only** (precip arm suspended, 2026-11-12); `t2m_min`, if computed, is **secondary** and cannot change the decision (owner decision 2026-11-15). `MIN_SAMPLE = 10` per cell (2026-11-14 rules 4–5) unchanged. A full 400+400 window is the protocol ideal once a longer observation capture exists; **180+185 is the sample used here and is labelled as such**.

**5. Fitting — two runs, both published.** EMOS and empirical quantile mapping are fitted **only on observations available before each scored issue date**; information from the scored date or later is never used to fit (§3, §8 ablation on train only). Two runs are pre-specified. Both are computed **once**, both are **published together with equal prominence**, and **neither design may be changed after its numbers are seen**:

- **Run A — chronological split, two-stage EMOS (already run; numbers and diagnosis in §0).** One fit per station × lead on the §4 train slice (180 issue dates); EMOS Gaussian with the **two-stage OLS** variance link; QM on ens_mean of the same slice; scored on the §4 eval slice (185 issue dates). Produced with the repository code **as of commit `f601a66`** (its artifacts are frozen as published; `results/hindcast/diagnostics/diagnose_emos.py` reproduces the published numbers from the current tree by fitting `fit_emos_two_stage` explicitly — reconcile max_abs_diff = 0.0 on all three CRPS columns, 95 cells). Its defect is reported with its numbers.
- **Run B — corrected EMOS fit + rolling window (specified here; run once after this amendment is approved).** Same cache, same stations, leads and member rule. **Run B computes `t2m_max` only: `t2m_min` (secondary) is not computed in this run** (the §2b rule covers it if ever needed, but no TMIN messages are fetched or scored for Run B). For **each issue date D and lead L separately**, EMOS **and** QM are fitted on the **45 most recent issue dates** whose verifying local day ended at least one full day before D: a training issue date `t` contributes iff **`t + L + 2 ≤ D`** in the local calendar — the cycle on D is 00Z, i.e. 21:00 local on D−1, so local day D−1 has not ended at issue time and the verifying local day `t + L` must end at least one full day before D. The window length **45** is fixed by this amendment and is **not tuned**; fewer dates are used only when the available history is shorter. A date with fewer than **MIN_SAMPLE = 10** usable training pairs is **not fitted and not scored — never silently scored as raw**; cells keep the MIN_SAMPLE = 10 rule on scored eval dates (“insufficient”, excluded from aggregates). EMOS variant: the **corrected joint fit** `N(a + b·ens_mean, c + d·ens_var)` with `c ≥ 0` (numerical floor), `d ≥ 0`, all four parameters minimising mean CRPS jointly (Gneiting et al. 2005), replacing the defective two-stage variance link. Because every Run B fit uses only strictly earlier dates, each of its scored dates is out-of-sample by construction; Run B therefore scores every issue date that clears the rules above (its eval set is that set of dates, not the fixed §4 slice — a stated asymmetry with Run A).

**ENSO scope.** The §2 hypothesis names an ENSO-conditioned calibration. This sample spans **one year, i.e. one ENSO phase per season**, so the ENSO-conditioned clause is **untestable here** — it can be neither confirmed nor falsified. Both runs are fitted **without any ENSO predictor**, and the ENSO hypothesis stays **open** until a multi-year sample exists. Only the unconditioned “calibrated vs raw ensemble” clause of the Phase 2 gate is decided by this hindcast.

**6. Baselines, metrics and decision rule.** The Phase 2 gate comparison is **calibrated vs raw ensemble** (fair CRPS / CRPSS), matching the ROADMAP exit-gate wording. Climatology and persistence (§4) remain required for the **operational** Phase 1 leaderboard; they are **not** redefined by this amendment and are not mixed into the hindcast CRPSS series. Binary-event and reliability metrics (§5) are out of scope for this hindcast gate run.

*Decision rule for X = 60 %, fixed before Run B exists.* The **primary method is corrected EMOS on Run B**; QM is reported beside it with the same per-station statistics as a **secondary** method and **cannot change the decision** (owner decision 2026-11-15, taken after Run A, where EMOS was the *worse* of the two methods — −0.0744 vs +0.0838 — so the choice does not favour a passing result). The primary variable is **`t2m_max` only** (`t2m_min`, if computed, is secondary and cannot change the decision). Per station, pool every sufficient (lead × eval-date) CRPS pair of the run: **station CRPSS = 1 − mean(CRPS_calibrated) / mean(CRPS_raw)** over all pooled pairs — leads are combined by pooling the pairs (each pair equal weight) and the ratio is taken **after** aggregating CRPS, never as a mean of cell ratios. A station **counts as improved** iff its per-station CRPSS > 0 **and** the 95 % interval of the pooled CRPS difference (calibrated − raw) from a **moving-block bootstrap over issue dates — block length 7 issue dates, 1000 resamples, 95 % interval** — excludes zero in the improving direction. Consecutive issue dates stay together inside a block, because temperature errors are serially correlated day to day, and all leads of a date move together (the protocol §6 1000-resample paired bootstrap, applied with blocks at station level). The hypothesis holds iff **X = 60 % or more** of the stations **with at least one sufficient cell** count as improved; stations with no sufficient cell leave the denominator. The **cell-mean** CRPSS over sufficient cells is a **secondary descriptive** statistic and cannot change the decision. The decision is taken on **Run B**; Run A is published beside it with its defect explained (§0, §5). If Run B fails, the hypothesis fails and that failure is reported (§2), not re-thresholded and not re-run.

**7. Labelling.** Every table, figure, docs mention and `skill.json` field for these numbers says **`hindcast`** with provider and retrieval date. Operational-archive scores and hindcast scores are never mixed in one series (2026-11-11). The **15-issue-date gate still binds the operational leaderboard**; this amendment does not open it. `operational_leaderboard_published` stays `false` until that gate opens on its own terms.

**8. Relation to the live-archive gate.** The 15-date gate (earliest 2026-11-25) continues to govern **raw-ensemble verification and the three baselines** on the operational archive. The **X = 60 % calibrated-vs-raw hypothesis** may be tested on this hindcast under this amendment (as §3.1 already allowed). Passing or failing the Phase 2 CRPSS gate on the hindcast does **not** publish operational skill numbers.

**9. Publication.** Full-run artifacts land in `results/hindcast/` with input sha256 recorded in the run metadata. Run A and Run B artifacts are published **together**, each carrying its run identity (`training: chronological-180` / `training: rolling-45`) in the metadata. `data/skill.json` may expose hindcast-labelled means and cells only with `label: hindcast` and the closed operational gate block; negative means are shown with equal prominence (§7). Smoke numbers remain non-gate, non-published as skill.

**10. Unchanged.** X = 60 %, 400-day operational splits, percentiles, bootstrap, 15-date gate, reporting rules: **frozen**. No threshold moved after seeing smoke or full-run results; Run B's design was fixed in this text before any of its numbers existed.
