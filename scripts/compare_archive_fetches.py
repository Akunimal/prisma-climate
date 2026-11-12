"""Compare two fetches of the same forecast issue date and report where they differ.

Used to explain the 2026-11-11 pair (canonical Release asset vs the second
manual fetch that landed on Hugging Face). Writes markdown and CSV under
results/archive_diff/. Values in results/ come only from this script.

    uv run --project backend python scripts/compare_archive_fetches.py \
        --canonical path/to/release.parquet \
        --superseded path/to/hf_run2.parquet

Both files must share the same row keys; differences are broken down by model
and by lead_day. The output states whether a pattern is *consistent with* a
model-cycle update — it never asserts that as proven.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

KEY_COLUMNS = ["location", "variable", "time", "member", "lead_day", "model", "source"]
VALUE_COLUMN = "value"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def issue_time(frame: pd.DataFrame) -> str:
    stamps = pd.to_datetime(frame["issue_time"], utc=True, errors="raise")
    return str(sorted({s.strftime("%Y-%m-%d %H:%M:%S") for s in stamps}))


def load(path: Path) -> pd.DataFrame:
    frame = pd.read_parquet(path)
    missing = [column for column in KEY_COLUMNS + [VALUE_COLUMN, "issue_time"] if column not in frame.columns]
    if missing:
        raise SystemExit(f"{path} is missing columns: {', '.join(missing)}")
    return frame


def compare(canonical: pd.DataFrame, superseded: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    left = canonical.set_index(KEY_COLUMNS)[VALUE_COLUMN].sort_index()
    right = superseded.set_index(KEY_COLUMNS)[VALUE_COLUMN].sort_index()
    if not left.index.equals(right.index):
        only_left = left.index.difference(right.index)
        only_right = right.index.difference(left.index)
        raise SystemExit(
            f"row keys differ: {len(only_left)} only in canonical, {len(only_right)} only in superseded"
        )

    both = pd.DataFrame({"canonical": left, "superseded": right})
    both["abs_diff"] = (both["canonical"] - both["superseded"]).abs()
    both["differs"] = both["abs_diff"] > 0
    both = both.reset_index()

    summary = {
        "rows": len(both),
        "differing": int(both["differs"].sum()),
        "differing_pct": round(100.0 * both["differs"].mean(), 1),
    }
    return both, summary


def breakdown(diff: pd.DataFrame, by: str) -> pd.DataFrame:
    grouped = (
        diff.groupby(by, dropna=False)
        .agg(rows=("differs", "size"), differing=("differs", "sum"))
        .reset_index()
    )
    grouped["differing_pct"] = (100.0 * grouped["differing"] / grouped["rows"]).round(1)
    if "abs_diff" in diff.columns:
        medians = (
            diff.loc[diff["differs"]]
            .groupby(by, dropna=False)["abs_diff"]
            .median()
            .rename("median_abs_diff")
            .reset_index()
        )
        grouped = grouped.merge(medians, on=by, how="left")
    return grouped.sort_values(by).reset_index(drop=True)


def to_markdown(table: pd.DataFrame, headers: list[str]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in table.itertuples(index=False):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical", required=True, type=Path, help="parquet of the file of record")
    parser.add_argument("--superseded", required=True, type=Path, help="parquet of the replaced fetch")
    parser.add_argument("--out-dir", type=Path, default=Path("results/archive_diff"))
    args = parser.parse_args(argv)

    for path in (args.canonical, args.superseded):
        if not path.is_file():
            print(f"missing file: {path}", file=sys.stderr)
            return 1

    canonical_frame = load(args.canonical)
    superseded_frame = load(args.superseded)
    diff, summary = compare(canonical_frame, superseded_frame)

    by_model = breakdown(diff, "model")
    by_lead = breakdown(diff, "lead_day")
    by_model_lead = breakdown(diff, ["model", "lead_day"])
    by_variable = breakdown(diff, "variable")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    diff.to_csv(args.out_dir / "row_differences.csv", index=False)
    by_model.to_csv(args.out_dir / "by_model.csv", index=False)
    by_lead.to_csv(args.out_dir / "by_lead_day.csv", index=False)
    by_model_lead.to_csv(args.out_dir / "by_model_lead_day.csv", index=False)
    by_variable.to_csv(args.out_dir / "by_variable.csv", index=False)

    canonical_sha = sha256_file(args.canonical)
    superseded_sha = sha256_file(args.superseded)

    gfs = by_model.loc[by_model["model"] == "gfs_seamless"]
    ecmwf = by_model.loc[by_model["model"] == "ecmwf_ifs025"]
    gfs_pct = float(gfs["differing_pct"].iloc[0]) if len(gfs) else float("nan")
    ecmwf_pct = float(ecmwf["differing_pct"].iloc[0]) if len(ecmwf) else float("nan")

    lead_0 = by_lead.loc[by_lead["lead_day"] == 0]
    lead_0_pct = float(lead_0["differing_pct"].iloc[0]) if len(lead_0) else float("nan")
    later = by_lead.loc[by_lead["lead_day"] >= 2]
    later_min = float(later["differing_pct"].min()) if len(later) else float("nan")
    later_max = float(later["differing_pct"].max()) if len(later) else float("nan")

    if ecmwf_pct == 0.0 and gfs_pct > 50.0:
        interpretation = (
            "Differences are confined to `gfs_seamless` while `ecmwf_ifs025` is identical. "
            "That pattern is *consistent with* a GFS model-cycle update between the two fetches "
            "and an unchanged ECMWF IFS ensemble — it is **not proof** of a cycle update, and "
            "neither file records a model cycle time (`issue_time` is a download-time proxy)."
        )
    elif gfs_pct >= 50.0 or ecmwf_pct >= 50.0:
        interpretation = (
            "At least one model shows a large differing share across the horizon. "
            "This is *consistent with* a model-cycle update between the two fetches "
            "— it is **not proof**, and no model cycle time is available."
        )
    else:
        interpretation = (
            "Differences are spread without a single dominant model or lead band. "
            "No model-cycle explanation is asserted; see the tables for the measured pattern."
        )

    report = f"""\
