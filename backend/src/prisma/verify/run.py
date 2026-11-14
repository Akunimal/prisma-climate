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
  archive (``observations/smn/observaciones`` per-day zips plus the
  ``regtemp`` window) by **local calendar day** — both the forecast target
  ``time`` and the observation ``FECHA`` are local-calendar labels
  (``day_convention: local_calendar``);
- scores the **raw ensemble** as fair CRPS per model over member values whose
  ``quality_flag`` is ``ok``, and records a case as ``missing_members``
  instead of scoring it when fewer than 80 % of that model's nominal member
  count (``configs/sources.yaml`` ``member_counts``) is present
  (2026-11-14 amendment, rules 1);
- scores **climatology** as ERA5 at the station points over the training
  window (section 3), shifted by the frozen per-station / per-calendar-month
  SMN-minus-ERA5 mean difference (2026-11-13 amendment,
  ``results/climatology_adjustment/``), sampled over the target's calendar
  day plus/minus 15 days using **circular** day-of-year distance with 29
  February treated as 28 February (2026-11-14 amendment, rule 2);
- scores **persistence** as the SMN observation of the last completed local
  calendar day strictly before the local date of issue_time — missing that
  day means ``n/a``, no further look-back — and ``n/a`` beyond lead day 3
  (section 4.3 anchored by 2026-11-14 amendment, rule 3);
- reports CRPSS of the raw ensemble against each baseline (section 5), per
  station and lead day over issue dates, pooled and per issue-hour stratum
  (section 3.2: 00:00-11:59 / 12:00-23:59 UTC), flagging every cell with
  fewer than 10 matured pairs as ``insufficient`` and excluding it from skill
  scores (2026-11-14 amendment, rules 4-5);
- prefers the latest archived ``regtemp`` snapshot per station-day over
  ``observaciones`` (the frozen climatology adjustment was estimated on
  regtemp), lets ``observaciones`` fill only uncovered days, and reports the
  number and size of the differences (2026-11-14 amendment, rule 6).

Local inputs used only above the gate: ``data/raw/openmeteo-era5.parquet``,
``results/climatology_adjustment/smn_era5_adjustment.csv``,
``configs/regions/argentina.yaml`` and the SMN catalogue probe file
``data/smn_probe/estaciones/estaciones_smn.txt`` (gitignored). HF access is
unauthenticated public read; no token is read or written anywhere here.

