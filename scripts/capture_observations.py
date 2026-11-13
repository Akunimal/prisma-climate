"""Capture SMN open-data payloads and archive them under ``observations/smn/``.

Used by ``.github/workflows/observations.yml`` only. The Hugging Face write token
stays an Actions secret: every upload happens in CI, this script is never run
with the token locally, and the workflow never commits to ``main`` — a run's
identity travels in the manifest it writes to Hugging Face instead of in a
heartbeat commit.

Keying rules, identical for all three payloads:

- the target day is read from the payload's ``FECHA`` (an 8-digit local calendar
  date, DDMMYYYY) and never from the runner clock, so a re-run resolves to the
  same target instead of minting a duplicate;
- an existing target is skipped, so the first capture of a day is canonical and
  frozen;
- targets live under ``observations/smn/<dato>/<date>/`` and never under
  ``forecasts/``, which stays reserved for issue-dated forecasts;
- ``regtemp`` serves a rolling 365-day window, so its key is the window's LAST
  FECHA read from the payload; ``retrieved_at`` lives in ``manifest.json``,
  never in the path.

Requests: only ``ssl.smn.gob.ar``, a plain HTTP client (default headers), at
most three per run (``regtemp``, ``datohorario``, ``observaciones``). Licence of
the payloads: CC BY 2.5 AR with attribution to the Servicio Meteorológico
Nacional — the dataset-level cc-by-4.0 tag covers ``forecasts/`` only.

    uv run --project backend --with huggingface_hub \\
        python scripts/capture_observations.py --payloads datohorario observaciones --upload
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import zipfile
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

import requests

SMN_HOST = "ssl.smn.gob.ar"
BASE_URL = f"https://{SMN_HOST}/dpd/zipopendata.php?dato="
TIMEOUT = 60

DAILY_DATOS = ("datohorario", "observaciones")
ALL_DATOS = ("regtemp", "datohorario", "observaciones")

PREFIX = "observations/smn"

ATTRIBUTION = "Servicio Meteorológico Nacional (SMN Argentina)"
LICENCE = "CC BY 2.5 AR"
LICENCE_URL = "https://creativecommons.org/licenses/by/2.5/ar/legalcode"
LICENCE_SOURCES = [
    (
        "PAD_legales.pdf, Terminos y Condiciones de Uso, Propiedad Intelectual: "
        "'El SMN licencia todos sus contenidos bajo la licencia Creative Commons "
        "Atribucion 2.5 Argentina'"
    ),
    (
        "Infoleg disp25.pdf, Politica de Datos del SMN, section 4.A: web-accessible "
        "SMN data are Datos Abiertos under CC BY 2.5 AR with attribution to the SMN"
    ),
]

# The regtemp capture the published discrepancy results were computed from. Its
# window is the only one a later rolling-window snapshot cannot reproduce.
PRIOR_CAPTURE = {
    "target": f"{PREFIX}/regtemp/2026-11-10/",
    "retrieved_at": "2026-11-12T01:41:32Z",
    "window": {"first": "2025-11-11", "last": "2026-11-10", "distinct_days": 365},
    "data_rows": 42953,
    "sha256_zip": "28b166d87e618df127cb2e7bb932e4b6c813b0ab4e489e860cc542bf5902af98",
    "note": (
        "captured locally 2026-11-12T01:41:32Z and uploaded by the repository "
        "owner through the Hugging Face web interface; it is the file the "
        "published discrepancy results were computed from and it cannot be "
        "re-fetched, because the endpoint serves a rolling 365-day window"
    ),
}

_FECHA_RE = re.compile(r"^[ \t]*(\d{8})(?!\d)")


def url_for(dato: str) -> str:
    """Endpoint URL for an allowed payload name (ssl.smn.gob.ar only)."""
    if dato not in ALL_DATOS:
        raise ValueError(f"unknown payload {dato!r}; allowed: {', '.join(ALL_DATOS)}")
    return BASE_URL + dato


def fetch_payload(dato: str, *, get: Callable[..., requests.Response] = requests.get) -> bytes:
    """Plain GET with default headers against ssl.smn.gob.ar only."""
    url = url_for(dato)
    if urlsplit(url).hostname != SMN_HOST:
        raise ValueError(f"refusing to fetch {url}: only {SMN_HOST} is allowed")
    response = get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.content


def read_member(payload: bytes) -> tuple[str, str]:
    """Return (member name, latin-1 text) of the single file inside the ZIP."""
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        members = archive.namelist()
        if len(members) != 1:
            raise ValueError(f"expected exactly one member in the payload, found {len(members)}")
        return members[0], archive.read(members[0]).decode("latin-1")


def parse_fechas(text: str) -> list[date]:
    """Every ``FECHA`` (DDMMYYYY, local calendar day) in payload order.

    The value must sit at the start of the line (after optional blanks) and must
    be a real calendar date, so headers, unit rows and separator rows are
    ignored instead of guessed at.
    """
    dates: list[date] = []
    for line in text.splitlines():
        match = _FECHA_RE.match(line)
        if match is None:
            continue
        try:
            dates.append(datetime.strptime(match.group(1), "%d%m%Y").date())
        except ValueError:
            continue
    return dates


def fields_of(text: str) -> list[str]:
    """Column names from the payload's own header line (the one holding FECHA)."""
    for line in text.splitlines():
        if "FECHA" in line:
            return line.split()
    raise ValueError("no header line with FECHA found in the payload")


