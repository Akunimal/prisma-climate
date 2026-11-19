# Station cross-check — South America config vs NOAA AWC / ISD catalogues

Generated from committed raw evidence `results/stations/_evidence/south_america/audit.json` on 2026-11-19T10:42:21.693341+00:00.

- Configured stations: 17; Retained: 17; Removed: 0; Auto-resolved: 0
- Dual-source confirmation: 17/17 (100.0%)
- Active 72h telemetry: 17/17 (100.0%)
- Flag thresholds: Haversine distance > 5.0 km, |Δelev| > 50 m (Decision C)
- Phase 2 Vetting Gate: **PASS**; Phase 3 Obs Ref Gate: **QUALIFIED**

## Results

| location | icao | ghcn_id | awc_site | isd_name | config_lat | config_lon | awc_lat | awc_lon | delta_dist_km | config_elev_m | awc_elev_m | delta_elev_m | obs_72h | obs/day | gap% | status | action |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Santiago Pudahuel | `SCEL` | `CI000085574` | Santiago/Benítez Intl | ARTURO MERINO BENITEZ INTL | -33.393 | -70.786 | -33.393 | -70.786 | 0.000 | 474.0 | 478.0 | -4.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Punta Arenas Carlos Ibáñez | `SCCI` | `CI000085934` | Punta Arenas Arpt | CARLOS IBANEZ DEL CAMPO INTL | -53.003 | -70.855 | -53.003 | -70.855 | 0.000 | 42.0 | 37.0 | 5.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Montevideo Carrasco | `SUMU` | `UYM00086580` | Carrasco Intl | CARRASCO INTL | -34.838 | -56.031 | -34.838 | -56.031 | 0.000 | 32.0 | 32.0 | 0.0 | 92 | 30.67 | 0.0% | PASS | `retain_unchanged` |
| Asunción Silvio Pettirossi | `SGAS` | `PAM00086218` | Asunción/Pettriossi | SILVIO PETTIROSSI INTL | -25.24 | -57.519 | -25.248 | -57.519 | 0.890 | 89.0 | 83.0 | 6.0 | 92 | 30.67 | 0.0% | PASS | `retain_unchanged` |
| São Paulo Congonhas | `SBSP` | `BR00E3-0510` | Sao Paulo/Congonhas | CONGONHAS DEPUTADO FREITAS NOBRE | -23.626 | -46.656 | -23.627 | -46.655 | 0.151 | 802.0 | 802.0 | 0.0 | 95 | 31.67 | 0.0% | PASS | `retain_unchanged` |
| Rio de Janeiro Galeão | `SBGL` | `BR000300400` | Rio de Janeiro/Galeão Intl | GALEAO ANTONIO CARLOS JOBIM | -22.809 | -43.251 | -22.815 | -43.261 | 1.223 | 9.0 | 3.0 | 6.0 | 73 | 24.33 | 0.0% | PASS | `retain_unchanged` |
| Brasília Pres. Juscelino Kubitschek | `SBBR` | `BR000360140` | Brasília Intl | PRESIDENTE JUSCELINO KUBITSCHEK | -15.869 | -47.921 | -15.867 | -47.933 | 1.303 | 1060.0 | 1051.0 | 9.0 | 82 | 27.33 | 0.0% | PASS | `retain_unchanged` |
| Manaus Eduardo Gomes | `SBEG` | `BR00E3-0008` | Manaus/Gomes Intl | EDUARDO GOMES INTL | -3.036 | -60.05 | -3.039 | -60.050 | 0.334 | 84.0 | 69.0 | 15.0 | 72 | 24.0 | 0.0% | PASS | `retain_unchanged` |
| Lima Jorge Chávez | `SPJC` | `PEM00084628` | Lima/Chávez Intl | JORGE CHAVEZ INTL | -12.022 | -77.114 | -12.024 | -77.113 | 0.248 | 34.0 | 26.0 | 8.0 | 73 | 24.33 | 0.0% | PASS | `retain_unchanged` |
| Cusco Alejandro Velasco Astete | `SPZO` | `PEM00084686` | Cuzco/Astete Arpt | TENIENTE ALEJANDRO VELASCO ASTETE INTL | -13.536 | -71.939 | -13.536 | -71.939 | 0.000 | 3310.0 | 3249.0 | 61.0 | 138 | 46.0 | 0.0% | WARN_ELEV | `retain_unchanged` |
| Bogotá El Dorado | `SKBO` | `COM00080222` | Bogota/El Dorado Arpt | EL DORADO INTL | 4.702 | -74.147 | 4.706 | -74.151 | 0.628 | 2548.0 | 2547.0 | 1.0 | 95 | 31.67 | 0.0% | PASS | `retain_unchanged` |
| Quito Mariscal Sucre | `SEQM` | `ECM00084071` | Quito/New Intl | MARISCAL SUCRE INTERNATIONAL AIRPORT | -0.125 | -78.358 | -0.124 | -78.354 | 0.458 | 2400.0 | 2386.0 | 14.0 | 78 | 26.0 | 0.0% | PASS | `retain_unchanged` |
| La Paz El Alto | `SLLP` | `BL000085201` | La Paz/El Alto Intl | EL ALTO INTL | -16.513 | -68.192 | -16.511 | -68.182 | 1.089 | 4058.0 | 4061.0 | -3.0 | 73 | 24.33 | 1.39% | PASS | `retain_unchanged` |
| Santa Cruz Viru Viru | `SLVR` | `BL000085242` | Santa Cruz/Viru Intl | VIRU VIRU INTL | -17.645 | -63.135 | -17.645 | -63.135 | 0.000 | 373.0 | 377.0 | -4.0 | 74 | 24.67 | 0.0% | PASS | `retain_unchanged` |
| Buenos Aires Aeroparque | `SABE` | `AR000087582` | Buenos Aires/Newbery Arpt | AEROPARQUE JORGE NEWBERY | -34.559 | -58.416 | -34.559 | -58.416 | 0.000 | 6.0 | 3.0 | 3.0 | 82 | 27.33 | 0.0% | PASS | `retain_unchanged` |
| Córdoba Aeropuerto | `SACO` | `AR000087344` | Cordoba/Taravella Intl | AMBROSIO L V TARAVELLA | -31.317 | -64.217 | -31.324 | -64.208 | 1.156 | 474.0 | 474.0 | 0.0 | 78 | 26.0 | 0.0% | PASS | `retain_unchanged` |
| Bariloche Aeropuerto | `SAZS` | `AR000087765` | San Carlos de Bariloche Arpt | SAN CARLOS DE BARILOCHE | -41.151 | -71.158 | -41.151 | -71.157 | 0.084 | 846.0 | 843.0 | 3.0 | 73 | 24.33 | 0.0% | PASS | `retain_unchanged` |

## Flags and Removals

- **`SPZO` (Cusco Alejandro Velasco Astete)**: status `WARN_ELEV`, action `retain_unchanged`. Distance delta: 0.0 km. Elev delta: 61.0 m. 72h observations: 138.
