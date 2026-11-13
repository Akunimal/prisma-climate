# Plan del proyecto — v2

> Nombre de trabajo: **PRISMA** (repo: `prisma-climate` o `climate-prediction-research`).
> Contenido del repo (README, docs, código) en **inglés**; este plan y `docs/es/RESUMEN.md` en español.

---

## 0. Qué cambia respecto del plan v1 y por qué

1. **Dos objetivos separados, con prioridades distintas.**
   - **Ahora:** un repo público que muestre trabajo real, para el formulario de acceso a Google Antigravity (y como portfolio de investigación).
   - **Después (opcional):** postular a grants como el Google.org Impact Challenge. El plan v1 diseñaba todo el repo alrededor de ese grant, pero según sus propias notas las personas físicas no son elegibles y la ventana 2026 ya cerró. Eso queda como fase futura, cuando haya resultados y un partner institucional. (Verificar las bases oficiales antes de contar con ese programa.)
2. **La app multiplataforma pasa a ser pieza central.** En el v1 solo aparecía como "API + panel" en la opción C. Acá es el producto visible del proyecto.
3. **Alcance recortado a lo que una persona puede sostener.** Se sacan del arranque Icechunk, Prefect, MLflow, Dask, flow matching, presupuesto y equipo con placeholders. Entran cuando hagan falta, no antes.
4. **Pregunta científica más alcanzable en la primera etapa.** Primero verificar y calibrar pronósticos abiertos en la región (1–15 días); después extender a subestacional (2–6 semanas) con ML.
5. **Regla de honestidad.** En `results/` solo entra lo que generó un script del repo. No se mencionan partners, equipo ni métricas que no existan. El README declara el estado real ("early stage").

---

## 0.1 Decisiones tomadas después de la v2

- **Región inicial: Argentina**, como primera instancia de un sistema diseñado para escalar globalmente. 15–20 estaciones representativas que cubren NOA/Puna, NEA/Chaco, Cuyo, Pampa, costa atlántica y Patagonia, declaradas en `configs/regions/argentina.yaml`. Agregar un país debe requerir solo un YAML nuevo, nunca cambios de código.
- **Observación primaria: NOAA GHCN-Daily** (cobertura global, dominio público). **SMN Argentina es fuente núcleo**, no complemento opcional: es la red local de referencia y se integra en el Tier 1.
- **Stack de la app: Flutter.**
- **Nombre: PRISMA.**
- **Fuentes:** el objetivo es integrar la mayor cantidad de fuentes locales y globales posible, bajo el contrato de conectores de la sección 3.
- **Selección de estaciones:** se prefieren estaciones presentes en GHCN-Daily y SMN con datos recientes; criterios y excepciones documentados en comentarios de `configs/regions/argentina.yaml`.
- **Archivado de pronósticos desde el día uno:** los pronósticos de ensemble del pasado no se pueden recuperar después; cada día perdido es un día de verificación perdido. Ver sección 3.9.

---

## 1. Qué es (una línea)

**Starting with Argentina, designed to scale globally.**

PRISMA es una app multiplataforma abierta que cruza datos meteorológicos y climáticos en tiempo real, verifica pronósticos contra observaciones y muestra probabilidades calibradas en lugar de valores únicos.

Lo que la hace distinta de una app del clima común:

- Muestra **probabilidades e incertidumbre**, no un solo valor.
- Muestra **qué tan bueno fue históricamente** el pronóstico para ese lugar y ese horizonte.
- **Cruza fuentes** (modelos, observaciones, señales lentas como ENSO, datos de impacto).
- Todo es **abierto y reproducible**.

---

## 2. Pregunta científica

**Fase 1 (alcanzable en semanas):**

> ¿Qué tan confiables son los pronósticos abiertos por ensembles (GFS, ECMWF, etc.) en la región elegida, a 1–15 días, y cuánto mejora un post-procesamiento estadístico local condicionado por señales lentas (fase ENSO, anomalía de SST)?

**Hipótesis falsable:**