Every emitted cell carries its ``n`` counts; cells with fewer than 10
matured pairs are flagged ``insufficient`` and excluded from skill scores
(2026-11-14 amendment, rules 4-5).
"""

from __future__ import annotations

import argparse
import os
import zipfile
from collections.abc import Callable, Iterable, Mapping, Sequence
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
MIN_SAMPLE = 10
MEMBER_FRACTION = 4, 5  # at least 80 % of the nominal member count present
LOCAL_TZ = "America/Argentina/Buenos_Aires"
DEFAULT_REPO = "Akunimal/prisma-climate"
BAND_MORNING = "00:00-11:59"
BAND_AFTERNOON = "12:00-23:59"
ERA5_REL = Path("data") / "raw" / "openmeteo-era5.parquet"
ADJ_REL = Path("results") / "climatology_adjustment" / "smn_era5_adjustment.csv"
CATALOGUE_REL = Path("data") / "smn_probe" / "estaciones" / "estaciones_smn.txt"
REGION_REL = Path("configs") / "regions" / "argentina.yaml"
SOURCES_REL = Path("configs") / "sources.yaml"
OUT_DIR_REL = Path("results") / "verification"
PAYLOAD_KINDS = ("regtemp", "observaciones")


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


def _payload_kind(repo_path: str) -> str | None:
    """Payload kind of an ``observations/smn/<kind>/...`` archive path.

    Returns ``"regtemp"`` / ``"observaciones"`` or ``None`` for anything else
    (``datohorario`` and manifests are not verification inputs).
    """
    parts = str(repo_path).replace("\\", "/").split("/")
    if len(parts) >= 4 and parts[0] == "observations" and parts[1] == "smn":
        if parts[2] in PAYLOAD_KINDS:
            return parts[2]
    return None


def load_member_counts(root: Path) -> dict[str, int]:
    """Nominal member count per model from ``configs/sources.yaml`` (rule 1).

    The values live in the ``openmeteo-ensemble`` source's
    ``options.member_counts``: member ids 0-30 for ``gfs_seamless`` (31
    delivered values) and 0-50 for ``ecmwf_ifs025`` (51), verified against
    every canonical archive parquet and the dataset card schema.
    """
    from ..ingest.base import load_yaml

    config = load_yaml(root / SOURCES_REL)
    for source in config.get("sources", []):
        if source.get("id") == "openmeteo-ensemble":
            counts = (source.get("options") or {}).get("member_counts")
            if isinstance(counts, dict) and counts:
                return {str(model): int(n) for model, n in counts.items()}
            raise ValueError(
                f"{SOURCES_REL}: openmeteo-ensemble options.member_counts missing; "
                "the 80% member rule (EVALUATION_PROTOCOL 2026-11-14) needs it"
            )
    raise ValueError(f"{SOURCES_REL}: no openmeteo-ensemble source entry")


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

    Missing station-days stay missing (never filled). Member usability
    (``quality_flag == ok`` and the 80 % count) is decided per case at
    scoring time (2026-11-14 amendment, rule 1), so suspect member rows are
    still joined here and excluded in :func:`score_pairs`. Variables are the
    two temperature targets; precipitation is not verifiable (2026-11-12
    amendment).
    """
    rows = forecasts.loc[forecasts["variable"].isin(TEMP_VARIABLES)]
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
    """SMN observation of the last completed local day before the issue day.

    Rule 3 of the 2026-11-14 amendment: the reference day is the local
    calendar day (America/Argentina/Buenos_Aires) strictly before the local
    date of ``issue_time``; if that day is not in the archive the answer is
    NaN — persistence never looks further back.
    """
    stamp = pd.Timestamp(issue_time)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    cutoff = stamp.tz_convert(LOCAL_TZ).tz_localize(None).normalize()
    target_day = cutoff - pd.Timedelta(days=1)
    series = observations.loc[
        observations["location"].eq(location) & observations["variable"].eq(variable)
    ].copy()
    series["time"] = pd.to_datetime(series["time"])
    hit = series.loc[series["time"].eq(target_day)]
    if hit.empty:
        return float("nan")
    return float(hit.iloc[0]["value"])


