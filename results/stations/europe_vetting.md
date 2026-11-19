# Station cross-check — Europe config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/europe/audit.json` on 2026-11-19T10:42:21.974564+00:00.

- Configured stations: 18; Retained: 18; Removed: 0; Auto-resolved: 0
- Dual-source confirmation: 18/18 (100.0%)
- Active 72h telemetry: 18/18 (100.0%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| London Heathrow | `EGLL` | `n/a` | London/Heathrow Intl | LONDON HEATHROW | 51.47 | -0.454 | 51.477 | -0.461 | 0.917 | 25.0 | 26.0 | -1.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Paris Charles de Gaulle | `LFPG` | `n/a` | Paris/De Gaulle Arpt | CHARLES DE GAULLE | 49.009 | 2.547 | 49.015 | 2.534 | 1.159 | 119.0 | 107.0 | 12.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Frankfurt am Main | `EDDF` | `n/a` | Frankfurt/Main Arpt | FRANKFURT MAIN | 50.037 | 8.562 | 50.045 | 8.598 | 2.720 | 111.0 | 113.0 | -2.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Amsterdam Schiphol | `EHAM` | `n/a` | Amsterdam/Schiphol Arpt | SCHIPHOL | 52.31 | 4.768 | 52.315 | 4.790 | 1.596 | -3.0 | -2.0 | -1.0 | 132 | 44.0 | 8.33% | PASS | `retain_unchanged` |
| Madrid Barajas | `LEMD` | `n/a` | Madrid/Barajas Arpt | ADOLFO SUAREZ MADRID BARAJAS | 40.483 | -3.567 | 40.466 | -3.555 | 2.146 | 609.0 | 589.0 | 20.0 | 136 | 45.33 | 6.94% | PASS | `retain_unchanged` |
| Rome Leonardo da Vinci | `LIRF` | `n/a` | Rome/Fiumicino | FIUMICINO | 41.8 | 12.238 | 41.800 | 12.239 | 0.083 | 4.0 | 2.0 | 2.0 | 132 | 44.0 | 8.33% | PASS | `retain_unchanged` |
| Athens Eleftherios Venizelos | `LGAV` | `n/a` | Athens/Venizelos Intl | ELEFTHERIOS VENIZELOS INTL | 37.936 | 23.948 | 37.936 | 23.945 | 0.263 | 94.0 | 83.0 | 11.0 | 132 | 44.0 | 6.94% | PASS | `retain_unchanged` |
| Lisbon Humberto Delgado | `LPPT` | `n/a` | Lisbon Arpt | LISBOA | 38.775 | -9.135 | 38.781 | -9.136 | 0.673 | 114.0 | 98.0 | 16.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Vienna International | `LOWW` | `n/a` | Vienna Intl | WIEN SCHWECHAT | 48.11 | 16.569 | 48.117 | 16.582 | 1.240 | 183.0 | 179.0 | 4.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Zurich Airport | `LSZH` | `n/a` | Zürich Intl Arpt | ZURICH | 47.458 | 8.548 | 47.480 | 8.536 | 2.607 | 432.0 | 424.0 | 8.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Stockholm Arlanda | `ESSA` | `n/a` | Stockholm/Arlanda Arpt | ARLANDA | 59.649 | 17.918 | 59.664 | 17.920 | 1.672 | 42.0 | 36.0 | 6.0 | 132 | 44.0 | 6.94% | PASS | `retain_unchanged` |
| Helsinki-Vantaa | `EFHK` | `n/a` | Helsinki/Vantaa Arpt | HELSINKI VANTAA | 60.317 | 24.963 | 60.327 | 24.957 | 1.160 | 55.0 | 56.0 | -1.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Oslo Gardermoen | `ENGM` | `n/a` | Oslo/Gardermoen Arpt | GARDERMOEN / OSLO | 60.197 | 11.1 | 60.201 | 11.080 | 1.191 | 208.0 | 204.0 | 4.0 | 132 | 44.0 | 6.94% | PASS | `retain_unchanged` |
| Warsaw Chopin | `EPWA` | `n/a` | Warsaw/Chopin Arpt | OKECIE / WARSAW CHOPIN | 52.167 | 20.967 | 52.163 | 20.961 | 0.604 | 110.0 | 107.0 | 3.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Prague Václav Havel | `LKPR` | `n/a` | Prague/Havel Arpt | RUZYNE | 50.1 | 14.26 | 50.101 | 14.260 | 0.111 | 380.0 | 364.0 | 16.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Bucharest Henri Coandă | `LROP` | `n/a` | Bucharest/Coandă Intl | HENRI COANDA | 44.571 | 26.085 | 44.572 | 26.102 | 1.351 | 96.0 | 92.0 | 4.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Keflavík International | `BIKF` | `n/a` | Keflavik Intl | KEFLAVIK NAVAL AIR STATION | 63.985 | -22.605 | 63.987 | -22.614 | 0.492 | 52.0 | 49.0 | 3.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Tromsø Langnes | `ENTC` | `n/a` | Tromsø Arpt | TROMSO | 69.683 | 18.918 | 69.675 | 18.916 | 0.893 | 10.0 | 9.0 | 1.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |

## Flags and Removals

No stations exceeded the 5.0 km / 50 m thresholds or failed telemetry.