def target_dir(dato: str, key: str) -> str:
    """HF directory of one capture — observations/ only, never forecasts/."""
    if dato not in ALL_DATOS:
        raise ValueError(f"unknown payload {dato!r}; allowed: {', '.join(ALL_DATOS)}")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", key):
        raise ValueError(f"refusing malformed capture date {key!r}")
    return f"{PREFIX}/{dato}/{key}"


def key_for(dato: str, dates: Sequence[date]) -> str:
    """Capture date from the payload's FECHA values, never from the clock.

    Daily payloads must hold exactly one distinct local day (the endpoint serves
    the latest completed day and ignores ``fecha``), otherwise the payload is
    not the single day it claims to be. ``regtemp`` is keyed by the last FECHA of
    the served window.
    """
    if not dates:
        raise ValueError(f"{dato} payload carries no parseable FECHA value")
    distinct = sorted(set(dates))
    if dato in DAILY_DATOS:
        if len(distinct) != 1:
            raise ValueError(
                f"{dato} payload carries {len(distinct)} distinct FECHA values "
                f"({', '.join(d.isoformat() for d in distinct)}); one capture must be one local day"
            )
        return distinct[0].isoformat()
    if dato == "regtemp":
        return distinct[-1].isoformat()
    raise ValueError(f"unknown payload {dato!r}; allowed: {', '.join(ALL_DATOS)}")


def day_convention_evidence(dato: str, member: str, key: str) -> str:
    if dato in DAILY_DATOS:
        return (
            f"FECHA is an 8-digit local calendar date DDMMYYYY with no hour column; "
            f"{member} carries exactly one distinct value ({key}) covering hours of "
            "that local calendar day, so a day is the local calendar day"
        )
    return (
        "FECHA is an 8-digit local calendar date DDMMYYYY with no hour column and "
        "one row per station-day, so the served window spans local calendar days"
    )


def prior_capture_block(dato: str, window_first: str, sha256_zip: str) -> dict | None:
    """Relation of a regtemp window to the 2026-11-12 capture it cannot repeat.

    Returns ``None`` when the manifest being written IS that capture, so the
    folder uploaded by the owner does not compare itself with itself.
    """
    if dato != "regtemp" or sha256_zip == PRIOR_CAPTURE["sha256_zip"]:
        return None
    first = date.fromisoformat(window_first)
    prior_first = date.fromisoformat(PRIOR_CAPTURE["window"]["first"])
    gap_days = (first - prior_first).days
    if gap_days > 0:
        note = (
            f"window starts {gap_days} day(s) later than the 2026-11-12 capture "
            f"(window {PRIOR_CAPTURE['window']['first']} to "
            f"{PRIOR_CAPTURE['window']['last']}): the earlier days have rolled off "
            "the rolling 365-day window, so this snapshot does not repeat them and "
            "the two are not a day-for-day superset"
        )
    elif gap_days == 0:
        note = "window starts on the same day as the 2026-11-12 capture"
    else:
        note = (
            "window starts earlier than the 2026-11-12 capture; unexpected for a "
            "rolling 365-day window — verify before relying on either snapshot"
        )
    return {
        "target": PRIOR_CAPTURE["target"],
        "retrieved_at": PRIOR_CAPTURE["retrieved_at"],
        "window": dict(PRIOR_CAPTURE["window"]),
        "data_rows": PRIOR_CAPTURE["data_rows"],
        "sha256_zip": PRIOR_CAPTURE["sha256_zip"],
        "window_starts_later": gap_days > 0,
        "gap_days": gap_days,
        "note": note,
        "source_note": PRIOR_CAPTURE["note"],
    }