def _norm_doy(stamp: pd.Timestamp) -> int:
    """Day-of-year on a 365-day scale (29 February treated as 28 February)."""
    doy = int(stamp.day_of_year)
    if stamp.is_leap_year and doy > 59:
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
    member_counts: Mapping[str, int],
) -> pd.DataFrame:
    """Score raw / climatology / persistence for every paired member group.

    One row per ``(issue_time, model, location, variable, time, lead_day)``.
    A case is scored only when the member values usable for it (present and
    ``quality_flag == ok``) are at least 80 % of the model's nominal member
    count; otherwise the row is recorded with
    ``case_status = "missing_members"`` and NaN scores (rule 1). Persistence
    beyond ``PERSISTENCE_MAX_LEAD`` is NaN (``n/a``, section 4.3).
    """
    group_cols = ["issue_time", "model", "location", "variable", "time", "lead_day"]
    persistence_cache: dict[tuple[str, str, Any], float] = {}
    records: list[dict[str, Any]] = []
    for key, group in pairs.groupby(group_cols, sort=False):
        issue_time, model, location, variable, target, lead_day = key
        obs_value = float(group["obs_value"].iloc[0])
        usable_mask = group["value"].notna()
        if "quality_flag" in group.columns:
            usable_mask = usable_mask & group["quality_flag"].eq("ok")
        members = group.loc[usable_mask, "value"].to_numpy(dtype=float)
        nominal = member_counts.get(str(model))
        if nominal is None:
            raise ValueError(
                f"no nominal member count for model {model!r} in "
                f"{SOURCES_REL} options.member_counts"
            )
        # At least 80 % of the nominal count present, as exact integer math:
        # present * 5 >= nominal * 4 (rule 1).
        enough = int(members.size) * MEMBER_FRACTION[1] >= nominal * MEMBER_FRACTION[0]
        if not enough:
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
                    "case_status": "missing_members",
                    "n_present_members": int(members.size),
                    "raw_crps": float("nan"),
                    "climatology_crps": float("nan"),
                    "persistence_crps": float("nan"),
                }
            )
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
                "case_status": "scored",
                "n_present_members": int(members.size),
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
                "case_status",
                "n_present_members",
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

    Cells carry their own pair counts. A cell with fewer than ``MIN_SAMPLE``
    matured pairs is flagged ``insufficient`` and its skill scores are set to
    NaN — excluded from skill scores and, downstream, from aggregates and the
    station count of the hypothesis test (rules 4-5 of the 2026-11-14
    amendment). ``n_missing`` counts the cases recorded as
    ``missing_members`` (rule 1); nothing is pooled across lead days to reach
    the minimum (rule 5).
    """
    keys = ["location", "variable", "model", "lead_day"]
    if by_stratum:
        keys = [*keys, "stratum"]
    if scored.empty:
        return pd.DataFrame(
            columns=[
                *keys,
                "n_pairs",
                "n_missing",
                "insufficient",
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
        n_missing = int(group["case_status"].eq("missing_members").sum())
        insufficient = n_raw < MIN_SAMPLE
        crpss_clim_cell = float("nan") if insufficient else _crpss_finite(raw, clim)
        crpss_pers_cell = float("nan") if insufficient else _crpss_finite(raw, pers)
        record = dict(zip(keys, key, strict=True))
        record.update(
            {
                "n_pairs": n_raw,
                "n_missing": n_missing,
                "insufficient": insufficient,
                "n_climatology": n_clim,
                "n_persistence": n_pers,
                "crps_raw": crps_raw,
                "crps_climatology": crps_clim,
                "crps_persistence": crps_pers,
                "crpss_vs_climatology": crpss_clim_cell,
                "crpss_vs_persistence": crpss_pers_cell,
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
    product_diffs: Mapping[str, Any] | None = None,
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
        "2026-11-11, 2026-11-12, 2026-11-13 and 2026-11-14. Climatology is ERA5 "
        "adjusted to SMN by the frozen table `results/climatology_adjustment/`; "
        f"persistence is n/a beyond lead day {PERSISTENCE_MAX_LEAD}.",
        "",
        "Sample honesty: every cell carries `n_pairs` / `n_climatology` / "
        f"`n_persistence`; a cell with fewer than {MIN_SAMPLE} matured pairs is "
        "flagged `insufficient` and its skill scores are blank (excluded from "
        "skill scores, aggregates and the station count of the hypothesis test). "
        "`n_missing` counts cases recorded as `missing_members` — fewer than 80% "
        "of the model's nominal member count present (rules 1, 4 and 5 of the "
        "2026-11-14 amendment).",
        "",
    ]
    if product_diffs is not None:
        lines.append(
            "SMN product precedence (rule 6): the latest archived regtemp snapshot "
            "is the primary series and `observaciones` fills only uncovered days. "
            "Overlapping station-days compared: "
            f"{product_diffs['n_comparable']} value pair(s), "
            f"{product_diffs['n_differ']} differing; "
            f"max |difference| {product_diffs['max_abs_diff']:.3f} degC, "
            f"mean |difference| {product_diffs['mean_abs_diff']:.3f} degC "
            "(regtemp value used in every differing case)."
        )
        lines.append("")
    lines += [
        "Issue-hour strata (section 3.2): pooled table in `leaderboard.csv`, "
        f"per-stratum table in `{strata_path.name}`.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return [board_path, strata_path, md_path]


def _parse_payload_zip(path: Path, kind: str) -> pd.DataFrame:
    """Parse one archived observations zip into payload-name rows.

    ``kind`` is ``"regtemp"`` or ``"observaciones"`` (decided from the repo
    path by the caller): both payload texts share the fixed windows of their
    own parsers — per-day ``observaciones`` through the connector parser,
    ``regtemp`` through the regtemp text parser (FECHA one column to the
    left). ``datohorario`` is hourly and has no role in Phase 1 temperature
    verification, so it is never passed here (rule 6).
    """
    if kind not in PAYLOAD_KINDS:
        raise ValueError(f"unknown payload kind {kind!r}; allowed: {', '.join(PAYLOAD_KINDS)}")
    with zipfile.ZipFile(path) as archive:
        members = sorted(name for name in archive.namelist() if name.lower().endswith(".txt"))
        if not members:
            raise ValueError(f"no .txt member in {path}")
        text = archive.read(members[0]).decode("latin-1")
    if kind == "regtemp":
        from ..report.smn_leg import parse_regtemp_text

        frame = parse_regtemp_text(text)
        return frame.rename(columns={"regtemp_name": "smn_name"})
    from ..ingest.smn import parse_observaciones

    frame = parse_observaciones(text)
    return frame[["time", "smn_name", "t2m_max", "t2m_min"]]


def _rows_from_frames(
    payload_frames: Sequence[tuple[str, pd.DataFrame]],
    region: dict[str, Any],
    catalogue_by_nro: dict[str, str],
) -> list[dict[str, Any]]:
    """Resolve payload names to region locations; one tagged row per value."""
    from ..report.smn_leg import resolve_region_stations

    names = {
        str(name)
        for _kind, frame in payload_frames
        for name in frame["smn_name"].dropna().unique()
    }
    resolution = resolve_region_stations(region, catalogue_by_nro, names)
    name_to_location = {
        str(row.regtemp_name): str(row.location)
        for row in resolution.itertuples(index=False)
        if str(row.match_status).startswith("resolved") and str(row.regtemp_name)
    }
    records: list[dict[str, Any]] = []
    for kind, frame in payload_frames:
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
                        "kind": kind,
                    }
                )
    return records


def _product_differences(
    regtemp_values: dict[tuple[str, str, Any], float],
    observ_values: dict[tuple[str, str, Any], float],
) -> dict[str, Any]:
    """Count and size the regtemp/observaciones differences (rule 6)."""
    shared = sorted(set(regtemp_values) & set(observ_values), key=str)
    differences = [
        abs(regtemp_values[key] - observ_values[key])
        for key in shared
        if regtemp_values[key] != observ_values[key]
    ]
    return {
        "n_comparable": len(shared),
        "n_differ": len(differences),
        "max_abs_diff": max(differences, default=0.0),
        "mean_abs_diff": (sum(differences) / len(differences)) if differences else 0.0,
    }


def observations_long(
    payload_frames: Sequence[tuple[str, pd.DataFrame]],
    region: dict[str, Any],
    catalogue_by_nro: dict[str, str],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build the long observation frame under rule 6 product precedence.

    ``payload_frames`` are ``(kind, frame)`` pairs with kind ``"regtemp"`` or
    ``"observaciones"`` (later frames within a kind win). The latest archived
    regtemp snapshot is the primary series per station-day; ``observaciones``
    fills only days no archived regtemp snapshot covers. When both products
    carry the same station-day and differ, the regtemp value is used and the
    number and size of the differences is returned alongside the frame.
    """
    records = _rows_from_frames(payload_frames, region, catalogue_by_nro)
    out = pd.DataFrame.from_records(
        records, columns=["location", "variable", "time", "value", "kind"]
    )

    def _values_of(kind: str) -> dict[tuple[str, str, Any], float]:
        values: dict[tuple[str, str, Any], float] = {}
        for row in records:
            if row["kind"] == kind:
                values[(row["location"], row["variable"], row["time"])] = row["value"]
        return values

    regtemp_values = _values_of("regtemp")
    observ_values = _values_of("observaciones")
    diffs = _product_differences(regtemp_values, observ_values)

    if out.empty:
        return out.drop(columns=["kind"]), diffs
    # Precedence (rule 6): regtemp wins every station-day it covers, whatever
    # the frame order; observaciones contributes only uncovered days. Within
    # a kind the later frame in ``payload_frames`` wins (archival order).
    keys = list(zip(out["location"], out["variable"], out["time"], strict=True))
    keep_mask = [
        kind == "regtemp" or key not in regtemp_values
        for kind, key in zip(out["kind"], keys, strict=True)
    ]
    kept = out.loc[keep_mask].drop(columns=["kind"])
    kept = kept.drop_duplicates(subset=["location", "variable", "time"], keep="last")
    return kept.sort_values(["location", "variable", "time"]).reset_index(drop=True), diffs


