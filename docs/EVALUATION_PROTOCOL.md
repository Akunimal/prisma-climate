
## Amendments

### 2026-11-11 — Archive maturity gate and hindcast labelling

Appended (original thresholds above unchanged; **X = 60 % remains frozen**):

1. **No leaderboard or skill numbers** (CRPS, CRPSS, Brier, BSS, reliability, coverage) may be published in `results/` until the daily forecast archive holds **at least 15 distinct issue dates**. Until then only code and unit tests may land; sample-size honesty applies even after day 15.
2. If a **historical-forecast API** is ever used to build a hindcast (forecasts not issued on that calendar day by our archive), every table, figure and docs mention must label the numbers **`hindcast`** explicitly, with the provider and retrieval date. Operational archive scores and hindcast scores are never mixed in one series without that label.
3. Climatology and persistence baselines are scored only on days that also have an archived forecast issue; no baseline is scored against reanalysis-only pseudo-forecasts.