> La calibración local (EMOS / quantile mapping) condicionada por ENSO reduce el CRPS de temperatura máxima y precipitación diaria respecto del ensemble crudo, en al menos X % de las estaciones de la región, manteniendo fiabilidad nominal al 90 %.

**Etiqueta (2026-11-13):** esta hipótesis se prueba en la **Fase 2 · Calibración + app** de [`ROADMAP.md`](ROADMAP.md) (gate de salida: "CRPSS > 0 del calibrado vs ensemble crudo"); la **Fase 1 · Verificación** del ROADMAP publica únicamente el leaderboard crudo vs climatología vs persistencia (el "Fase 2 (meses)" de esta sección es la extensión subestacional, equivalente a la Fase 3 del ROADMAP). Donde un texto anterior diga "hipótesis de la Fase 1", léase "hipótesis de la Fase 2 · Calibración". X = 60 % sin cambios.

**Fase 2 (meses):** extender el horizonte a 2–6 semanas (la brecha subestacional, S2S) con modelos de ML, siempre comparados contra climatología, persistencia y el ensemble calibrado de la Fase 1.

Métricas: CRPS / CRPSS, Brier score en eventos (calor extremo, helada, lluvia intensa), diagrama de fiabilidad.

---

## 3. Datos: fuentes, contrato y control de calidad

### 3.1 Objetivo

Integrar **la mayor cantidad de fuentes locales y globales posible** sin que el sistema se vuelva frágil. Dos consecuencias de diseño:

- **SMN Argentina es fuente núcleo.** No es un complemento opcional: es la red de observación local de referencia para la región inicial.
- **Agregar una fuente no puede tocar nada fuera de su conector y `configs/sources.yaml`.** Si integrar una fuente obliga a modificar el runner, el esquema o el análisis, el diseño está mal.

### 3.2 Ejes del cruce

| Eje del cruce | Fuente | Para qué | Estado objetivo |
|---|---|---|---|
| Pronóstico | Open-Meteo Forecast + Ensemble API; después GEFS/ECMWF abiertos | Pronósticos determinísticos y ensembles de varios modelos | Tier 1 (Open-Meteo), Tier 2 (GEFS/ECMWF) |
| Histórico | Open-Meteo Historical (ERA5) | Climatología y entrenamiento | Tier 1 |
| Observación | NOAA GHCN-Daily; SMN Argentina | Verificar contra lo que pasó realmente | Tier 1 |
| Señales lentas | NOAA ONI/ENSO y SAM | Condicionar la calibración | Tier 1 |
| Precipitación satelital | NASA IMERG / GPM; CHIRPS | Cubrir zonas sin estaciones | Tier 2 |
| Océano | NOAA OISST | SST como predictor | Tier 2 |
| Agua e impactos | INA, Servicio de Hidrografía Naval, CAMMESA, INTA | Pasar de meteorología a información de decisión | Tier 2–3 |
| Atmósfera/aire | ISD, GOES-19, NASA FIRMS, SMAP, OpenAQ/CAMS | Variables y eventos adicionales | Tier 2–3 |

Los tres sentidos del "cruce":

1. **Entre fuentes:** varios modelos y observaciones sobre el mismo punto y momento.
2. **Entre latencias:** datos que llegan cada hora, cada día o con semanas de retraso; el sistema registra cuándo llegó cada dato.
3. **Con impacto:** relacionar el pronóstico con demanda eléctrica, agro, etc.

### 3.3 Contrato de conectores

Un conector por fuente, bajo `backend/src/prisma/ingest/`. Todos implementan la misma interfaz:

```
fetch(region, **options) → normalize(...) → store(parquet)
```

`normalize` lleva todo al **esquema común**:

