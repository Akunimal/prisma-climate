# Resumen del proyecto (Fase 0)

**PRISMA — Empezando por Argentina, diseñado para escalar globalmente.**

Investigación independiente en etapa temprana. Este documento resume en español el estado real del repositorio; el plan completo (en español) está en [`../PLAN.md`](../PLAN.md) y la documentación técnica en inglés en [`../README.md`](../README.md).

## Qué es

PRISMA es una app multiplataforma abierta (todavía no implementada) que cruza datos meteorológicos y climáticos en tiempo real, verifica pronósticos contra observaciones y mostrará probabilidades calibradas en lugar de valores únicos.

Lo que la distingue de una app del clima común:

- Muestra **probabilidades e incertidumbre**, no un solo valor.
- Muestra **qué tan bueno fue históricamente** el pronóstico para ese lugar y ese horizonte.
- **Cruza fuentes** (modelos, observaciones, señales lentas como ENSO, datos de impacto).
- Todo es **abierto y reproducible**.

## Qué existe hoy (Fase 0)

- **Ingesta** de Open-Meteo (historial ERA5 + ensemble multi-modelo), NOAA GHCN-Daily y los índices NOAA ONI/SAM, normalizados a Parquet.
- **Control de calidad** (límites físicos, picos, duplicados) y **registro de fuentes** con licencias y convención de día en [`configs/sources.yaml`](../configs/sources.yaml).
- **Región Argentina**: 19 estaciones en `configs/regions/argentina.yaml`, con los criterios de selección documentados en comentarios (preferencia GHCN∩SMN con datos recientes; cobertura por zonas climáticas).
- **Notebook 01** que genera figuras reales de las estaciones.
- **Workflow diario** (GitHub Actions) que archiva el pronóstico de ensemble: los pronósticos pasados no se pueden recuperar; cada día perdido es un día de verificación perdido. Sube a un Dataset público de Hugging Face, con GitHub Release como respaldo.
- **Convención de día** (`day_convention`) y **hora de emisión** (`issue_time`) en el esquema, declarados por fuente.

## Qué no existe todavía

Métricas de verificación, calibración, la API, la app Flutter y el conector de SMN Argentina. Nada en `results/` fue producido por nada distinto de un script del repositorio.

## Fuentes de datos

| Fuente | Licencia | Redistribuible | Estado |
|---|---|---|---|
| Open-Meteo (ERA5 + ensemble) | CC BY 4.0 (nivel gratuito no comercial); ERA5 bajo licencia Copernicus | Solo derivados | activa |
| NOAA GHCN-Daily | Dominio público (NOAA/NCEI) | Sí | activa |
| NOAA ONI / SAM | Dominio público (NOAA/NWS) | Sí | activa |
| SMN Argentina | CC BY 2.5 AR (contenido del sitio; términos a registrar) | Por verificar | planificada (endpoints verificados, conector sin escribir) |

**Diagnóstico SMN (verificado 2026-11-11):** `www.smn.gob.ar` sirve un desafío JS de Cloudflare a clientes simples (no es un bloqueo por IP ni por país); `api.smn.gob.ar` está caído en el origen (522); pero **los datos abiertos en `ssl.smn.gob.ar/dpd/zipopendata.php?dato=...` responden 200 sin desafío** (`estaciones`, `observaciones`, `tiepre`, entre otros). El catálogo oficial está en datos.gob.ar (CKAN). Detalle en [`docs/DATA_SOURCES.md`](../DATA_SOURCES.md).

## Cómo reproducir

Requiere [uv](https://docs.astral.sh/uv/). Desde la raíz del repositorio:

```bash
uv sync --project backend
uv run --project backend python -m prisma.ingest
uv run --project backend python scripts/run_notebook.py
```

El tercer comando escribe las figuras en `results/figures/`. `uv run --project backend pytest` corre la suite de tests.

## Hoja de ruta

| Fase | Entregable | Puerta |
|---|---|---|
| 0 · Repo honesto | README con estado real, licencia, fuentes, ingesta + notebook | Alguien clona y reproduce un gráfico con un comando |
| 1 · Verificación | Ingesta diaria automática, SMN integrado, primeras métricas | Leaderboard generado por script |
| 2 · Calibración + app v0.1 | EMOS/quantile mapping, API, app Flutter (web + Android) | CRPSS > 0; app pública por link |
| 3 · Subestacional + alertas | Horizonte 2–6 semanas con ML | El ML supera a la calibración, o se documenta que no |
| 4 · Bien público + partners | DOI, preprint, partner institucional | Al menos un partner interesado |

Detalle en [`docs/ROADMAP.md`](../ROADMAP.md).

## Licencia y citación

Apache-2.0 ([`LICENSE`](../LICENSE)). Metadatos de citación en [`CITATION.cff`](../CITATION.cff).