def run_block_from_env(env: Mapping[str, str]) -> dict | None:
    """Identity of the Actions run that produced this manifest.

    The observation workflow never commits to main, so this block is where its
    run status is recorded.
    """
    run_id = env.get("GITHUB_RUN_ID")
    if not run_id:
        return None
    server = env.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = env.get("GITHUB_REPOSITORY", "")
    return {
        "workflow": env.get("GITHUB_WORKFLOW", ""),
        "workflow_file": env.get("GITHUB_WORKFLOW_REF", ""),
        "run_id": run_id,
        "run_attempt": env.get("GITHUB_RUN_ATTEMPT", ""),
        "event": env.get("GITHUB_EVENT_NAME", ""),
        "scheduled_cron": env.get("SCHEDULED_CRON") or None,
        "head_sha": env.get("GITHUB_SHA", ""),
        "run_url": f"{server}/{repository}/actions/runs/{run_id}" if repository else None,
    }


def build_manifest(
    *,
    dato: str,
    member: str,
    key: str,
    dates: Sequence[date],
    fields: Sequence[str],
    payload: bytes,
    retrieved_at: datetime,
    upload_status: str,
    requests_used: int = 1,
    env: Mapping[str, str] | None = None,
) -> dict:
    """Manifest of one capture: provenance, window, checksum, licence, run."""
    distinct = sorted(set(dates))
    window = {
        "first": distinct[0].isoformat(),
        "last": distinct[-1].isoformat(),
        "distinct_days": len(distinct),
    }
    manifest: dict = {
        "source_id": "smn-argentina",
        "dato": dato,
        "endpoint": url_for(dato),
        "payload_file": f"{dato}.zip",
        "payload_member": member,
        "retrieved_at": retrieved_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "capture_key": key,
        "capture_key_source": (
            "last FECHA of the served window, read from the payload"
            if dato == "regtemp"
            else "the payload's FECHA, read from the payload (the runner clock is never used)"
        ),
        "served_window": window,
        "data_rows": len(dates),
        "sha256_zip": hashlib.sha256(payload).hexdigest(),
        "fields": list(fields),
        "field_layout": (
            "whitespace-separated fixed columns; FECHA is an 8-digit DDMMYYYY local "
            "calendar date in the first column"
        ),
        "day_convention": "local_calendar",
        "day_convention_evidence": day_convention_evidence(dato, member, key),
        "attribution": ATTRIBUTION,
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "licence_sources": list(LICENCE_SOURCES),
        "licence_scope": (
            "applies to this observations/smn/ prefix; the dataset-level cc-by-4.0 "
            "tag covers forecasts/ and is a different licence"
        ),
        "hf_target": f"{target_dir(dato, key)}/",
        "hf_upload": upload_status,
        "requests_used": requests_used,
    }
    prior = prior_capture_block(dato, window["first"], manifest["sha256_zip"])
    if prior is not None:
        manifest["prior_capture"] = prior
    run = run_block_from_env(env if env is not None else os.environ)
    if run is not None:
        manifest["github_run"] = run
    return manifest


def plan_uploads(
    dato: str,
    key: str,
    exists: Callable[[str], bool],
) -> tuple[list[str], list[str]]:
    """Split one capture into files to upload and an already-canonical target.

    The payload file gates the whole directory: when it is already present the
    manifest of the frozen first capture is not overwritten either.
    """
    directory = target_dir(dato, key)
    payload_target = f"{directory}/{dato}.zip"
    manifest_target = f"{directory}/manifest.json"
    if exists(payload_target):
        return [], [payload_target]
    return [payload_target, manifest_target], []


