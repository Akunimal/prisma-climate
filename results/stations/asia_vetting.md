# Station cross-check — Asia config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/asia/audit.json` on 2026-11-19T10:42:49.319365+00:00.

- Configured stations: 19; Retained: 18; Removed: 1; Auto-resolved: 0
- Dual-source confirmation: 18/19 (94.7%)
- Active 72h telemetry: 18/19 (94.7%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Beijing Capital International | `ZBAA` | `n/a` | Beijing Intl | BEIJING - CAPITAL INTERNATIONAL AIRPORT | 40.08 | 116.584 | 40.082 | 116.603 | 1.632 | 35.0 | 31.0 | 4.0 | 134 | 44.67 | 8.33% | PASS | `retain_unchanged` |
| Shanghai Pudong International | `ZSPD` | `n/a` | Shanghai/Pudong Intl | PUDONG | 31.144 | 121.808 | 31.146 | 121.800 | 0.793 | 4.0 | 4.0 | 0.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Tokyo Haneda | `RJTT` | `n/a` | Tokyo/Haneda Intl | TOKYO INTL | 35.552 | 139.78 | 35.553 | 139.781 | 0.143 | 6.0 | 5.0 | 1.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Seoul Incheon International | `RKSI` | `n/a` | Seoul/Incheon Intl | INCHEON INTL | 37.469 | 126.451 | 37.469 | 126.451 | 0.000 | 7.0 | 7.0 | 0.0 | 107 | 35.67 | 25.0% | PASS | `retain_unchanged` |
| Moscow Sheremetyevo | `UUEE` | `n/a` | Moscow/Sheremetyevo Intl | SHEREMETYEVO | 55.973 | 37.415 | 55.973 | 37.415 | 0.000 | 190.0 | 186.0 | 4.0 | 162 | 54.0 | 25.0% | PASS | `retain_unchanged` |
| Novosibirsk Tolmachevo | `UNNT` | `n/a` | Novosibirsk/Tolmachevo Arpt | TOLMACHEVO | 55.013 | 82.651 | 55.013 | 82.651 | 0.000 | 111.0 | 106.0 | 5.0 | 131 | 43.67 | 25.0% | PASS | `retain_unchanged` |
| Yakutsk Airport | `UEEE` | `n/a` | Yakutsk Arpt | YAKUTSK | 62.093 | 129.771 | 62.093 | 129.774 | 0.156 | 101.0 | 106.0 | -5.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Delhi Indira Gandhi International | `VIDP` | `n/a` | New Delhi/Gandhi Intl | INDIRA GANDHI INTL | 28.566 | 77.103 | 28.567 | 77.117 | 1.372 | 237.0 | 236.0 | 1.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Mumbai Chhatrapati Shivaji Maharaj | `VABB` | `n/a` | Mumbai/Shivaji Intl | CHHATRAPATI SHIVAJI MAHARAJ INTL | 19.088 | 72.868 | 19.100 | 72.859 | 1.635 | 14.0 | 14.0 | 0.0 | 133 | 44.33 | 6.94% | PASS | `retain_unchanged` |
| Bangkok Suvarnabhumi | `VTBS` | `n/a` | Bangkok/Suvarnabhumi Arpt | CHON BURI/SATTAHIP / SUVARNABHUMI INTL | 13.681 | 100.747 | 13.686 | 100.767 | 2.231 | 2.0 | 1.0 | 1.0 | 131 | 43.67 | 6.94% | PASS | `retain_unchanged` |
| Ho Chi Minh City Tan Son Nhat | `VVTS` | `n/a` | Ho Chi Minh/Nhat Intl | TAN SON NHAT INTL | 10.819 | 106.652 | 10.817 | 106.667 | 1.653 | 10.0 | 10.0 | 0.0 | 134 | 44.67 | 6.94% | PASS | `retain_unchanged` |
| Singapore Changi | `WSSS` | `n/a` | Singapore/Changi Intl | SINGAPORE CHANGI INTL | 1.35 | 103.994 | 1.368 | 103.982 | 2.405 | 7.0 | 17.0 | -10.0 | 135 | 45.0 | 6.94% | PASS | `retain_unchanged` |
| Kuala Lumpur International | `WMKK` | `n/a` | Kuala Lumpur Intl | KUALA LUMPUR INTL | 2.743 | 101.698 | 2.747 | 101.714 | 1.832 | 21.0 | 21.0 | 0.0 | 153 | 51.0 | 0.0% | PASS | `retain_unchanged` |
| Jakarta Soekarno-Hatta International | `WIII` | `n/a` | Jakarta/Hatta Intl | SOEKARNO HATTA INTL | -6.126 | 106.656 | -6.125 | 106.659 | 0.350 | 10.0 | 9.0 | 1.0 | 142 | 47.33 | 4.17% | PASS | `retain_unchanged` |
| Manila Ninoy Aquino International | `RPLL` | `n/a` | Manila/Aquino Intl | NINOY AQUINO INTL | 14.509 | 121.02 | 14.507 | 121.004 | 1.737 | 23.0 | 15.0 | 8.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Taipei Taoyuan International | `RCTP` | `n/a` | Taipei/Taoyuan Arpt | CHIANG KAI SHEK INTL / TAOYUAN INTL | 25.078 | 121.233 | 25.078 | 121.233 | 0.000 | 32.0 | 33.0 | -1.0 | 156 | 52.0 | 0.0% | PASS | `retain_unchanged` |
| Almaty International | `UAAA` | `n/a` | Almaty Intl | ALMATY | 43.352 | 77.041 | 43.350 | 77.027 | 1.154 | 681.0 | 673.0 | 8.0 | 153 | 51.0 | 0.0% | PASS | `retain_unchanged` |
| Tashkent International | `UTTT` | `n/a` | n/a | YUZHNY / TASHKENT ISLAM KARIMOV INTL | 41.258 | 69.281 | n/a | n/a | n/a | 432.0 | n/a | n/a | 0 | 0.0 | 100.0% | FAIL | `remove` |
| Karachi Jinnah International | `OPKC` | `n/a` | Karachi/Jinnah Intl | JINNAH INTL | 24.907 | 67.161 | 24.902 | 67.139 | 2.287 | 30.0 | 20.0 | 10.0 | 143 | 47.67 | 0.0% | PASS | `retain_unchanged` |

## Flags and Removals

- **`UTTT` (Tashkent International)**: status `FAIL`, action `remove`. Distance delta: None km. Elev delta: None m. 72h observations: 0.
