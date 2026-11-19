# Station cross-check — Africa config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/africa/audit.json` on 2026-11-19T10:42:26.615637+00:00.

- Configured stations: 17; Retained: 14; Removed: 3; Auto-resolved: 0
- Dual-source confirmation: 15/17 (88.2%)
- Active 72h telemetry: 15/17 (88.2%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Cairo International | `HECA` | `n/a` | Cairo Intl | CAIRO INTL | 30.122 | 31.406 | 30.133 | 31.405 | 1.227 | 116.0 | 142.0 | -26.0 | 132 | 44.0 | 8.33% | PASS | `retain_unchanged` |
| Casablanca Mohammed V International | `GMMN` | `n/a` | Casablanca Intl | MOHAMMED V | 33.367 | -7.59 | 33.367 | -7.590 | 0.000 | 200.0 | 196.0 | 4.0 | 137 | 45.67 | 8.33% | PASS | `retain_unchanged` |
| Dakar Blaise Diagne International | `GOBD` | `n/a` | Dakar/Diagne Intl | n/a | 14.671 | -17.073 | 14.671 | -17.067 | 0.645 | 88.0 | 90.0 | -2.0 | 131 | 43.67 | 8.33% | FAIL | `remove` |
| Lagos Murtala Muhammed | `DNMM` | `n/a` | Lagos/Muhammed Intl | MURTALA MUHAMMED | 6.577 | 3.321 | 6.577 | 3.321 | 0.000 | 41.0 | 27.0 | 14.0 | 63 | 21.0 | 13.89% | PASS | `retain_unchanged` |
| Accra Kotoka International | `DGAA` | `n/a` | Accra/Kotoka Intl | KOTOKA INTL | 5.605 | -0.167 | 5.600 | -0.170 | 0.648 | 62.0 | 68.0 | -6.0 | 66 | 22.0 | 8.33% | PASS | `retain_unchanged` |
| Nairobi Jomo Kenyatta International | `HKJK` | `n/a` | Nairobi/Kenyatta Intl | JKIA / NAIROBI JOMO KENYATTA INTL | -1.319 | 36.928 | -1.319 | 36.928 | 0.000 | 1624.0 | 1615.0 | 9.0 | 127 | 42.33 | 0.0% | PASS | `retain_unchanged` |
| Addis Ababa Bole International | `HAAB` | `n/a` | Addis Ababa/Bole Intl | BOLE INTL | 8.978 | 38.799 | 8.978 | 38.799 | 0.000 | 2334.0 | 2319.0 | 15.0 | 83 | 27.67 | 12.5% | PASS | `retain_unchanged` |
| Dar es Salaam Julius Nyerere | `HTDA` | `n/a` | Dar Es Salaam Arpt | MWALIMU JULIUS K NYERERE INTL | -6.878 | 39.203 | -6.881 | 39.201 | 0.400 | 55.0 | 53.0 | 2.0 | 135 | 45.0 | 1.39% | PASS | `retain_unchanged` |
| Johannesburg O. R. Tambo | `FAOR` | `n/a` | Johannesburg/Tambo Intl | JOHANNESBURG INTL | -26.139 | 28.246 | -26.139 | 28.246 | 0.000 | 1694.0 | 1684.0 | 10.0 | 121 | 40.33 | 4.17% | PASS | `retain_unchanged` |
| Cape Town International | `FACT` | `n/a` | Capetown Intl | CAPE TOWN INTL | -33.965 | 18.602 | -33.965 | 18.602 | 0.000 | 46.0 | 48.0 | -2.0 | 87 | 29.0 | 0.0% | PASS | `retain_unchanged` |
| Antananarivo Ivato International | `FMMI` | `n/a` | Antananarivo/Ivato Intl | IVATO | -18.797 | 47.479 | -18.797 | 47.479 | 0.000 | 1279.0 | 1269.0 | 10.0 | 153 | 51.0 | 0.0% | PASS | `retain_unchanged` |
| Mauritius Sir Seewoosagur Ramgoolam | `FIMP` | `n/a` | Mauritius Intl | SIR SEEWOOSAGUR RAMGOOLAM INTL | -20.43 | 57.684 | -20.434 | 57.684 | 0.445 | 57.0 | 57.0 | 0.0 | 73 | 24.33 | 0.0% | PASS | `retain_unchanged` |
| Kinshasa N'djili International | `FZAA` | `n/a` | Kinshasa/NDjili Arpt | NDJILI INTL | -4.386 | 15.445 | -4.387 | 15.448 | 0.351 | 313.0 | 309.0 | 4.0 | 0 | 0.0 | 100.0% | FAIL | `remove` |
| Khartoum International | `HSSS` | `n/a` | Khartoum Intl | n/a | 15.59 | 32.553 | 15.589 | 32.553 | 0.111 | 386.0 | 387.0 | -1.0 | 0 | 0.0 | 100.0% | FAIL | `remove` |
| Tunis Carthage International | `DTTA` | `n/a` | Tunis/Carthage Intl | CARTHAGE | 36.851 | 10.227 | 36.851 | 10.227 | 0.000 | 7.0 | 4.0 | 3.0 | 144 | 48.0 | 0.0% | PASS | `retain_unchanged` |
| Algiers Houari Boumediene | `DAAG` | `n/a` | Algiers Intl | HOUARI BOUMEDIENE | 36.691 | 3.215 | 36.691 | 3.215 | 0.000 | 25.0 | 18.0 | 7.0 | 144 | 48.0 | 0.0% | PASS | `retain_unchanged` |
| Niamey Diori Hamani International | `DRRN` | `n/a` | Niamey/Hamani Intl | DIORI HAMANI | 13.482 | 2.184 | 13.483 | 2.170 | 1.518 | 223.0 | 223.0 | 0.0 | 67 | 22.33 | 6.94% | PASS | `retain_unchanged` |

## Flags and Removals

- **`GOBD` (Dakar Blaise Diagne International)**: status `FAIL`, action `remove`. Distance delta: 0.645 km. Elev delta: -2.0 m. 72h observations: 131.
- **`FZAA` (Kinshasa N'djili International)**: status `FAIL`, action `remove`. Distance delta: 0.351 km. Elev delta: 4.0 m. 72h observations: 0.
- **`HSSS` (Khartoum International)**: status `FAIL`, action `remove`. Distance delta: 0.111 km. Elev delta: -1.0 m. 72h observations: 0.
