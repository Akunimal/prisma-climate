"""Phase 1 verification runner (docs/EVALUATION_PROTOCOL.md, as amended).

Usage::

    python -m prisma.verify.run

Hard gate (2026-11-11 amendment): the command refuses to compute anything on
real data unless the Hugging Face dataset holds at least 15 distinct issue
dates under ``forecasts/``. Below the gate it prints the current count and
nothing else, then exits non-zero; no command-line flag overrides this (the
parser accepts no flags at all). Tests inject synthetic listings and loaders;
the real archive is never scored before the gate opens.

Above the gate the command:

- pairs archived ensemble forecasts with the SMN temperature observation
  archive (``observations/smn/observaciones`` per-day zips plus the optional
  ``regtemp`` window) by **local calendar day** — both the forecast target
  ``time`` and the observation ``FECHA`` are local-calendar labels
  (``day_convention: local_calendar``);
- scores the **raw ensemble** as fair CRPS per model over ``quality_flag ==
  ok`` members (ok-only policy INFERRED; listed as an open protocol point);
- scores **climatology** as ERA5 at the station points over the training
  window (section 3), shifted by the frozen per-station / per-calendar-month
  SMN-minus-ERA5 mean difference (2026-11-13 amendment,
  ``results/climatology_adjustment/``), sampled over the target's calendar
  day plus/minus 15 days (section 4.2; circular day-of-year distance
  INFERRED);
- scores **persistence** as the last completed SMN local day strictly before
  the issue's local day, carried forward, ``n/a`` beyond lead day 3
  (section 4.3; reference-day rule INFERRED);
- reports CRPSS of the raw ensemble against each baseline (section 5), per
  station and lead day over issue dates, pooled and per issue-hour stratum
  (section 3.2: 00:00-11:59 / 12:00-23:59 UTC).

Local inputs used only above the gate: ``data/raw/openmeteo-era5.parquet``,
``results/climatology_adjustment/smn_era5_adjustment.csv``,
``configs/regions/argentina.yaml`` and the SMN catalogue probe file
``data/smn_probe/estaciones/estaciones_smn.txt`` (gitignored). HF access is
unauthenticated public read; no token is read or written anywhere here.

No minimum sample per cell and no lead-day suppression is applied (open
protocol points); every emitted cell carries its ``n`` counts.
"""

from __future__ import annotations

import argparse
import os
import zipfile
from collections.abc import Callable, Iterable, Sequence
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .metrics import crps_ensemble, crps_from_samples, crpss

GATE_ISSUE_DATES = 15
TEMP_VARIABLES = ("t2m_max", "t2m_min")
PERSISTENCE_MAX_LEAD = 3
CAL_WINDOW_DAYS = 15
LOCAL_TZ = "America/Argentina/Cordoba"
DEFAULT_REPO = "Akunimal/prisma-climate"
BAND_MORNING = "00:00-11:59"
BAND_AFTERNOON = "12:00-23:59"
ERA5_REL = Path("data") / "raw" / "openmeteo-era5.parquet"
ADJ_REL = Path("results") / "climatology_adjustment" / "smn_era5_adjustment.csv"
CATALOGUE_REL = Path("data") / "smn_probe" / "estaciones" / "estaciones_smn.txt"
REGION_REL = Path("configs") / "regions" / "argentina.yaml"
OUT_DIR_REL = Path("results") / "verification"


def gate_message(issue_dates: int) -> str:
    """The only output below the gate: the count and the refusal."""
    return (
        f"{issue_dates} distinct issue dates archived; "
        f"{GATE_ISSUE_DATES} required by the 15-issue-date gate "
        "(docs/EVALUATION_PROTOCOL.md). No metric computed."
    )


def count_issue_dates(paths: Iterable[str]) -> int:
    """Distinct ``forecasts/<YYYY-MM-DD>/...`` date keys in a repo file listing."""
    dates: set[str] = set()
    for raw in paths:
        parts = str(raw).replace("\\", "/").split("/")
        if len(parts) >= 3 and parts[0] == "forecasts" and parts[1]:
            dates.add(parts[1])
    return len(dates)


