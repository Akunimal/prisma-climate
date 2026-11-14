# Site data export

The app reads **static JSON published on GitHub Pages**. There is no server and
no API in this phase: a workflow regenerates the tree from the public archives
and deploys it as ordinary files.

- **Export script:** [`scripts/export_site_data.py`](../scripts/export_site_data.py)
- **Publishing workflow:** [`.github/workflows/site.yml`](../.github/workflows/site.yml)
- **Tests:** [`backend/tests/test_export_site_data.py`](../backend/tests/test_export_site_data.py)
  (synthetic fixtures; no network, no real archive)

Every read of the Hugging Face dataset is **unauthenticated**: the script never
reads `HF_TOKEN` and passes `token=False` to `huggingface_hub`, so a cached login
token on disk is never used either.

## What the export reads

| input | location in the public dataset |
|---|---|
| canonical ensemble forecast | `forecasts/<issue_date>/openmeteo-ensemble_<issue_date>.parquet` (latest issue date) |
| canonical SMN regtemp snapshot | `observations/smn/regtemp/<fecha>/regtemp.zip` (latest snapshot) |

The issue date, issue time and station list come from those files and from
`configs/regions/argentina.yaml`; the archive key is never the wall clock.

## JSON tree

```
data/latest.json
data/about.json
data/stations/<station_id>.json
```

The deploy root contains `index.html` plus this `data/` directory, so with the
Pages base URL `https://<owner>.github.io/<repo>/data/` the app fetches
`latest.json`, `about.json` and `stations/<station_id>.json` relatively.

### `latest.json`

| field | type | meaning |
|---|---|---|
| `schema_version` | string | tree version, currently `"1.0"` |
| `generated_at` | string | export instant, ISO-8601 UTC (`...Z`) |
| `issue_date` | string | `YYYY-MM-DD`, forecast issue date (from the archive path) |
| `issue_time` | string | ISO-8601 UTC, from the parquet `issue_time` column (download-time proxy) |
| `models` | array of string | model ids present, sorted (`ecmwf_ifs025`, `gfs_seamless`) |
| `stations` | array of object | `id`, `name`, `lat`, `lon`, `climate_zone` from `configs/regions/` |

### `stations/<station_id>.json`

| field | type | meaning |
|---|---|---|
| `schema_version`, `generated_at`, `issue_date`, `issue_time`, `models` | | same values as `latest.json` |
| `station` | object | `id`, `name`, `lat`, `lon`, `climate_zone` |
| `forecast` | object | `{variable: {model: [case, ...]}}` for `t2m_max`, `t2m_min`, `precip` |
| `observed` | array | last 30 archived SMN days: `date`, `t2m_max`, `t2m_min` (null when the field is blank) |

A forecast `case` is one lead day of one model:

| field | type | meaning |
|---|---|---|
| `lead_day` | integer | 0-15, from the archive |
| `valid_local_date` | string | local calendar date the values are valid for (`YYYY-MM-DD`) |
| `n_members` | integer | usable members in the case (`quality_flag == "ok"` and non-null value) |
| `nominal_members` | integer | nominal member count of the model (`options.member_counts` in `configs/sources.yaml`) |
| `status` | string | `"ok"` or `"missing_members"` |
| `p10`, `p25`, `p50`, `p75`, `p90` | number or null | percentile of the usable member values (linear interpolation), rounded to 2 decimals |
| `min`, `max` | number or null | smallest and largest usable member value |
| `fraction_ge_1mm`, `fraction_ge_10mm` | number or null | **precip only**: share of usable members at or above 1 mm / 10 mm |

**Models are never pooled.** Each model keeps its own case list, its own
`n_members` and its own quantiles.

**80 % member rule (2026-11-14 amendment, rule 1).** A case is exported only if
at least 80 % of the model's nominal member count is present; otherwise the case
is written with `status: "missing_members"` and every statistic `null`. It is
never filled from another model, another lead day or another case.

### `about.json`

| field | meaning |
|---|---|
| `schema_version`, `generated_at` | as above |
| `dataset_url` | public Hugging Face dataset |
| `region` | `id`, `name`, `timezone` of the region file |
| `sources` | ids, roles, licences (`CC BY 4.0`; `CC BY 2.5 AR`), licence URLs, the exact attribution strings and their URLs |
| `status.forecasts` | states the forecasts are raw and uncalibrated |
| `status.verification` | states that no verification result is published before the 15-issue-date gate |
| `status.observations` | states that SMN gaps stay null and are never filled |
| `status.smn_snapshot_date` | date key of the regtemp snapshot used |

## No skill metrics

The tree carries **descriptive statistics of the raw ensemble members and the
archived observations only**. No CRPS, CRPSS, Brier score, reliability,
coverage, station-skill aggregate or leaderboard is computed, exported or
displayed: those stay gated on **15 distinct issue dates**
([`docs/EVALUATION_PROTOCOL.md`](EVALUATION_PROTOCOL.md); the gate stood at 4/15
on 2026-11-14, earliest open 2026-11-25). A test asserts that no exported key
names a skill metric.

## How to run it

```bash
uv run --project backend --with huggingface_hub python scripts/export_site_data.py --out-dir data
```

`--out-dir` defaults to `data/` at the repository root. Generated files are
**not committed** (see `.gitignore`): the Pages workflow builds them on the
runner. The export also accepts `--root` and, for tests, injectable listing and
download callables.

The values are rounded to 2 decimals; percentiles use NumPy's default linear
interpolation; `min`/`max` are the extrema of the usable members, not of the
nominal set.

## Real example (2026-11-14 issue, Buenos Aires Observatorio)

Excerpt of `stations/buenos_aires.json`, `forecast.t2m_max`, lead day 0:

```json
{
  "ecmwf_ifs025": {
    "lead_day": 0,
    "valid_local_date": "2026-11-13",
    "n_members": 51,
    "nominal_members": 51,
    "status": "ok",
    "p10": 24.2,
    "p25": 24.9,
    "p50": 25.8,
    "p75": 26.45,
    "p90": 27.0,
    "min": 22.4,
    "max": 28.0
  },
  "gfs_seamless": {
    "lead_day": 0,
    "valid_local_date": "2026-11-13",
    "n_members": 31,
    "nominal_members": 31,
    "status": "ok",
    "p10": 26.5,
    "p25": 26.7,
    "p50": 27.0,
    "p75": 27.2,
    "p90": 27.4,
    "min": 26.2,
    "max": 27.8
  }
}
```

## Publishing

`.github/workflows/site.yml` runs on completion of **Daily forecast archive**
(`workflow_run`) and on `workflow_dispatch`; it exports the tree, adds the
static `site/index.html`, and deploys the result to GitHub Pages. It has
`contents: read` and never commits to `main`.

**Owner action:** in *Settings → Pages → Source* the repository must be set to
**GitHub Actions**. On 2026-11-14 the Pages API returned `404 Not Found`
(OBSERVED), i.e. Pages was **not** enabled; the workflow will fail at the deploy
step until the owner flips that switch. The workflow does not work around it.

## Licences and attribution

The page and `about.json` must keep the attribution strings next to the data:

- **Weather data by Open-Meteo.com (CC BY 4.0)** —
  <https://open-meteo.com/>. The Open-Meteo licence page offers the API data
  under CC BY 4.0 and requires "a link next to any location" where the data are
  displayed; the free tier is non-commercial only.
- **Servicio Meteorológico Nacional (SMN), Argentina (CC BY 2.5 AR)** —
  <https://www.smn.gob.ar/> with the licence at
  <https://creativecommons.org/licenses/by/2.5/ar/>.
