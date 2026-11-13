# Archive issue-hour distribution

Generated 2026-11-13 20:03:20 UTC by `scripts/issue_hour_distribution.py` from the canonical archive parquets (file paths are relative to the archive root).
Values in `results/` come only from this script. **Sample metadata only** - no CRPS, Brier or reliability is computed here.
Bands are the UTC strata of protocol section 3.2.2 (`docs/EVALUATION_PROTOCOL.md`).

## Per issue date

| issue_date | issue_time (UTC) | hour | band | rows | file |
|---|---|---|---|---:|---|
| 2026-11-11 | 2026-11-11 16:27:24 | 16 | 12:00-23:59 | 74784 | `2026-11-11/openmeteo-ensemble_2026-11-11.parquet` |
| 2026-11-12 | 2026-11-12 08:31:23 | 08 | 00:00-11:59 | 74784 | `2026-11-12/openmeteo-ensemble_2026-11-12.parquet` |
| 2026-11-13 | 2026-11-13 16:24:08 | 16 | 12:00-23:59 | 74784 | `2026-11-13/openmeteo-ensemble_2026-11-13.parquet` |

## Counts per band

| band | issue dates |
|---|---:|
| 00:00-11:59 | 1 |
| 12:00-23:59 | 2 |
| **total** | **3** |
