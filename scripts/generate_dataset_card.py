"""Generate the Hugging Face dataset card for Akunimal/prisma-climate.

The card is generated rather than hand-written so that what the dataset claims
always comes from a file in this repository, and so the one-shot reconciliation
workflow can inject the Hugging Face revision it observed before writing.

    uv run --project backend python scripts/generate_dataset_card.py \
        --out docs/HF_DATASET_CARD.md

Optional provenance arguments are supplied by .github/workflows/hf-backfill.yml
from the state it reads on the public Hugging Face API before any write:

    --superseded-revision <git sha>   dataset revision holding the replaced file
    --superseded-sha256  <sha256>     sha256 of the file that was replaced
"""

from __future__ import annotations

import argparse
from pathlib import Path

# sha256 of the file that was superseded on 2026-11-11 (manual run #2). The row
# breakdown below was measured against the canonical Release asset for that pair
# only; a different superseded file must not borrow these numbers.
RUN2_SHA256 = "8b8800946c89abdef5a2be78ac3799f29421c5667e4a53a26fe4c4ba500be81c"
RUN2_BREAKDOWN = (
    "Both files hold the same 74,784 rows with identical keys; 25,554 values "
    "(34.2%) differ. Every differing row is in `gfs_seamless` (25,554 of 28,272, "
    "90.4%); **zero** rows of `ecmwf_ifs025` differ (0 of 46,512). Within GFS the "
    "differing share runs from 61.1% at lead 0 to 90-97% at leads 2-15, so the "
    "differences span the whole horizon instead of concentrating at the start. "
    "That pattern is *consistent with* a GFS cycle update between the two fetches "
    "while the ECMWF IFS ensemble was unchanged - it is not proof of it, and no "
    "model cycle time is available."
)

SCHEMA_TABLE = """\
| field | required | meaning |
|---|---|---|
| `variable` | yes | `t2m_max`, `t2m_min`, `precip` |
| `unit` | yes | `degC` for temperature, `mm` for precipitation |
| `lat`, `lon` | yes | station coordinates (from `ghcnd-stations.txt`, see the repository docs) |
| `time` | yes | UTC date of the forecast target, no time zone |
| `source` | yes | source id from `configs/sources.yaml` (`openmeteo-ensemble`) |
| `value` | yes | the forecast value |
| `quality_flag` | yes | `ok` / `suspect` / `fail` |
| `location` | yes | configured station name |
| `member` | no | ensemble member index: 0-30 for `gfs_seamless`, 0-50 for `ecmwf_ifs025` |
| `lead_day` | no | forecast lead in days, 0-15 |
| `model` | no | `gfs_seamless` or `ecmwf_ifs025` |
| `day_convention` | yes | `local_calendar` - the value is aggregated over the local calendar day |
| `issue_time` | no | **download-time proxy** in UTC; see the note below |
| `retrieved_at` | yes | UTC instant the provider was queried |
|"""

ISSUE_TIME_NOTE = """\
`issue_time` is a **download-time proxy**, not a model initialisation time. The
provider does not expose the model cycle time, so PRISMA records the UTC fetch
instant instead (plan section 3.3, `docs/PLAN.md`). Two files with different
`issue_time` values are two fetches, not necessarily two model cycles."""