def list_forecast_paths() -> list[str]:
    """Unauthenticated listing of the public HF dataset (no token read)."""
    os.environ.pop("HF_TOKEN", None)
    from huggingface_hub import list_repo_files

    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)
    return list(list_repo_files(repo, repo_type="dataset"))


def issue_band(issue_time: Any) -> str:
    """UTC issue-hour stratum of the 2026-11-13 amendment (section 3.2)."""
    stamp = pd.Timestamp(issue_time)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    hour = stamp.tz_convert("UTC").hour
    return BAND_MORNING if hour <= 11 else BAND_AFTERNOON


def pair_forecasts_observations(
    forecasts: pd.DataFrame,
    observations: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-join member-level forecast rows to observations on local day.

    Missing station-days stay missing (never filled). ``quality_flag == ok``
    rows only (INFERRED policy — open protocol point). Variables are the two
    temperature targets; precipitation is not verifiable (2026-11-12
    amendment).
    """
    rows = forecasts.loc[forecasts["variable"].isin(TEMP_VARIABLES)]
    if "quality_flag" in rows.columns:
        rows = rows.loc[rows["quality_flag"].eq("ok")]
    obs = observations.rename(columns={"value": "obs_value"})[
        ["location", "variable", "time", "obs_value"]
    ]
    merged = rows.merge(obs, on=["location", "variable", "time"], how="inner")
    return merged.loc[merged["obs_value"].notna()].reset_index(drop=True)


def persistence_value(
    observations: pd.DataFrame,
    location: str,
    variable: str,
    issue_time: Any,
) -> float:
    """Last completed SMN local day strictly before the issue's local day.

    INFERRED reference-day rule (open protocol point): only observations that
    were complete before the issue's local calendar day may be carried
    forward; NaN when the archive holds no earlier day.
    """
    stamp = pd.Timestamp(issue_time)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    cutoff = stamp.tz_convert(LOCAL_TZ).tz_localize(None).normalize()
    series = observations.loc[
        observations["location"].eq(location) & observations["variable"].eq(variable)
    ].copy()
    series["time"] = pd.to_datetime(series["time"])
    prior = series.loc[series["time"] < cutoff]
    if prior.empty:
        return float("nan")
    return float(prior.loc[prior["time"].idxmax(), "value"])


def _norm_doy(stamp: pd.Timestamp) -> int:
    """Day-of-year on a 365-day scale (leap-day tail folded back)."""
    doy = int(stamp.day_of_year)
    if stamp.is_leap_year and doy > 60:
        return doy - 1
    return doy


def climatology_samples(
    era5: pd.DataFrame,
    adjustment: pd.DataFrame,
    location: str,
    variable: str,
    target: Any,
    train_start: Any,
    train_end: Any,
) -> np.ndarray:
    """Adjusted ERA5 climatology sample for one target's calendar window.

    Rows of ``era5`` (``location``, ``variable``, ``time``, ``value``; source
    pre-filtered to openmeteo-era5) inside the training window whose normalized
    day-of-year is within ``CAL_WINDOW_DAYS`` of the target (circular), each
    shifted by the frozen table's ``mean_diff_smn_minus_era5`` for that
    station / variable / the sample row's own calendar month.
    """
    target_stamp = pd.Timestamp(target)
    work = era5[["location", "variable", "time", "value"]].copy()
    work["time"] = pd.to_datetime(work["time"])
    window = work.loc[
        work["location"].eq(location)
        & work["variable"].eq(variable)
        & (work["time"] >= pd.Timestamp(train_start))
        & (work["time"] <= pd.Timestamp(train_end))
    ]
    if window.empty:
        return np.empty(0, dtype=float)
    window = window.drop_duplicates(subset=["time"], keep="first").sort_values("time")
    target_doy = _norm_doy(target_stamp)
    doys = window["time"].map(lambda t: _norm_doy(pd.Timestamp(t))).to_numpy()
    distance = np.abs(doys - target_doy)
    distance = np.minimum(distance, 365 - distance)
    selected = window.loc[distance <= CAL_WINDOW_DAYS]
    if selected.empty:
        return np.empty(0, dtype=float)

    table = adjustment.set_index(["location", "variable", "calendar_month"])[
        "mean_diff_smn_minus_era5"
    ]
    keys = pd.MultiIndex.from_arrays(
        [
            [location] * len(selected),
            [variable] * len(selected),
            list(selected["time"].dt.month),
        ]
    )
    diffs = table.reindex(keys)
    if diffs.isna().any():
        months = [int(month) for month in selected["time"].dt.month]
        missing = sorted(
            {
                month
                for month, is_nan in zip(months, diffs.isna(), strict=True)
                if is_nan
            }
        )
        raise ValueError(
            f"no frozen adjustment for {location} {variable} months {missing}"
        )
    values = selected["value"].to_numpy(dtype=float) + diffs.to_numpy(dtype=float)
    return values


def score_pairs(
    pairs: pd.DataFrame,
    observations: pd.DataFrame,
    era5: pd.DataFrame,
    adjustment: pd.DataFrame,
    *,
    train_start: Any,
    train_end: Any,
) -> pd.DataFrame:
    """Score raw / climatology / persistence for every paired member group.

    One row per ``(issue_time, model, location, variable, time, lead_day)``.
    Persistence beyond ``PERSISTENCE_MAX_LEAD`` is NaN (``n/a``, section 4.3).
    """
    group_cols = ["issue_time", "model", "location", "variable", "time", "lead_day"]
    persistence_cache: dict[tuple[str, str, Any], float] = {}
    records: list[dict[str, Any]] = []
    for key, group in pairs.groupby(group_cols, sort=False):
        issue_time, model, location, variable, target, lead_day = key
        obs_value = float(group["obs_value"].iloc[0])
        members = group["value"].dropna().to_numpy(dtype=float)
        if members.size == 0:
            continue
        raw = crps_ensemble(members, obs_value)

        samples = climatology_samples(
            era5, adjustment, location, variable, target, train_start, train_end
        )
        clim = crps_from_samples(samples, obs_value) if samples.size else float("nan")

        cache_key = (location, variable, issue_time)
        if cache_key not in persistence_cache:
            persistence_cache[cache_key] = persistence_value(
                observations, location, variable, issue_time
            )
        reference = persistence_cache[cache_key]
        if int(lead_day) <= PERSISTENCE_MAX_LEAD and np.isfinite(reference):
            pers = crps_ensemble([reference], obs_value)
        else:
            pers = float("nan")

        records.append(
            {
                "issue_time": issue_time,
                "model": model,
                "location": location,
                "variable": variable,
                "time": target,
                "lead_day": int(lead_day),
                "stratum": issue_band(issue_time),
                "obs_value": obs_value,
                "raw_crps": raw,
                "climatology_crps": clim,
                "persistence_crps": pers,
            }
        )
    if not records:
        return pd.DataFrame(
            columns=[
                "issue_time",
                "model",
                "location",
                "variable",
                "time",
                "lead_day",
                "stratum",
                "obs_value",
                "raw_crps",
                "climatology_crps",
                "persistence_crps",
            ]
        )
    return pd.DataFrame.from_records(records)


def _mean_finite(values: np.ndarray) -> tuple[float, int]:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), 0
    return float(finite.mean()), int(finite.size)


def _crpss_finite(raw: np.ndarray, reference: np.ndarray) -> float:
    both = np.isfinite(raw) & np.isfinite(reference)
    if not both.any():
        return float("nan")
    return float(crpss(raw[both], reference[both]))


def leaderboard(scored: pd.DataFrame, *, by_stratum: bool = False) -> pd.DataFrame:
    """Per station / lead day means over issue dates (pooled or per stratum).

    Cells carry their own pair counts; no cell is suppressed and no minimum
    sample is applied (open protocol points).
    """
    keys = ["location", "variable", "model", "lead_day"]
    if by_stratum:
        keys = [*keys, "stratum"]
    if scored.empty:
        return pd.DataFrame(
            columns=[
                *keys,
                "n_pairs",
                "n_climatology",
                "n_persistence",
                "crps_raw",
                "crps_climatology",
                "crps_persistence",
                "crpss_vs_climatology",
                "crpss_vs_persistence",
            ]
        )
    records: list[dict[str, Any]] = []
    for key, group in scored.groupby(keys, sort=True):
        if not isinstance(key, tuple):
            key = (key,)
        raw = group["raw_crps"].to_numpy(dtype=float)
        clim = group["climatology_crps"].to_numpy(dtype=float)
        pers = group["persistence_crps"].to_numpy(dtype=float)
        crps_raw, n_raw = _mean_finite(raw)
        crps_clim, n_clim = _mean_finite(clim)
        crps_pers, n_pers = _mean_finite(pers)
        record = dict(zip(keys, key, strict=True))
        record.update(
            {
                "n_pairs": n_raw,
                "n_climatology": n_clim,
                "n_persistence": n_pers,
                "crps_raw": crps_raw,
                "crps_climatology": crps_clim,
                "crps_persistence": crps_pers,
                "crpss_vs_climatology": _crpss_finite(raw, clim),
                "crpss_vs_persistence": _crpss_finite(raw, pers),
            }
        )
        records.append(record)
    return pd.DataFrame.from_records(records)


def write_results(
    board: pd.DataFrame,
    strata: pd.DataFrame,
    out_dir: Path,
    *,
    issue_dates: int,
) -> list[Path]:
    """Write the leaderboard tables under ``results/verification/`` (script-only)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    board_path = out_dir / "leaderboard.csv"
    strata_path = out_dir / "leaderboard_by_issue_hour_stratum.csv"
    md_path = out_dir / "leaderboard.md"
    board.to_csv(board_path, index=False)
    strata.to_csv(strata_path, index=False)
    stamp = pd.Timestamp.now(tz="UTC").tz_localize(None)
    lines = [
        "# Phase 1 leaderboard — raw vs climatology vs persistence",
        "",
        f"Generated by `python -m prisma.verify.run` on {stamp} (UTC) after the "
        f"15-issue-date gate ({issue_dates} distinct issue dates archived).",
        "",
        "Baseline definitions: `docs/EVALUATION_PROTOCOL.md` as amended "
        "2026-11-11, 2026-11-12 and 2026-11-13. Climatology is ERA5 adjusted to "
        "SMN by the frozen table `results/climatology_adjustment/`; persistence "
        f"is n/a beyond lead day {PERSISTENCE_MAX_LEAD}.",
        "",
        "Sample honesty: every cell carries `n_pairs` / `n_climatology` / "
        "`n_persistence`; no cell is suppressed and no minimum sample is "
        "applied (open protocol points, reported to the project owner).",
        "",
        "Issue-hour strata (section 3.2): pooled table in `leaderboard.csv`, "
        f"per-stratum table in `{strata_path.name}`.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [board_path, strata_path, md_path]


def _parse_payload_zip(path: Path) -> pd.DataFrame:
    """Parse one archived observations zip into payload-name rows.

    Both payload texts share the fixed windows of their parsers: per-day
    ``observaciones`` zips go through the connector parser; ``regtemp`` zips
    through the regtemp text parser (FECHA one column to the left).
    """
    from ..ingest.smn import parse_observaciones

    with zipfile.ZipFile(path) as archive:
        members = sorted(name for name in archive.namelist() if name.lower().endswith(".txt"))
        if not members:
            raise ValueError(f"no .txt member in {path}")
        text = archive.read(members[0]).decode("latin-1")
    if "regtemp" in path.as_posix() or "registro_temperatura" in members[0]:
        from ..report.smn_leg import parse_regtemp_text

        frame = parse_regtemp_text(text)
        return frame.rename(columns={"regtemp_name": "smn_name"})
    frame = parse_observaciones(text)
    return frame[["time", "smn_name", "t2m_max", "t2m_min"]]


def observations_long(
    payload_frames: Sequence[pd.DataFrame],
    region: dict[str, Any],
    catalogue_by_nro: dict[str, str],
) -> pd.DataFrame:
    """Resolve payload names to region locations; one row per non-blank value.

    Duplicate station-days prefer the later frame in ``payload_frames`` (pass
    daily ``observaciones`` after ``regtemp`` so the daily canonical payload
    wins; INFERRED dedup rule — the two sources have not been observed to
    overlap).
    """
    from ..report.smn_leg import resolve_region_stations

    names = {
        str(name)
        for frame in payload_frames
        for name in frame["smn_name"].dropna().unique()
    }
    resolution = resolve_region_stations(region, catalogue_by_nro, names)
    name_to_location = {
        str(row.regtemp_name): str(row.location)
        for row in resolution.itertuples(index=False)
        if str(row.match_status).startswith("resolved") and str(row.regtemp_name)
    }
    records: list[dict[str, Any]] = []
    for frame in payload_frames:
        for row in frame.itertuples(index=False):
            location = name_to_location.get(str(row.smn_name))
            if location is None:
                continue
            for variable, value in (
                ("t2m_max", row.t2m_max),
                ("t2m_min", row.t2m_min),
            ):
                if value != value:  # NaN: blank field is a gap, never a row
                    continue
                records.append(
                    {
                        "location": location,
                        "variable": variable,
                        "time": pd.Timestamp(row.time),
                        "value": float(value),
                    }
                )
    out = pd.DataFrame.from_records(
        records, columns=["location", "variable", "time", "value"]
    )
    if out.empty:
        return out
    out = out.drop_duplicates(subset=["location", "variable", "time"], keep="last")
    return out.sort_values(["location", "variable", "time"]).reset_index(drop=True)


def run_above_gate(issue_dates: int) -> int:
    """Full Phase 1 pipeline; only reachable once the gate count is >= 15."""
    from huggingface_hub import hf_hub_download

    from ..ingest.base import find_repo_root, load_region

    root = find_repo_root()
    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)
    paths = list_forecast_paths()

    forecast_paths = sorted(
        p for p in paths if p.startswith("forecasts/") and p.endswith(".parquet")
    )
    obs_paths = sorted(
        p for p in paths if p.startswith("observations/smn/") and p.endswith(".zip")
    )
    forecasts = pd.concat(
        [
            pd.read_parquet(hf_hub_download(repo, p, repo_type="dataset"))
            for p in forecast_paths
        ],
        ignore_index=True,
    )
    payload_frames = [
        _parse_payload_zip(Path(hf_hub_download(repo, p, repo_type="dataset")))
        for p in obs_paths
    ]

    region = load_region(root / REGION_REL)
    from ..report.smn_leg import parse_catalogue_nro_names

    catalogue = parse_catalogue_nro_names(root / CATALOGUE_REL)
    observations = observations_long(payload_frames, region, catalogue)

    era5 = pd.read_parquet(root / ERA5_REL)
    era5 = era5.loc[era5["source"].eq("openmeteo-era5")]
    era5 = era5[["location", "variable", "time", "value"]]
    adjustment = pd.read_csv(root / ADJ_REL)

    train_start = pd.Timestamp(region["history_start"])
    train_end = pd.Timestamp(date.today() - timedelta(days=400))
    pairs = pair_forecasts_observations(forecasts, observations)
    scored = score_pairs(
        pairs,
        observations,
        era5,
        adjustment,
        train_start=train_start,
        train_end=train_end,
    )
    board = leaderboard(scored)
    strata = leaderboard(scored, by_stratum=True)
    written = write_results(board, strata, root / OUT_DIR_REL, issue_dates=issue_dates)
    print(
        f"gated run: {issue_dates} issue dates; {len(pairs)} paired member rows; "
        f"{len(board)} leaderboard cells; wrote "
        + ", ".join(path.relative_to(root).as_posix() for path in written)
    )
    return 0


def main(
    argv: list[str] | None = None,
    *,
    list_files: Callable[[], list[str]] | None = None,
    run: Callable[[int], int] | None = None,
) -> int:
    """Entry point: the gate first, nothing else below it.

    The parser defines no options, so no flag can override the gate; tests
    inject ``list_files`` (synthetic archive listing) and ``run`` (recorder)
    to exercise both sides without touching the real archive.
    """
    parser = argparse.ArgumentParser(
        prog="python -m prisma.verify.run",
        description=(
            "Phase 1 verification runner; gated on 15 distinct archived issue "
            "dates (docs/EVALUATION_PROTOCOL.md). No options exist."
        ),
    )
    parser.parse_args(argv)

    paths = list_files() if list_files is not None else list_forecast_paths()
    issue_dates = count_issue_dates(paths)
    if issue_dates < GATE_ISSUE_DATES:
        print(gate_message(issue_dates))
        return 1
    runner = run if run is not None else run_above_gate
    result = runner(issue_dates)
    return int(result) if result is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
