# regtemp station-name reconciliation

Generated 2026-11-12 03:14:47 UTC by `scripts/reconcile_regtemp_names.py`.
Values in `results/` come only from this script.

## Summary

- regtemp rows with parseable name/date: **42953**
- distinct local days: **365** (expected 365)
- distinct `NOMBRE` values: **118**
- catalogue stations parsed: **118**
- catalogue names not present in regtemp: **0**

| Match status | Count |
|---|---|
| exact | 118 |
| fuzzy | 0 |
| none | 0 |

- Ambiguous (fuzzy) matches: **0**
- Unmatched (no catalogue hit): **0**
- One-to-many catalogue duplicates: **0**

### Why not 135 names

A whitespace `split()` parse of regtemp yields ~134 distinct tokens because rows with blank `TMAX`/`TMIN` shift fields and invent fake station tokens (e.g. `AERO`). Fixed-column parsing (name at chars 21+, date at chars 0-8 as `DDMMYYYY`) is required and gives **118** distinct names over **42953** rows / **365** days.

## Partial coverage

| Station | Days present | Missing days |
|---|---|---|
| BENITO JUAREZ AERO | 356 | 9 |
| CHILECITO AERO | 296 | 69 |
| GOBERNADOR GREGORES AERO | 364 | 1 |
| OBERA | 353 | 12 |
| SANTA CRUZ AERO | 363 | 2 |
| VICTORICA | 341 | 24 |

Total missing station-days: **117** (6 stations below 365 days).

## Region station resolution (via catalogue NRO)

Region stations from `results/stations/ghcn_vs_smn.csv`: **19 resolved**, **0 partial**, **0 unresolved** of 19.

| Location | NRO | Catalogue name | regtemp name | Days | Status |
|---|---|---|---|---|---|
| La Quiaca Observatorio | 87007 | LA QUIACA OBSERVATORIO | LA QUIACA OBSERVATORIO | 365 | resolved |
| Salta Aero | 87047 | SALTA AERO | SALTA AERO | 365 | resolved |
| Tucuman (Teniente Benjamin Matienzo) | 87121 | TUCUMAN AERO | TUCUMAN AERO | 365 | resolved |
| Formosa | 87162 | FORMOSA AERO | FORMOSA AERO | 365 | resolved |
| Resistencia Aero | 87155 | RESISTENCIA AERO | RESISTENCIA AERO | 365 | resolved |
| Posadas | 87178 | POSADAS AERO | POSADAS AERO | 365 | resolved |
| Mendoza Aero | 87418 | MENDOZA AERO | MENDOZA AERO | 365 | resolved |
| San Juan | 87311 | SAN JUAN AERO | SAN JUAN AERO | 365 | resolved |
| Malargue | 87506 | MALARGUE AERO | MALARGUE AERO | 365 | resolved |
| Cordoba Aero | 87344 | CORDOBA AERO | CORDOBA AERO | 365 | resolved |
| Rosario | 87480 | ROSARIO AERO | ROSARIO AERO | 365 | resolved |
| Buenos Aires Observatorio | 87585 | BUENOS AIRES OBSERVATORIO | BUENOS AIRES OBSERVATORIO | 365 | resolved |
| Santa Rosa Aero | 87623 | SANTA ROSA AERO | SANTA ROSA AERO | 365 | resolved |
| Mar del Plata Aero | 87692 | MAR DEL PLATA AERO | MAR DEL PLATA AERO | 365 | resolved |
| Bahia Blanca Aero | 87750 | BAHIA BLANCA AERO | BAHIA BLANCA AERO | 365 | resolved |
| Comodoro Rivadavia | 87860 | COMODORO RIVADAVIA AERO | COMODORO RIVADAVIA AERO | 365 | resolved |
| San Carlos de Bariloche | 87765 | BARILOCHE AERO | BARILOCHE AERO | 365 | resolved |
| Trelew Aero | 87828 | TRELEW AERO | TRELEW AERO | 365 | resolved |
| Ushuaia Malvinas Argentinas | 87938 | USHUAIA AERO | USHUAIA AERO | 365 | resolved |

## Wiring status

**Not wired.** This table is a prerequisite for the future regtemp backfill (T22). Capture and name reconciliation do not imply ingest.

Full per-name table: [`regtemp_names.csv`](regtemp_names.csv).
Region resolution: [`region_resolution.csv`](region_resolution.csv).