def _provenance(superseded_revision: str | None, superseded_sha256: str | None) -> str:
    if not superseded_sha256:
        return """\
## Provenance - 2026-11-11 (backfill)

- **Canonical file:** `forecasts/2026-11-11/openmeteo-ensemble_2026-11-11.parquet`,
  sha256 `88c23d04d21d391215bb99277e5b24b926e015367f3c0bb0b62952b9b29dde6c` - the
  asset of GitHub Release `forecast-2026-11-11`, fetched at `issue_time`
  2026-11-11 16:27:24 UTC. It is the first archive of that issue date and the file
  of record published by the Release, so under the "first archive is canonical and
  frozen" rule it is the file this dataset keeps.
- **No file was replaced.** Either the target path was empty or it already held
  exactly the sha256 above, in which case the upload was skipped as a no-op.
- The daily workflow keeps skip-if-exists, so a same-day re-run never overwrites
  the canonical file.
"""

    revision = superseded_revision or "recorded in the run log of the workflow that performed the reconciliation"
    if superseded_sha256 == RUN2_SHA256:
        difference = (
            "- **Difference (measured, not modelled):** " + RUN2_BREAKDOWN + "\n"
        )
        source = (
            "a second fetch of the same issue date by manual workflow run #2 "
            "(<https://github.com/Akunimal/prisma-climate/actions/runs/43090250095>)"
        )
    else:
        difference = (
            "- **Difference:** the replaced file was not the run-#2 file, so no row-level "
            "comparison was measured for it; see the workflow run log.\n"
        )
        source = "an earlier file at the same path"

    return f"""\
## Provenance - 2026-11-11 (backfill)

- **Canonical file:** `forecasts/2026-11-11/openmeteo-ensemble_2026-11-11.parquet`,
  sha256 `88c23d04d21d391215bb99277e5b24b926e015367f3c0bb0b62952b9b29dde6c` - the
  asset of GitHub Release `forecast-2026-11-11`, fetched at `issue_time`
  2026-11-11 16:27:24 UTC. It is the first archive of that issue date and the file
  of record published by the Release, so under the "first archive is canonical and
  frozen" rule it is the file this dataset keeps.
- **Superseded file:** sha256 `{superseded_sha256}` (`issue_time` 2026-11-11 19:46:14
  UTC), {source}. It stays readable in this dataset's git history at revision
  `{revision}` - nothing was deleted.
{difference}- The replacement was a **one-time reconciliation**, not the normal path: the daily
  workflow keeps skip-if-exists, so a same-day re-run never overwrites the canonical
  file.
"""


