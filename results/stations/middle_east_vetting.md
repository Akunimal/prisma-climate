# Station cross-check — Middle East config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/middle_east/audit.json` on 2026-11-22T23:25:52.124262+00:00.

- Configured stations: 12; Retained: 12; Removed: 0; Auto-resolved: 0
- Dual-source confirmation: 12/12 (100.0%)
- Active 72h telemetry: 12/12 (100.0%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Dubai International | `OMDB` | `n/a` | Dubai Intl | DUBAI INTL | 25.253 | 55.364 | 25.254 | 55.366 | 0.230 | 19.0 | 5.0 | 14.0 | 143 | 47.67 | 0.0% | PASS | `retain_unchanged` |
| Doha Hamad International | `OTHH` | `n/a` | Doha/Hamad Intl | DOHA / HAMAD INTL | 25.273 | 51.608 | 25.273 | 51.609 | 0.101 | 4.0 | 3.0 | 1.0 | 71 | 23.67 | 1.39% | PASS | `retain_unchanged` |
| Riyadh King Khalid International | `OERK` | `n/a` | Riyadh/King Khaled Intl | KING KHALED INTL | 24.958 | 46.699 | 24.945 | 46.702 | 1.477 | 625.0 | 618.0 | 7.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Jeddah King Abdulaziz International | `OEJN` | `n/a` | Jeddah/King Abdulaziz Intl | KING ABDULAZIZ INTL | 21.679 | 39.157 | 21.685 | 39.166 | 1.145 | 15.0 | 8.0 | 7.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Bahrain International | `OBBI` | `n/a` | Bahrain Intl | BAHRAIN INTL | 26.271 | 50.634 | 26.271 | 50.634 | 0.000 | 2.0 | 6.0 | -4.0 | 138 | 46.0 | 0.0% | PASS | `retain_unchanged` |
| Muscat International | `OOMS` | `n/a` | Muscat/Seeb Intl | SEEB INTL / MUSCAT INTL | 23.593 | 58.284 | 23.595 | 58.298 | 1.444 | 15.0 | 8.0 | 7.0 | 70 | 23.33 | 2.78% | PASS | `retain_unchanged` |
| Amman Queen Alia International | `OJAI` | `n/a` | Amman/Alia Intl | QUEEN ALIA INTL | 31.723 | 35.993 | 31.723 | 35.993 | 0.000 | 730.0 | 723.0 | 7.0 | 59 | 19.67 | 18.06% | PASS | `retain_unchanged` |
| Tel Aviv Ben Gurion | `LLBG` | `n/a` | Tel Aviv/Ben Gurion Arpt | BEN GURION | 32.009 | 34.885 | 32.011 | 34.887 | 0.292 | 41.0 | 35.0 | 6.0 | 144 | 48.0 | 0.0% | PASS | `retain_unchanged` |
| Baghdad International | `ORBI` | `n/a` | Baghdad Intl | BAGHDAD INTL AIRPORT | 33.262 | 44.234 | 33.263 | 44.235 | 0.145 | 35.0 | 37.0 | -2.0 | 65 | 21.67 | 13.89% | PASS | `retain_unchanged` |
| Basra International | `ORMM` | `n/a` | Basrah Intl | BASRAH INTL | 30.549 | 47.662 | 30.549 | 47.662 | 0.000 | 3.0 | 2.0 | 1.0 | 61 | 20.33 | 15.28% | PASS | `retain_unchanged` |
| Damascus International | `OSDI` | `n/a` | Damascus Intl | DAMASCUS INTL | 33.415 | 36.514 | 33.411 | 36.516 | 0.482 | 616.0 | 614.0 | 2.0 | 65 | 21.67 | 9.72% | PASS | `retain_unchanged` |
| Erbil International | `ORER` | `n/a` | Erbil Intl | ERBIL INTL | 36.237 | 43.963 | 36.232 | 43.951 | 1.211 | 409.0 | 399.0 | 10.0 | 76 | 25.33 | 8.33% | PASS | `retain_unchanged` |

## Flags and Removals

No stations exceeded the 5.0 km / 50 m thresholds or failed telemetry.
