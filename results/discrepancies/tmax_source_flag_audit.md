# GHCN TMAX source/quality flag audit

Generated 2026-11-13 19:12:35 (UTC) by `scripts/ghcn_tmax_source_flag_audit.py` from the raw `.dly` files in `data/cache/ghcn/` (19 stations, TMAX only, years 1996–2025; a blank flag column is shown as `(blank)`). The cache is gitignored and is read, never re-fetched, by this script.

Diagnostic table, not a skill metric: no CRPS/Brier/reliability number exists before the 15-issue-date gate (`docs/EVALUATION_PROTOCOL.md`). Counts and biases below describe what the files carry; they assert no cause.

## TMAX values by source flag and period

| period | source_flag | n | share_pct |
| --- | --- | --- | --- |
| 1996-2003 | G | 30950 | 73.9 |
| 2004 | G | 1530 | 39.2 |
| 2004 | S | 2371 | 60.8 |
| 2005-2025 | S | 67569 | 100.0 |
| 1996-2003 | I | 51 | 0.1 |
| 1996-2003 | S | 10882 | 26.0 |

## TMAX values by quality flag and period

| period | quality_flag | n |
| --- | --- | --- |
| 1996-2003 | (blank) | 41880 |
| 2004 | (blank) | 3901 |
| 2005-2025 | (blank) | 67568 |
| 1996-2003 | I | 1 |
| 2005-2025 | I | 1 |
| 1996-2003 | G | 2 |

## Per-year source-flag composition (all stations)

| year | G | I | S |
| --- | --- | --- | --- |
| 1996 | 3959 | 0 | 1311 |
| 1997 | 4015 | 0 | 1355 |
| 1998 | 3983 | 0 | 1320 |
| 1999 | 3906 | 0 | 1284 |
| 2000 | 4025 | 0 | 1355 |
| 2001 | 3609 | 10 | 1475 |
| 2002 | 3687 | 4 | 1421 |
| 2003 | 3766 | 37 | 1361 |
| 2004 | 1530 | 0 | 2371 |
| 2005 | 0 | 0 | 3048 |
| 2006 | 0 | 0 | 3154 |
| 2007 | 0 | 0 | 3183 |
| 2008 | 0 | 0 | 2951 |
| 2009 | 0 | 0 | 2684 |
| 2010 | 0 | 0 | 3029 |
| 2011 | 0 | 0 | 3323 |
| 2012 | 0 | 0 | 3454 |
| 2013 | 0 | 0 | 3127 |
| 2014 | 0 | 0 | 3287 |
| 2015 | 0 | 0 | 3660 |
| 2016 | 0 | 0 | 3581 |
| 2017 | 0 | 0 | 3559 |
| 2018 | 0 | 0 | 3331 |
| 2019 | 0 | 0 | 3291 |
| 2020 | 0 | 0 | 3345 |
| 2021 | 0 | 0 | 3377 |
| 2022 | 0 | 0 | 3362 |
| 2023 | 0 | 0 | 3393 |
| 2024 | 0 | 0 | 3268 |
| 2025 | 0 | 0 | 2162 |

## ERA5−GHCN t2m_max bias by source flag

Paired local-calendar days, both sides `quality_flag ok` (the same pairing as the discrepancy report); positive = ERA5 warmer.

| period | source_flag | n_pairs | mean_bias_C |
| --- | --- | --- | --- |
| all years | G | 32477 | -1.38 |
| all years | I | 51 | -3.95 |
| all years | S | 80821 | -3.45 |
| 1996-2003 | G | 30947 | -1.37 |
| 1996-2003 | I | 51 | -3.95 |
| 2004 | G | 1530 | -1.49 |
| 2005-2025 | S | 67568 | -3.45 |
| 2004 | S | 2371 | -3.48 |
| 1996-2003 | S | 10882 | -3.40 |

## Coverage context (paired station-days, mean per station)

| year | mean n_days |
| --- | --- |
| 1996 | 277.4 |
| 1997 | 282.6 |
| 1998 | 279.1 |
| 1999 | 273.2 |
| 2000 | 283.1 |
| 2001 | 283.0 |
| 2002 | 269.1 |
| 2003 | 271.8 |
| 2004 | 205.3 |
| 2005 | 169.3 |
| 2006 | 175.2 |
| 2007 | 176.8 |
| 2008 | 163.9 |
| 2009 | 149.1 |
| 2010 | 168.3 |
| 2011 | 174.9 |
| 2012 | 181.8 |
| 2013 | 183.9 |
| 2014 | 182.6 |
| 2015 | 192.6 |
| 2016 | 188.5 |
| 2017 | 187.3 |
| 2018 | 175.3 |
| 2019 | 173.2 |
| 2020 | 176.1 |
| 2021 | 177.7 |
| 2022 | 176.9 |
| 2023 | 178.6 |
| 2024 | 172.0 |
| 2025 | 113.8 |

## Reading: does the 2003→2005 step coincide with a source-flag change?

Source-flag share of TMAX values, 1996–2003 vs 2005–2025: G 73.9% -> 0.0%; I 0.1% -> 0.0%; S 26.0% -> 100.0%.

Shares moved by >= 1.0 point: G, S. The composition change and the bias/coverage step occur at the same time in these tables, and the per-period bias rows above show what each flag's own bias is on either side of the step.

Temporal coincidence in a table is not a cause: nothing here claims why the bias moved. The discriminating candidates stay the ones listed in `bias_reattribution.md`, none asserted.
