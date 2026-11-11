"""Quality control applied before any cross-source analysis."""

from __future__ import annotations

from typing import Any

import pandas as pd

PHYSICAL_LIMITS: dict[str, tuple[float, float]] = {
    "t2m": (-60.0, 60.0),
    "t2m_max": (-45.0, 55.0),
    "t2m_min": (-55.0, 40.0),
    "precip": (0.0, 400.0),
    "soil_moisture": (0.0, 1.0),
    "oni": (-6.0, 6.0),
    "sam": (-6.0, 6.0),
}

# Absolute departure from a centred 7-day median that is treated as a spike.
SPIKE_THRESHOLD: dict[str, float] = {
    "t2m_max": 15.0,
    "t2m_min": 15.0,
    "precip": 250.0,
}

DUPLICATE_KEYS = ["source", "location", "variable", "time", "member", "lead_day", "model"]
STALE_DAYS = 30


def apply_qc(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.drop_duplicates(subset=DUPLICATE_KEYS, keep="last").copy()
    out["quality_flag"] = out["quality_flag"].fillna("ok").astype("object")

    for variable, (low, high) in PHYSICAL_LIMITS.items():
        candidate = out["variable"].eq(variable) & out["value"].notna()
        out.loc[candidate & ~out["value"].between(low, high), "quality_flag"] = "fail"

    daily = out["variable"].isin(SPIKE_THRESHOLD) & out["quality_flag"].eq("ok")
    if daily.any():
        subset = out.loc[daily, ["source", "location", "variable", "time", "value"]].copy()
        subset = subset.sort_values(["source", "location", "variable", "time"])
        median = subset.groupby(["source", "location", "variable"])["value"].transform(
            lambda series: series.rolling(7, center=True, min_periods=3).median()
        )
        threshold = subset["variable"].map(SPIKE_THRESHOLD)
        spike = (subset["value"] - median).abs() > threshold
        out.loc[subset.loc[spike].index, "quality_flag"] = "suspect"

    return out


def station_status(
    frame: pd.DataFrame,
    as_of: Any | None = None,
    stale_days: int = STALE_DAYS,
) -> pd.DataFrame:
    observations = frame.loc[
        frame["source"].eq("ghcn-daily") & frame["quality_flag"].eq("ok"),
        ["location", "time"],
    ]
    if observations.empty:
        return pd.DataFrame(columns=["location", "last_observation", "days_since", "stale"])

    last = observations.groupby("location")["time"].max()
    reference = (
        pd.Timestamp(as_of)
        if as_of is not None
        else pd.Timestamp.now(tz="UTC").tz_localize(None)
    )
    status = last.rename("last_observation").to_frame()
    status["days_since"] = (reference.normalize() - status["last_observation"]).dt.days
    status["stale"] = status["days_since"] > stale_days
    return status.reset_index()


def summary(frame: pd.DataFrame) -> pd.DataFrame:
    grouped = frame.groupby(["source", "variable", "quality_flag"]).size().rename("rows")
    table = grouped.unstack(fill_value=0)
    for flag in ("ok", "suspect", "fail"):
        if flag not in table:
            table[flag] = 0
    table = table[["ok", "suspect", "fail"]]
    table["total"] = table.sum(axis=1)
    return table.reset_index()