def stage_payload(out_root: Path, dato: str, key: str, payload: bytes) -> Path:
    """Write the payload as served under ``<out_root>/<dato>/<key>/``."""
    directory = out_root / dato / key
    directory.mkdir(parents=True, exist_ok=True)
    payload_path = directory / f"{dato}.zip"
    payload_path.write_bytes(payload)
    return payload_path


def stage_manifest(out_root: Path, dato: str, key: str, manifest: Mapping[str, object]) -> Path:
    """Write the manifest next to the payload it describes."""
    directory = out_root / dato / key
    directory.mkdir(parents=True, exist_ok=True)
    manifest_path = directory / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--payloads",
        nargs="+",
        choices=ALL_DATOS,
        default=list(DAILY_DATOS),
        help="payloads to capture (default: the two daily ones)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/observations"),
        help="staging root; raw payloads written here are never committed",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="upload to the Hugging Face dataset (CI only; needs HF_TOKEN and HF_DATASET_REPO)",
    )
    parser.add_argument(
        "--local-zip",
        type=Path,
        default=None,
        help="read a locally captured ZIP instead of fetching (exactly one --payloads entry)",
    )
    parser.add_argument(
        "--retrieved-at",
        default=None,
        help="UTC retrieval instant to record for --local-zip (default: now)",
    )
    args = parser.parse_args(argv)

    if args.local_zip is not None and len(args.payloads) != 1:
        print("--local-zip requires exactly one --payloads entry", file=sys.stderr)
        return 1
    if args.local_zip is not None and not args.local_zip.is_file():
        print(f"local ZIP not found: {args.local_zip}", file=sys.stderr)
        return 1

    token = os.environ.get("HF_TOKEN")
    repo = os.environ.get("HF_DATASET_REPO")
    api = None
    if args.upload:
        if not token or not repo:
            print(
                "HF_TOKEN / HF_DATASET_REPO not configured; observation captures are "
                "uploaded by the workflow in CI, never with a local token.",
                file=sys.stderr,
            )
            return 2
        from huggingface_hub import HfApi  # imported late: only needed when uploading

        api = HfApi(token=token)
        api.create_repo(repo, repo_type="dataset", exist_ok=True)

    failures = 0
    for dato in args.payloads:
        try:
            if args.local_zip is not None:
                payload = args.local_zip.read_bytes()
            else:
                payload = fetch_payload(dato)
            member, text = read_member(payload)
            dates = parse_fechas(text)
            key = key_for(dato, dates)
            fields = fields_of(text)

            if api is not None:
                planned, skipped = plan_uploads(
                    dato, key, lambda target: api.file_exists(repo, target, repo_type="dataset")
                )
                for target in skipped:
                    print(f"skip {target}: already present (first capture is canonical)")
                if not planned:
                    continue

            target = target_dir(dato, key)
            payload_path = stage_payload(args.out, dato, key, payload)
            if api is not None:
                api.upload_file(
                    path_or_fileobj=str(payload_path),
                    path_in_repo=f"{target}/{dato}.zip",
                    repo_id=repo,
                    repo_type="dataset",
                    commit_message=f"observation capture {dato} {key}",
                )
            if args.retrieved_at is not None:
                retrieved_at = datetime.strptime(args.retrieved_at, "%Y-%m-%dT%H:%M:%SZ").replace(
                    tzinfo=UTC
                )
            else:
                retrieved_at = datetime.now(UTC)
            manifest = build_manifest(
                dato=dato,
                member=member,
                key=key,
                dates=dates,
                fields=fields,
                payload=payload,
                retrieved_at=retrieved_at,
                upload_status="uploaded" if api is not None else "staged",
                requests_used=0 if args.local_zip is not None else 1,
            )
            manifest_path = stage_manifest(args.out, dato, key, manifest)
            if api is not None:
                api.upload_file(
                    path_or_fileobj=str(manifest_path),
                    path_in_repo=f"{target}/manifest.json",
                    repo_id=repo,
                    repo_type="dataset",
                    commit_message=f"observation manifest {dato} {key}",
                )
            print(
                f"{dato}: {key} ({len(dates)} rows, {len(set(dates))} day(s)) -> "
                f"{target}/ [{'uploaded' if api else 'staged'}]"
            )
        except Exception as exc:  # noqa: BLE001 - one failed payload must not block the others
            failures += 1
            print(f"{dato}: capture failed: {exc}", file=sys.stderr)
    if failures:
        print(f"{failures} payload(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
