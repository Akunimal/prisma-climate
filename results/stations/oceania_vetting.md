# Station cross-check — Oceania & Pacific config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/oceania/audit.json` on 2026-11-19T10:42:26.776146+00:00.

- Configured stations: 16; Retained: 16; Removed: 0; Auto-resolved: 0
- Dual-source confirmation: 16/16 (100.0%)
- Active 72h telemetry: 16/16 (100.0%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sydney Kingsford Smith | `YSSY` | `n/a` | Sydney Intl | SYDNEY INTL | -33.946 | 151.177 | -33.946 | 151.173 | 0.369 | 6.0 | 3.0 | 3.0 | 136 | 45.33 | 11.11% | PASS | `retain_unchanged` |
| Melbourne Tullamarine | `YMML` | `n/a` | Melbourne Intl | MELBOURNE INTL | -37.673 | 144.843 | -37.666 | 144.832 | 1.242 | 132.0 | 115.0 | 17.0 | 136 | 45.33 | 11.11% | PASS | `retain_unchanged` |
| Brisbane Airport | `YBBN` | `n/a` | Brisbane Intl | BRISBANE AIRPORT | -27.384 | 153.118 | -27.391 | 153.130 | 1.418 | 4.0 | 3.0 | 1.0 | 128 | 42.67 | 11.11% | PASS | `retain_unchanged` |
| Perth Airport | `YPPH` | `n/a` | Perth Intl | PERTH INTL | -31.94 | 115.967 | -31.927 | 115.976 | 1.677 | 20.0 | 16.0 | 4.0 | 130 | 43.33 | 12.5% | PASS | `retain_unchanged` |
| Adelaide Airport | `YPAD` | `n/a` | Adelaide Intl | ADELAIDE INTL | -34.945 | 138.531 | -34.952 | 138.520 | 1.269 | 6.0 | 2.0 | 4.0 | 135 | 45.0 | 12.5% | PASS | `retain_unchanged` |
| Darwin International | `YPDN` | `n/a` | Darwin Intl | DARWIN INTL | -12.415 | 130.877 | -12.424 | 130.893 | 2.005 | 31.0 | 32.0 | -1.0 | 135 | 45.0 | 12.5% | PASS | `retain_unchanged` |
| Alice Springs Airport | `YBAS` | `n/a` | Alice Springs Arpt | ALICE SPRINGS | -23.807 | 133.902 | -23.795 | 133.889 | 1.879 | 545.0 | 549.0 | -4.0 | 143 | 47.67 | 12.5% | PASS | `retain_unchanged` |
| Hobart Airport | `YMHB` | `n/a` | Hobart Intl | HOBART | -42.836 | 147.51 | -42.834 | 147.503 | 0.613 | 4.0 | 2.0 | 2.0 | 126 | 42.0 | 12.5% | PASS | `retain_unchanged` |
| Cairns Airport | `YBCS` | `n/a` | Cairns Intl | CAIRNS INTL | -16.886 | 145.755 | -16.874 | 145.745 | 1.707 | 3.0 | 2.0 | 1.0 | 131 | 43.67 | 12.5% | PASS | `retain_unchanged` |
| Auckland Airport | `NZAA` | `n/a` | Auckland Intl | AUCKLAND INTL | -37.008 | 174.792 | -37.008 | 174.792 | 0.000 | 7.0 | 7.0 | 0.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Christchurch International | `NZCH` | `n/a` | Christchurch Intl | CHRISTCHURCH INTL | -43.489 | 172.532 | -43.489 | 172.528 | 0.323 | 37.0 | 36.0 | 1.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Wellington International | `NZWN` | `n/a` | Wellington Intl | WELLINGTON INTL | -41.327 | 174.805 | -41.331 | 174.806 | 0.453 | 13.0 | 12.0 | 1.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Nadi International | `NFFN` | `n/a` | Nadi Intl | NADI INTL | -17.755 | 177.443 | -17.755 | 177.443 | 0.000 | 18.0 | 14.0 | 4.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Port Moresby Jacksons International | `AYPY` | `n/a` | Port Moresby Intl | PORT MORESBY JACKSONS INTL | -9.444 | 147.22 | -9.443 | 147.216 | 0.453 | 38.0 | 44.0 | -6.0 | 4 | 1.33 | 95.83% | PASS | `retain_unchanged` |
| Honolulu Daniel K. Inouye International | `PHNL` | `n/a` | Honolulu Intl | HONOLULU INTERNATIONAL AIRPORT | 21.319 | -157.922 | 21.315 | -157.924 | 0.486 | 4.0 | 2.0 | 2.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Tahiti Faa'a International | `NTAA` | `n/a` | Tahiti Island/Faaa Intl | TAHITI FAA A | -17.554 | -149.607 | -17.554 | -149.607 | 0.000 | 2.0 | 2.0 | 0.0 | 144 | 48.0 | 0.0% | PASS | `retain_unchanged` |

## Flags and Removals

No stations exceeded the 5.0 km / 50 m thresholds or failed telemetry.