def build_card(
    superseded_revision: str | None = None,
    superseded_sha256: str | None = None,
) -> str:
    """Return the full dataset card markdown."""
    return f"""\
---
license: cc-by-4.0
---

# PRISMA daily forecast archive

Daily archived ensemble forecasts for the 19 configured stations in Argentina,
produced by [PRISMA](https://github.com/Akunimal/prisma-climate), an open
forecast-verification project. Past ensemble forecasts are only partially
re-fetchable from the provider (member data is retained for about 3 days, so a
very recent missed day can be repaired inside that window), but no deep
uniform-cycle ensemble backfill exists: every issue date is archived on the day
it is retrieved, and a missed day beyond the retention window is lost
verification data.

## Layout

```
forecasts/<issue_date>/openmeteo-ensemble_<issue_date>.parquet
```

One file per issue date. The issue date is read from the parquet's `issue_time`
column and never from the runner clock, and an existing path is skipped rather
than overwritten, so the **first archive of an issue date is canonical and
frozen**.

## Update frequency

Scheduled at **09:47, 12:17, 14:43 and 18:31 UTC** (redesigned 2026-11-13 after
the delays observed on 2026-11-12; previously 06:47, 12:17 and 18:31 UTC) by
the `Daily forecast archive` workflow (`.github/workflows/ingest.yml`) on
`ubuntu-latest`. **The schedule is proven as of 2026-11-12:** the first
`event=schedule` run completed that day (run 43249798026, conclusion `success`,
headSha `1e82b23`, started 15:37 UTC — the 12:17 UTC slot, ~3h20m late), and
two more schedule runs started 19:52 and 23:44 UTC that day (runs 43294532842
and 43331372851, both `success`), hours after their nominal slots; GitHub
documents scheduled runs as best-effort and subject to delay or drop under
load. Before them, the 2026-11-12 file was archived by a manual
`workflow_dispatch` rescue, and the scheduled runs themselves were data no-ops
(the canonical file already existed). The archive path itself is proven
(skip-if-exists keeps the first file of an issue date canonical).

**Residual risk:** a schedule slot can be delayed or dropped, a UTC day with no
successful run is lost verification data, and nothing self-heals; a watchdog
records missing days in the repository's ingest status for visibility only and
never repairs them. This card is generated by
`scripts/generate_dataset_card.py` and published by
`.github/workflows/hf-backfill.yml`.

## Schema

Every row follows the PRISMA connector contract (plan section 3.3):

{SCHEMA_TABLE}

{ISSUE_TIME_NOTE}

## Contents

- Models: `gfs_seamless` and `ecmwf_ifs025`, both served by the Open-Meteo
  Ensemble API.
- 19 locations, 16 forecast days (`lead_day` 0-15), 31 member indices for GFS
  and 51 for ECMWF IFS.
- Variables: `t2m_max`, `t2m_min` (degC) and `precip` (mm).

## Attribution and licences

Licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The files
redistribute derived forecast values; the underlying sources keep their own
terms:

- **Weather data by Open-Meteo.com (CC BY 4.0)** - <https://open-meteo.com/>.
  The Open-Meteo licence page states that API data are offered under
  Attribution 4.0 International (CC BY 4.0) and requires a link next to any
  location where Open-Meteo data are displayed. Its **free tier is
  non-commercial only**; commercial use of the API requires a paid plan.
- **ECMWF open data (IFS ensemble)** - the ECMWF open-data page states that the
  free IFS/AIFS forecast subset "is governed by the Creative Commons CC-BY-4.0
  licence and the ECMWF Terms of Use", that it "may be redistributed and used
  commercially, subject to appropriate attribution":
  <https://www.ecmwf.int/en/forecasts/datasets/open-data>.
- **NOAA GFS** - a U.S. Government work, public domain. The NWS disclaimer puts
  NWS/NOAA data "in the public domain, unless specifically noted otherwise",
  with the usual restrictions: no claiming it as your own work, no implying
  NOAA endorsement, and no presenting modified content as official government
  material: <https://www.weather.gov/disclaimer>.
- **ERA5 / Copernicus Climate Change Service** - not present in these files
  (they hold GFS and ECMWF IFS ensemble forecasts). Any ERA5-derived product
  published elsewhere in PRISMA must carry: "Contains modified Copernicus
  Climate Change Service information [Year]. Neither the European Commission nor
  ECMWF is responsible for any use that may be made of the information."

{_provenance(superseded_revision, superseded_sha256)}
## Provenance - 2026-11-12 (manual dispatch rescue)

- **Canonical file:** `forecasts/2026-11-12/openmeteo-ensemble_2026-11-12.parquet`,
  sha256 `689a013ffc6f23742a2728b1aefffc0c0733c533513e183ccd6b38209f10d2e5`
  (107,951 bytes), archived by manual `workflow_dispatch` run
  <https://github.com/Akunimal/prisma-climate/actions/runs/43183607191> at
  08:31 UTC because the 06:47 UTC slot had not produced a run by then. The
  GitHub Release fallback was **not** used for this run.
- **Schedule status:** proven as of 2026-11-12 - the first `event=schedule` run
  (run 43249798026, conclusion `success`, headSha `1e82b23`, 12:17 UTC slot
  started ~3h20m late) completed on this repository; two more schedule runs
  started 19:52 and 23:44 UTC that day (runs 43294532842 and 43331372851,
  both `success`), hours after their nominal slots (GitHub does not expose
  which cron produced which run). All three were data no-ops: the canonical
  file above was already in place, so the runs only left ingest status
  heartbeat commits. The archive mechanism (issue-dated path, skip-if-exists)
  is proven, and a later same-day run is a tested no-op. The 15-date
  evaluation gate counts distinct issue dates regardless of trigger, so this
  manually rescued date counts.

## Evaluation gate

Skill metrics and any leaderboard are published only once **15 distinct issue
dates** are archived. Counting starts at 2026-11-11, so the earliest possible
15th distinct issue date is **2026-11-25** if every day archives. The
hypothesis threshold **X = 60%** — the minimum share of stations in which local
calibration must reduce CRPS versus the raw ensemble while keeping 90% nominal
reliability — is frozen and is not re-thresholded; see `docs/EVALUATION_PROTOCOL.md`.

## Source repository

<https://github.com/Akunimal/prisma-climate>
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default="docs/HF_DATASET_CARD.md",
        help="path of the card markdown to write",
    )
    parser.add_argument(
        "--superseded-revision",
        default=None,
        help="dataset revision that still holds the replaced file (from the public HF API)",
    )
    parser.add_argument(
        "--superseded-sha256",
        default=None,
        help="sha256 of the file that was replaced, if any",
    )
    args = parser.parse_args(argv)

    card = build_card(
        superseded_revision=args.superseded_revision,
        superseded_sha256=args.superseded_sha256,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card, encoding="utf-8", newline="\n")
    print(f"wrote {out} ({len(card.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