| campo | obligatorio | notas |
|---|---|---|
| `variable` | sí | nombre canónico (`t2m_max`, `t2m_min`, `precip`, `oni`, `sam`, ...) |
| `unit` | sí | completa desde la tabla de unidades canónicas si el conector no la fija |
| `lat`, `lon` | sí | punto real de la observación o celda de grilla usada |
| `time` | sí | UTC, sin zona horaria |
| `source` | sí | id del registro en `configs/sources.yaml` |
| `value` | sí | número; nulos explícitos permitidos |
| `quality_flag` | sí | `ok` / `suspect` / `fail` |
| `location` | sí | id de estación o punto de la región |
| `member`, `lead_day`, `model` | no | preservan identidad de ensembles y multi-modelo sin inventar esquemas nuevos |
| `day_convention` | sí | `utc`, `local_calendar`, `obs_hour_XX` o `unknown`; declarado por fuente en `configs/sources.yaml` y copiado a cada fila |
| `issue_time` | no | solo pronósticos: momento de emisión del pronóstico (UTC). Si el proveedor no expone el ciclo de modelo, se registra el momento de descarga como proxy |
| `retrieved_at` | sí | cuándo se descargó el dato (latencia real, no la nominal) |

### 3.4 Registro de fuentes: `configs/sources.yaml`

Es la **única fuente de verdad** del estado de cada fuente. Cada entrada declara, como mínimo:

- `id`, `name`, `connector`, `tier`
- `license`
- `coverage`
- `latency`
- `update_frequency`
- `day_convention`: `utc` / `local_calendar` / `obs_hour_XX` / `unknown`
- `redistributable`: `yes` / `no` / `derived_only` / `unknown`
- `status`: `active` / `planned` / `blocked`
- `access`, `endpoint`, `verified_on`, `notes`, `options`

Toda fuente `active` debe tener `day_convention` distinto de `unknown`; resolverlo es requisito previo a implementar el conector. `docs/DATA_SOURCES.md` es la versión legible para humanos de lo mismo; si difieren, manda el YAML.

### 3.5 Control de calidad automático

Antes de cualquier análisis cruzado corre un paso de QC que etiqueta cada fila:

- **Límites físicos** por variable (p. ej. temperatura y precipitación fuera de rango → `fail`).
- **Picos** contra la mediana centrada de 7 días (→ `suspect`).
- **Estaciones obsoletas:** última observación más vieja que 30 días (→ reporte de estación `stale`).
- **Duplicados** por `(source, location, variable, time, member, lead_day, model)`, conservando el último.
- Resumen por fuente/variable/flag para el reporte.

Ninguna fila se borra en silencio: se marca. El QC no reemplaza la verificación contra observaciones; solo evita que datos rotos contaminen el cruce.

### 3.6 Reporte de discrepancias entre fuentes

Un script del repo compara, para el mismo lugar y momento, los valores de distintas fuentes (p. ej. ERA5 vs GHCN vs SMN) y escribe el reporte en `results/`. Sirve para tres cosas:

- detectar sesgos sistemáticos de una fuente,
- detectar errores de unidad o de zona horaria,
- documentar honestamente dónde las fuentes no coinciden.

El reporte es una salida de script, nunca un archivo editado a mano.

### 3.7 Orden de integración

**Tier 1** (arranque, sostiene la Fase 1):

1. SMN Argentina
2. Open-Meteo (ensemble y ERA5)
3. GHCN-Daily
4. ERA5 (vía Open-Meteo; acceso directo a Copernicus más adelante)
5. Índices ENSO/ONI y SAM

**Tier 2** (cuando la Fase 1 ya verifica):

- INTA
- NASA IMERG
- CHIRPS
- NOAA OISST
- GEFS y ECMWF open data
- ISD

**Tier 3** (impactos y variables específicas):

- INA
- Servicio de Hidrografía Naval
- NASA FIRMS
- SMAP
- GOES-19
- CAMMESA
- OpenAQ / CAMS

El orden no es un compromiso de fechas: es el orden en que se justifica el esfuerzo.

### 3.8 Regla de verificación previa

Antes de escribir el conector de una fuente:

1. Verificar el **método de acceso** real (endpoint, autenticación, formato, límites de uso).
2. Verificar la **licencia** y si permite redistribuir el dato derivado.
3. Registrar el hallazgo en `configs/sources.yaml` (`verified_on`, `notes`) y en `docs/DATA_SOURCES.md`.