def run_above_gate(
    issue_dates: int,
    *,
    list_files: Callable[[], list[str]] | None = None,
    download: Callable[[str, str], Path] | None = None,
    root: Path | None = None,
) -> int:
    """Full Phase 1 pipeline; only reachable once the gate count is >= 15.

    ``list_files`` (archive listing), ``download`` (repo path -> local file)
    and ``root`` (repository root holding the local inputs and the results
    directory) are injectable so tests run the whole path on synthetic data
    in a temp directory; the defaults hit the public HF dataset and this
    checkout. The HF token is never read.
    """
    from ..ingest.base import find_repo_root, load_region

    root = find_repo_root() if root is None else Path(root)
    repo = os.environ.get("HF_DATASET_REPO", DEFAULT_REPO)
    if list_files is None:
        paths = list_forecast_paths()
    else:
        paths = list(list_files())
    if download is None:
        from huggingface_hub import hf_hub_download

        def _hf_download(repo_id: str, repo_path: str) -> Path:
            return Path(hf_hub_download(repo_id, repo_path, repo_type="dataset"))

        fetch = _hf_download
    else:
        fetch = download

    forecast_paths = sorted(
        p for p in paths if p.startswith("forecasts/") and p.endswith(".parquet")
    )
    # Rule 6 covers the two daily-temperature products; datohorario is hourly
    # and is not a Phase 1 verification input, so it is never parsed here.
    kind_by_path = {
        p: kind
        for p in paths
        if (kind := _payload_kind(p)) is not None and p.endswith(".zip")
    }
    obs_paths = sorted(kind_by_path)
    forecasts = pd.concat(
        [pd.read_parquet(fetch(repo, p)) for p in forecast_paths],
        ignore_index=True,
    )
    payload_frames = [
        (kind_by_path[p], _parse_payload_zip(fetch(repo, p), kind_by_path[p]))
        for p in obs_paths
    ]

    region = load_region(root / REGION_REL)
    member_counts = load_member_counts(root)
    from ..report.smn_leg import parse_catalogue_nro_names

    catalogue = parse_catalogue_nro_names(root / CATALOGUE_REL)
    observations, product_diffs = observations_long(payload_frames, region, catalogue)

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
        member_counts=member_counts,
    )
    board = leaderboard(scored)
    strata = leaderboard(scored, by_stratum=True)
    written = write_results(
        board,
        strata,
        root / OUT_DIR_REL,
        issue_dates=issue_dates,
        product_diffs=product_diffs,
    )
    n_missing = int(scored["case_status"].eq("missing_members").sum()) if len(scored) else 0
    print(
        f"gated run: {issue_dates} issue dates; {len(pairs)} paired member rows; "
        f"{n_missing} cases recorded as missing_members; "
        f"{product_diffs['n_differ']} regtemp/observaciones difference(s) of "
        f"{product_diffs['n_comparable']} overlapping value(s); "
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
