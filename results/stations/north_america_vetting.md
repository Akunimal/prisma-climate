# Station cross-check — North America config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/north_america/audit.json` on 2026-11-19T10:42:21.806846+00:00.

- Configured stations: 18; Retained: 18; Removed: 0; Auto-resolved: 0
- Dual-source confirmation: 18/18 (100.0%)
- Active 72h telemetry: 18/18 (100.0%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| New York JFK International | `KJFK` | `USW00094789` | New York/JF Kennedy Intl | JOHN F KENNEDY INTERNATIONAL AIRPORT | 40.64 | -73.779 | 40.639 | -73.764 | 1.274 | 4.0 | 3.0 | 1.0 | 71 | 23.67 | 1.39% | PASS | `retain_unchanged` |
| Chicago O'Hare International | `KORD` | `USW00094846` | Chicago/O'Hare Intl | CHICAGO O'HARE INTERNATIONAL AIRPORT | 41.974 | -87.907 | 41.960 | -87.932 | 2.550 | 205.0 | 202.0 | 3.0 | 69 | 23.0 | 4.17% | PASS | `retain_unchanged` |
| Miami International | `KMIA` | `USW00012839` | Miami Intl | MIAMI INTERNATIONAL AIRPORT | 25.795 | -80.29 | 25.788 | -80.317 | 2.803 | 2.0 | 1.0 | 1.0 | 104 | 34.67 | 0.0% | PASS | `retain_unchanged` |
| Houston George Bush Intercontinental | `KIAH` | `USW00012960` | Houston/Bush Intl | G BUSH INTERCONTINENTAL AP/HOUSTON AP | 29.98 | -95.34 | 29.984 | -95.361 | 2.054 | 30.0 | 27.0 | 3.0 | 76 | 25.33 | 0.0% | PASS | `retain_unchanged` |
| Denver International | `KDEN` | `USW00003017` | Denver Intl | DENVER INTERNATIONAL AIRPORT | 39.856 | -104.674 | 39.847 | -104.656 | 1.844 | 1656.0 | 1656.0 | 0.0 | 73 | 24.33 | 0.0% | PASS | `retain_unchanged` |
| Los Angeles International | `KLAX` | `USW00023174` | Los Angeles Intl | LOS ANGELES INTERNATIONAL AIRPORT | 33.942 | -118.408 | 33.938 | -118.387 | 2.020 | 38.0 | 30.0 | 8.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Seattle-Tacoma International | `KSEA` | `USW00024233` | Seattle-Tacoma Intl | SEATTLE-TACOMA INTERNATIONAL AIRPORT | 47.45 | -122.312 | 47.445 | -122.314 | 0.620 | 132.0 | 115.0 | 17.0 | 74 | 24.67 | 0.0% | PASS | `retain_unchanged` |
| Phoenix Sky Harbor | `KPHX` | `USW00023183` | Phoenix/Sky Harbor Intl | PHOENIX SKY HARBOR INTL AIRPORT | 33.434 | -112.012 | 33.428 | -112.004 | 1.037 | 346.0 | 338.0 | 8.0 | 75 | 25.0 | 0.0% | PASS | `retain_unchanged` |
| Anchorage Ted Stevens | `PANC` | `USW00026451` | Anchorage Intl | TED STEVENS ANCHORAGE INTL | 61.174 | -149.996 | 61.169 | -150.028 | 1.786 | 46.0 | 39.0 | 7.0 | 103 | 34.33 | 1.39% | PASS | `retain_unchanged` |
| Toronto Pearson International | `CYYZ` | `CA006158733` | Toronto/Pearson Intl | LESTER B PEARSON INTL | 43.677 | -79.625 | 43.679 | -79.629 | 0.391 | 173.0 | 171.0 | 2.0 | 75 | 25.0 | 0.0% | PASS | `retain_unchanged` |
| Halifax Stanfield International | `CYHZ` | `CA006352000` | Halifax/Stanfield Intl | HALIFAX INTL / STANFIELD INTL | 44.881 | -63.509 | 44.878 | -63.514 | 0.485 | 145.0 | 136.0 | 9.0 | 75 | 25.0 | 0.0% | PASS | `retain_unchanged` |
| Calgary International | `CYYC` | `CA003031093` | Calgary Intl | CALGARY INTL | 51.114 | -114.02 | 51.116 | -114.011 | 0.666 | 1084.0 | 1085.0 | -1.0 | 114 | 38.0 | 0.0% | PASS | `retain_unchanged` |
| Vancouver International | `CYVR` | `CA001108447` | Vancouver Intl | VANCOUVER INTL | 49.195 | -123.182 | 49.183 | -123.168 | 1.678 | 4.0 | 2.0 | 2.0 | 75 | 25.0 | 0.0% | PASS | `retain_unchanged` |
| Yellowknife Airport | `CYZF` | `CA002204100` | Yellowknife Arpt | YELLOWKNIFE | 62.463 | -114.44 | 62.475 | -114.448 | 1.396 | 206.0 | 202.0 | 4.0 | 102 | 34.0 | 0.0% | PASS | `retain_unchanged` |
| Mexico City Benito Juárez | `MMMX` | `MX000009048` | Mexico City Intl | LICENCIADO BENITO JUAREZ INTL / MEXICO CITY INTL | 19.436 | -99.072 | 19.436 | -99.072 | 0.000 | 2230.0 | 2224.0 | 6.0 | 82 | 27.33 | 19.44% | PASS | `retain_unchanged` |
| Monterrey International | `MMMY` | `MX000019047` | Monterrey Intl | GENERAL MARIANO ESCOBEDO INTL / MONTERREY INTL | 25.778 | -100.107 | 25.774 | -100.104 | 0.537 | 390.0 | 382.0 | 8.0 | 72 | 24.0 | 8.33% | PASS | `retain_unchanged` |
| Cancún International | `MMUN` | `MX000023024` | Cancún Intl | CANCUN INTL | 21.036 | -86.877 | 21.038 | -86.855 | 2.294 | 6.0 | 13.0 | -7.0 | 74 | 24.67 | 18.06% | PASS | `retain_unchanged` |
| Guadalajara International | `MMGL` | `MX000014066` | Guadalajara Arpt | DON MIGUEL HIDALGO Y COSTILLA INTL / GUADALAJARA INTL | 20.522 | -103.311 | 20.523 | -103.312 | 0.152 | 1529.0 | 1531.0 | -2.0 | 71 | 23.67 | 16.67% | PASS | `retain_unchanged` |

## Flags and Removals

No stations exceeded the 5.0 km / 50 m thresholds or failed telemetry.