Si el acceso no puede verificarse desde este entorno, la fuente queda en `status: blocked` con la razón escrita. **No se implementa un conector a ciegas y no se sortea un desafío de acceso con scraping.**

Nota de licencias ya registrada: Open-Meteo es CC BY 4.0 y su nivel gratuito es solo para uso no comercial; ERA5 subyacente está bajo licencia Copernicus. Coincide con el uso declarado del proyecto.

### 3.9 Archivado diario de pronósticos

Los pronósticos de ensemble pasados **no se pueden recuperar**: si un día no se archiva, se pierde esa muestra de verificación. Por eso el archivado empieza en la Fase 0, no después:

- `.github/workflows/ingest.yml` corre todos los días (cron) en `ubuntu-latest`, descarga el ensemble de Open-Meteo para todas las estaciones de la región y guarda el Parquet con `issue_time`.
- **Nada de datos crudos en git y nada de Actions artifacts como almacenamiento.** El archivo diario sube a un Dataset público de Hugging Face (token en el secreto `HF_TOKEN`); si aún no está configurado, se adjunta a un GitHub Release como respaldo.
- La corrida escribe `results/ingest_status.json` (última corrida, filas por fuente, fallos) y lo commitea, para que los workflows programados no se desactiven por inactividad.
- Solo runners estándar de GitHub; sin runners de mayor tamaño.

---

## 4. Arquitectura

```
Fuentes (APIs abiertas, archivos, portales nacionales)
        │  un conector por fuente: fetch → normalize → store
        ▼
Ingesta + QC (límites físicos, picos, estaciones obsoletas, duplicados)
        │  jobs programados (GitHub Actions cron → después Cloud Run Jobs)
        ▼
Almacén (Parquet + DuckDB para series; Zarr solo para grillas, Fase 2)
        │
        ├──► Reporte de discrepancias entre fuentes ──► results/
        ▼
Verificación (CRPS, Brier, fiabilidad) ──► Calibración (EMOS / quantile mapping)
        │                                         │
        └──────────────► API (FastAPI) ◄──────────┘
                              │
                              ▼
              App multiplataforma (Flutter)
        Android · iOS · Web · Windows — misma base de código
                              │
                              ▼
          results/ y leaderboard (generados por scripts, versionados)
```

La verificación realimenta la calibración: cada día se compara el pronóstico de ayer con lo observado y se actualizan las métricas.

Regla de escala: la lógica específica de un país vive solo en el conector de su red nacional (p. ej. `ingest/smn.py`). El resto del sistema es agnóstico a la región.

---

## 5. La app multiplataforma

**Stack: Flutter.** Una base de código para Android, iOS, web y Windows; soporte maduro de mapas (`flutter_map`) y gráficos.

Primera versión publicable como **web** (sin tiendas, se comparte con un link) + **APK de Android**.

### Pantallas

1. **Pronóstico probabilístico** — por ubicación: rango probable (bandas 10–90 %) en vez de un solo número; probabilidad de lluvia, helada, calor extremo.
2. **¿Qué tan confiable es esto?** — skill histórico del pronóstico para ese lugar y horizonte ("a 7 días, este pronóstico acertó el rango el 85 % de las veces"). Es la pantalla diferencial.
3. **Comparador de fuentes** — los distintos modelos y la observación, superpuestos.
4. **Señales de fondo** — estado de ENSO y qué implica para la región.
5. **Alertas por umbral** — el usuario elige (p. ej. "avisame si P(helada) > 40 %"). Fase 3.
6. **Datos abiertos** — descarga de lo que muestra la app (bien público).

Caché offline para zonas con mala conectividad.

---

## 6. Estructura del repo (monorepo)