# Archive fetch comparison — 2026-11-11

Generated by `scripts/compare_archive_fetches.py`. Both files are real provider
fetches of the same issue date; nothing here is synthetic.

| side | path | sha256 | issue_time (UTC) | rows |
|---|---|---|---|---|
| canonical | `{args.canonical}` | `{canonical_sha}` | {issue_time(canonical_frame)} | {len(canonical_frame)} |
| superseded | `{args.superseded}` | `{superseded_sha}` | {issue_time(superseded_frame)} | {len(superseded_frame)} |

## Summary

- shared rows: **{summary['rows']}**
- differing values: **{summary['differing']}** ({summary['differing_pct']}%)

## By model

{to_markdown(by_model, ['model', 'rows', 'differing', 'differing_pct', 'median_abs_diff'])}

## By lead_day

{to_markdown(by_lead, ['lead_day', 'rows', 'differing', 'differing_pct', 'median_abs_diff'])}

## By model x lead_day

{to_markdown(by_model_lead, ['model', 'lead_day', 'rows', 'differing', 'differing_pct', 'median_abs_diff'])}

## By variable

{to_markdown(by_variable, ['variable', 'rows', 'differing', 'differing_pct', 'median_abs_diff'])}

## Interpretation

{interpretation}

Measured anchors: GFS differing share {gfs_pct}%, ECMWF IFS {ecmwf_pct}%;
lead 0 {lead_0_pct}%, leads 2-15 range {later_min}-{later_max}%.

## Files

- `results/archive_diff/row_differences.csv`
- `results/archive_diff/by_model.csv`
- `results/archive_diff/by_lead_day.csv`
- `results/archive_diff/by_model_lead_day.csv`
- `results/archive_diff/by_variable.csv`
"""
    out_md = args.out_dir / "archive_fetch_diff.md"
    out_md.write_text(report, encoding="utf-8", newline="\n")
    print(f"wrote {out_md}")
    print(f"rows={summary['rows']} differing={summary['differing']} ({summary['differing_pct']}%)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
