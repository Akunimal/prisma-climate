# Architecture

Target architecture. Verification and calibration (Phase 1–2) now exist; the API has code but no server in this phase, and only the Flutter web app ships (see [`ROADMAP.md`](ROADMAP.md)).

```
Sources (open APIs, fixed files, national portals)
        │  one connector per source: fetch → normalize → store
        ▼
Ingest + QC (physical limits, spikes, stale stations, duplicates)
        │  scheduled jobs (GitHub Actions cron today; Cloud Run Jobs later)
        ▼
Storage (Parquet under data/ — gitignored; Zarr only for grids, Phase 2)
        │
        ├──► source-discrepancy report ──► results/
        ▼
Verification (CRPS, Brier, reliability) ──► calibration (EMOS / quantile mapping)
        │                                         │
        └──────────────► API (FastAPI) ◄──────────┘    (code exists; no server this phase)
                              │
                              ▼
                   Flutter app (Web — Phase 2; Android · iOS · Windows not built)
                              │
                              ▼
            results/ and leaderboard (script outputs only, versioned)
```

## Rules that keep it scalable

- **One connector per source**, under `backend/src/prisma/ingest/`. All implement the same interface from `base.py`: `fetch(region) → normalize → store(parquet)` returning a tidy DataFrame with the canonical columns (`variable`, `unit`, `lat`, `lon`, `time`, `source`, `value`, `quality_flag`, `location`, plus optional `member`/`lead_day`/`model`, and `day_convention`, `issue_time`, `retrieved_at`).
- **Adding a source touches only its connector module and `configs/sources.yaml`.** If it forces a change to the runner, the schema, or the analysis, the design is wrong.
- **Adding a country is one new YAML** under `configs/regions/`. Country-specific logic lives only in that country's connector (e.g. a future `ingest/smn.py`); the rest of the pipeline is region-agnostic.
- **The source registry is the single source of truth** for licences, cadence, day convention, redistribution rights and status. `docs/DATA_SOURCES.md` is the human-readable copy; if they differ, the YAML wins.

## Components (Phase 0)

| Path | Role |
|---|---|
| `backend/src/prisma/ingest/base.py` | Connector ABC, canonical schema, day-convention validation, repo-root lookup |
| `backend/src/prisma/ingest/openmeteo.py` | ERA5 history + ensemble forecast connectors |
| `backend/src/prisma/ingest/ghcn.py` | GHCN-Daily `.dly` parser |
| `backend/src/prisma/ingest/indices.py` | NOAA ONI and SAM index connectors |
| `backend/src/prisma/ingest/registry.py` | Load `configs/sources.yaml`, select sources, build connectors |
| `backend/src/prisma/ingest/runner.py` | Run a selection, write `_manifest.json` and `results/ingest_status.json` |
| `backend/src/prisma/qc/rules.py` | Physical limits, 7-day spike flag, duplicate handling |
| `backend/src/prisma/report/discrepancies.py` | ERA5 vs GHCN-Daily comparison per station/day → `results/discrepancies/` |
| `configs/sources.yaml` | Source registry |
| `configs/regions/argentina.yaml` | Region, stations, variables, horizontes |
| `scripts/run_notebook.py` | Execute `notebooks/01_data_overview.ipynb` headlessly (Agg backend) |
| `scripts/upload_forecast.py` | Push daily forecast Parquet to Hugging Face; exit 2 signals fallback |
| `.github/workflows/ingest.yml` | Daily cron: ingest → upload → commit status heartbeat |
| `.github/workflows/ci.yml` | Lint + tests on push/PR |

## Storage layout

```
data/raw/            downloaded Parquet (gitignored)
data/raw/_manifest.json   per-run manifest: rows, failures, timestamps
results/             only script outputs (versioned): figures, ingest_status.json
```

Raw data never enters git. GitHub Actions artifacts are never used as storage. The daily forecast archive goes to a public Hugging Face Dataset (secret `HF_TOKEN`, variable `HF_DATASET_REPO`), with a GitHub Release asset as fallback while that is not configured.

## Failure behaviour

The runner continues past per-source errors: a failing source is recorded in the manifest and in `results/ingest_status.json` (`status: ok | partial | failed`), never raised as a whole-run abort. The status file is always written, so the workflow can commit a heartbeat even after partial failures.

## What is deliberately absent

No server: the FastAPI code exists under `backend/src/prisma/api/` with tests, but Phase 2 offers no API service (owner decision, 2026-11-15) — the app reads the static export. No Android/iOS/Windows build (web only; listed as candidates in [`ROADMAP.md`](ROADMAP.md)). No infrastructure "just in case". Verification, calibration and the Flutter web app have since landed; see [`ROADMAP.md`](ROADMAP.md) for current status.