```
prisma-climate/
├── README.md               # qué es, estado real, quickstart, figuras, fuentes y licencias
├── LICENSE                 # Apache-2.0
├── CITATION.cff
├── docker-compose.yml      # backend + API local
├── configs/
│   ├── sources.yaml        # registro de fuentes: licencia, cobertura, latencia, estado
│   └── regions/
│       └── argentina.yaml  # región, estaciones, variables, horizontes
├── backend/
│   ├── pyproject.toml      # uv, ruff, pytest
│   ├── src/prisma/
│   │   ├── ingest/         # base.py (contrato), openmeteo.py, ghcn.py, smn.py, indices.py, ...
│   │   ├── qc/             # límites físicos, picos, estaciones obsoletas
│   │   ├── store/          # parquet + duckdb
│   │   ├── report/         # discrepancias entre fuentes
│   │   ├── verify/         # metrics.py (CRPS, Brier), reliability.py
│   │   ├── calibrate/      # emos.py, quantile_mapping.py
│   │   └── api/            # FastAPI: /forecast, /skill, /sources, /enso
│   └── tests/
├── app/                    # Flutter
│   └── lib/{screens,services,models,widgets}/
├── notebooks/
│   ├── 01_data_overview.ipynb
│   ├── 02_verification.ipynb
│   └── 03_calibration.ipynb
├── results/                # SOLO salidas generadas por scripts (figuras, reportes, leaderboard.csv)
├── docs/
│   ├── PLAN.md             # este archivo
│   ├── ARCHITECTURE.md
│   ├── DATA_SOURCES.md     # fuente, licencia, frecuencia, redistribuible sí/no
│   ├── EVALUATION_PROTOCOL.md  # escrito ANTES de calibrar/entrenar
│   ├── ROADMAP.md
│   └── es/RESUMEN.md
└── .github/workflows/
    ├── ci.yml              # lint + tests (backend y app)
    └── ingest.yml          # cron diario de ingesta y verificación
```

Se mantiene del v1: `EVALUATION_PROTOCOL.md` escrito antes de entrenar, `results/` versionado, `configs/` en vez de constantes, licencia permisiva, DOI vía Zenodo más adelante.

---

## 7. Roadmap con puertas de salida

| Fase | Plazo | Entregable | Puerta (condición para pasar) |
|---|---|---|---|
| **0 · Repo honesto** | esta semana | README con estado real, licencia, `DATA_SOURCES.md`, ingesta funcionando (Open-Meteo + GHCN), notebook 01 con un gráfico real de la región | Alguien clona el repo y con un comando reproduce el gráfico |
| **1 · Verificación** | 2–4 semanas | Ingesta diaria automática (GitHub Actions), SMN integrado, QC y reporte de discrepancias, primeras métricas reales en `results/`, `EVALUATION_PROTOCOL.md` | Leaderboard con ensemble crudo vs climatología vs persistencia, generado por script |
| **2 · Calibración + app v0.1** | 1–2 meses | EMOS / quantile mapping, API FastAPI, app Flutter (web + Android) con pantallas 1–3 | CRPSS > 0 del calibrado vs ensemble crudo; app pública accesible por link |
| **3 · Subestacional + alertas** | 2–4 meses | Horizonte 2–6 semanas con ML, condicionamiento ENSO, pantallas 4–5, iOS/Windows | Modelo ML supera al calibrado de Fase 2 en al menos un horizonte, o se documenta que no |
| **4 · Bien público + partners** | 4–6 meses | Dataset y modelos con DOI (Zenodo), preprint o informe técnico, contacto con universidad / CONICET / INTA | Al menos un partner institucional interesado (requisito para grants) |

Si una fase no pasa su puerta, se documenta el resultado negativo: también es un resultado.

---

## 8. Métricas

| Dimensión | Métrica | Objetivo |
|---|---|---|
| Científica | CRPSS vs climatología / persistencia / ensemble crudo | > 0 (Fase 2) |
| Científica | Brier skill en eventos (helada, calor, lluvia intensa) | > 0 (Fase 2) |
| Científica | Fiabilidad al 90 % | Desvío < 0,05 |
| Datos | Cobertura de fuentes activas del Tier 1 | 5/5 (Fase 1) |
| Datos | Discrepancias entre fuentes explicadas | 100 % documentadas |
| Ingeniería | Ingesta diaria sin intervención manual | 30 días seguidos |
| Ingeniería | Reproducibilidad: script → mismas figuras | 100 % en CI |
| Producto | App accesible en web + Android | Fase 2 |
| Bien público | Datos y código abiertos, DOI | Fase 4 |

