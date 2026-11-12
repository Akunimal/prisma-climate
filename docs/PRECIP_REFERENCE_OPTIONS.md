# Precipitation reference options for the Phase 1 hypothesis — open memo

Status: **analysis only, no decision.** Written 2026-11-12. The choice among
options (a)–(c) below is the user's, and must be recorded in
`docs/EVALUATION_PROTOCOL.md` **before any skill numbers are seen**. This memo
does not change **X = 60%** and does not change the 15-issue-date gate.

## The problem

The Phase 1 falsifiable hypothesis covers **daily precipitation** as well as
`t2m_max`. Verification needs a fresh observational reference for precip on the
same days as the archived forecasts. Today:

| Source | Role | Limitation |
|---|---|---|
| SMN Argentina open data | intended local station truth | **no precipitation field** in any open payload (probed 2026-11-11; see `docs/DATA_SOURCES.md`) |
| NOAA GHCN-Daily `PRCP` | primary station precip in Phase 0 | **stale at source**: last ok observation 2025-08-24 (444 days as of the 2026-11-11 QC audit, `results/qc/freshness.md`) |
| Open-Meteo ERA5 | reanalysis / climatology | **not station truth**; grid-cell values, not a rain gauge |

So the precip arm currently has **no fresh observational reference** for
issue dates from 2026-11-11 onward. Temperature has SMN `t2m_max`/`t2m_min`
accumulating forward; precip does not.

## Option (a) — satellite precip proxy (IMERG / CHIRPS)

- **What they are:** satellite-based (IMERG: GPM multi-satellite + gauge blend
  where available; CHIRPS: satellite IR + station gauge merge over land).
  Registered as Tier 2 planned sources in `configs/sources.yaml`.
- **Latency (order of magnitude, to confirm at §3.8 verification):** IMERG
  near-real-time products are typically hours to ~a day; CHIRPS daily is
  typically days to weeks behind. Exact lag must be verified before any
  connector is written — this memo does not assert a number as final.
- **Licence:** IMERG/NASA GPM data are generally open with attribution;
  CHIRPS is free for research/use with attribution (Climate Hazards Center).
  **Both must pass the project's §3.8 access + licence + redistribution check
  before `status: active`.**
- **What they are not:** they are **not station truth**. A satellite precip
  estimate over a grid cell is not a point gauge; treating it as ground truth
  would change what the hypothesis measures (forecast skill vs. a product,
  not vs. an observation). Using them as the *only* reference would need an
  explicit protocol amendment saying so.
- **Fit:** useful as a **spatial proxy** or secondary reference, especially
  where gauges are missing — not a drop-in replacement for the station arm.

## Option (b) — restrict the precip arm to the historical GHCN period

- **What it means:** score precip verification only on issue/observation dates
  where GHCN-Daily `PRCP` is still fresh (through 2025-08-24 in the current
  store), with every table and doc labelling those scores **`hindcast`** (or
  explicitly “historical GHCN period”), per the existing 2026-11-11 protocol
  amendment on hindcast labelling.
- **What it preserves:** station truth; no new source; X and the 15-date
  archive gate untouched for the *archive* maturity rule.
- **What it costs:** the operational archive from 2026-11-11 onward would
  **not** contribute precip skill numbers until a fresh precip reference
  exists; the live precip arm of the hypothesis stays unverified. Risk of
  mixing historical and operational periods if labels are dropped.
- **Fit:** honest short-term path if the goal is “publish something about
  precip now” without inventing a reference.

## Option (c) — document the limitation; precip arm not yet verifiable

- **What it means:** state in `EVALUATION_PROTOCOL.md` and reporting that the
  precip arm of the Phase 1 hypothesis **cannot be evaluated yet** for
  archived issue dates (no fresh station precip; SMN has none; GHCN stale;
  ERA5 reanalysis is not the verification target). Temperature arm proceeds
  under the same X and gate rules.
- **What it preserves:** zero risk of a false precip claim; no new
  dependencies; fully consistent with “results only from what ran.”
- **What it costs:** Phase 1 ships with a documented hole on one of the two
  hypothesis variables until (a) or a restored GHCN/SMN precip series lands.
- **Fit:** the conservative default if no decision is made before results are
  seen — and the only option that requires no new data contract.

## What this memo does not do

- Does **not** pick (a), (b), or (c).
- Does **not** change **X = 60%** (hypothesis threshold: share of stations
  where local calibration must beat the raw ensemble on CRPS at 90% nominal
  reliability).
- Does **not** change the **15 distinct issue dates** gate (earliest
  2026-11-25).
- Does **not** authorize any precip number in `results/` before the user
  records a choice in `docs/EVALUATION_PROTOCOL.md`.