---

## 9. Riesgos

- **Alcance (riesgo n.º 1):** es un proyecto de una persona. Se avanza fase por fase; nada de infraestructura "por las dudas".
- **Fuentes de datos:** disponibilidad, formato y licencia de SMN, CAMMESA, INTA pueden cambiar. Cada fuente se valida antes de depender de ella; el registro deja el estado y la fecha de verificación.
- **Acceso bloqueado:** si un portal nacional exige captcha o bloquea el acceso automatizado, la fuente queda `blocked` y se documenta. No se sortea el control de acceso.
- **"AI washing":** todo modelo de IA va al lado de un baseline estadístico. Si el simple gana, se dice.
- **Coherencia:** lo que se declara en formularios y aplicaciones tiene que coincidir con lo que muestra el repo.
- **Grants:** requieren organización elegible. No se diseña el repo alrededor de eso hasta la Fase 4.

---

## 10. Decisiones

**Resueltas:**

1. **Región inicial:** Argentina, 15–20 estaciones en `configs/regions/argentina.yaml`. "Starting with Argentina, designed to scale globally."
2. **Stack de la app:** Flutter.
3. **Nombre:** PRISMA (repo `prisma-climate`).
4. **Fuentes:** registro en `configs/sources.yaml`; SMN es núcleo y Tier 1; orden de integración por tiers.
5. **Repo en GitHub:** `Akunimal/prisma-climate`, público, creado el 2026-11-11 con CI (lint + tests) en verde.
6. **Umbral X de la hipótesis (sección 2):** 60 % de estaciones, fijado en `EVALUATION_PROTOCOL.md` §2 antes de cualquier calibración.
7. **Acceso a SMN:** verificado el 2026-11-11 — datos abiertos en `ssl.smn.gob.ar` sin desafío; registrado en `configs/sources.yaml` y `docs/DATA_SOURCES.md`.
8. **Licencia y convención de día SMN (2026-11-11):** `PAD_legales.pdf` + Infoleg disp25.pdf confirman CC BY 2.5 AR con atribución sobre datos crudos/observacionales → `redistributable: yes`; `day_convention: local_calendar` verificado desde los payloads (`datohorario` FECHA+HORA [HOA] 0–23, `observaciones` un TMAX/TMIN por día local; el parámetro `fecha` se ignora). Conector `ingest/smn.py` implementado → `status: active`.

**Pendientes:** ninguno de la Fase 1 previo al conector.

---

## 11. Prompt de arranque para el agente (Fase 0)

```
Read docs/PLAN.md. Implement Phase 0 only:
1. Create the repo structure from section 6 (empty folders get a .gitkeep; do not create the Flutter app yet).
2. backend/: Python project with uv. Implement the connector contract in src/prisma/ingest/base.py and
   connectors for Open-Meteo (historical ERA5 + current ensemble forecast) and NOAA GHCN-Daily.
   Sources live in configs/sources.yaml; the region is configs/regions/argentina.yaml (15-20 stations
   across Argentina's climate zones). Save normalized Parquet under data/ (gitignored).
3. notebooks/01_data_overview.ipynb: load the Parquet files and plot the last 30 years of
   temperature for each location plus the current ensemble forecast with a 10-90% band.
   Save the figures to results/figures/.
4. README.md in English: one-line description, honest status ("early-stage independent
   research"), quickstart (max 5 commands), the generated figure, data sources with licenses,
   Apache-2.0 license.
5. docs/DATA_SOURCES.md with every source, its license, update frequency and whether it can
   be redistributed.
Do not add features from later phases. Do not put anything in results/ that was not produced
by a script in the repo.
```
