"""Tests for scripts/capture_observations.py: date keying, skip-if-exists, manifest."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
import io
import json
import sys
import types
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "capture_observations.py"

DATOHORARIO_TEXT = (
    "FECHA     HORA  TEMP   HUM   PNM    DD    FF     NOMBRE\n"
    "          [HOA]  [ºC]   [%]  [hPa]  [gr] [km/hr]\n"
    " 12112026     0  23.6   75  1015.4   40   11     AEROPARQUE AERO\n"
    " 12112026     1  23.0   76  1015.2   30   13     AEROPARQUE AERO\n"
)
OBSERVACIONES_TEXT = (
    " FECHA    TMAX  TMIN  NOMBRE\n"
    " -------- ----- ----- ---\n"
    " 10112026  25.1  16.8 AEROPARQUE AERO\n"
    " 10112026  24.7  13.1 AZUL AERO\n"
)
REGTEMP_TEXT = (
    "\nFECHA    TMAX  TMIN  NOMBRE\n"
    "-------- ----- ----- ---\n"
    "10112026  25.1  16.8 AEROPARQUE AERO\n"
    "10112026  24.7  13.1 AZUL AERO\n"
    "09112026  22.0  12.0 AZUL AERO\n"
)


def make_zip(member: str, text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(member, text)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def capture():
    spec = importlib.util.spec_from_file_location("capture_observations", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["capture_observations"] = module
    spec.loader.exec_module(module)
    return module


def test_daily_key_is_read_from_the_payload_not_the_clock(capture) -> None:
    """The key comes from FECHA; the keying function takes no clock at all."""
    assert set(inspect.signature(capture.key_for).parameters) == {"dato", "dates"}
    key = capture.key_for("datohorario", capture.parse_fechas(DATOHORARIO_TEXT))
    assert key == "2026-11-12"
    assert key != datetime.now(UTC).strftime("%Y-%m-%d")


def test_observaciones_key_is_the_served_local_day(capture) -> None:
    key = capture.key_for("observaciones", capture.parse_fechas(OBSERVACIONES_TEXT))
    assert key == "2026-11-10"


def test_regtemp_key_is_the_last_fecha_of_the_window(capture) -> None:
    dates = capture.parse_fechas(REGTEMP_TEXT)
    assert capture.key_for("regtemp", dates) == "2026-11-10"
    assert capture.parse_fechas(REGTEMP_TEXT)[0].isoformat() == "2026-11-10"
    assert min(dates).isoformat() == "2026-11-09"


def test_regtemp_ignores_the_earlier_days_of_the_window(capture) -> None:
    dates = capture.parse_fechas(REGTEMP_TEXT)
    assert capture.key_for("regtemp", dates) != "2026-11-09"


def test_daily_payload_spanning_two_days_is_rejected(capture) -> None:
    text = OBSERVACIONES_TEXT + " 11112026  20.0  10.0 AZUL AERO\n"
    with pytest.raises(ValueError, match="distinct FECHA"):
        capture.key_for("observaciones", capture.parse_fechas(text))


def test_payload_without_fecha_is_rejected(capture) -> None:
    with pytest.raises(ValueError, match="no parseable FECHA"):
        capture.key_for("regtemp", capture.parse_fechas("FECHA TMAX TMIN NOMBRE\n"))


def test_targets_live_under_observations_never_forecasts(capture) -> None:
    for dato, key in (
        ("regtemp", "2026-11-10"),
        ("datohorario", "2026-11-12"),
        ("observaciones", "2026-11-10"),
    ):
        target = capture.target_dir(dato, key)
        assert target.startswith("observations/smn/")
        assert "forecasts" not in target


def test_malformed_capture_date_is_refused(capture) -> None:
    with pytest.raises(ValueError, match="malformed"):
        capture.target_dir("regtemp", "12-11-2026")


def test_plan_uploads_skips_an_existing_capture(capture) -> None:
    planned, skipped = capture.plan_uploads("regtemp", "2026-11-10", lambda _target: True)
    assert planned == []
    assert skipped == [
        "observations/smn/regtemp/2026-11-10/regtemp.zip",
        "observations/smn/regtemp/2026-11-10/manifest.json",
    ]


def test_plan_uploads_lists_payload_and_manifest_for_a_new_capture(capture) -> None:
    planned, skipped = capture.plan_uploads("datohorario", "2026-11-12", lambda _target: False)
    assert planned == [
        "observations/smn/datohorario/2026-11-12/datohorario.zip",
        "observations/smn/datohorario/2026-11-12/manifest.json",
    ]
    assert skipped == []


def test_plan_uploads_never_skips_a_folder_with_only_the_payload(capture) -> None:
    """A failed second upload left payload-only folders; skip must not hide them."""
    payload = "observations/smn/datohorario/2026-11-12/datohorario.zip"
    planned, skipped = capture.plan_uploads(
        "datohorario", "2026-11-12", lambda target: target == payload
    )
    assert planned == [
        payload,
        "observations/smn/datohorario/2026-11-12/manifest.json",
    ]
    assert skipped == []


def test_plan_uploads_never_skips_a_folder_with_only_the_manifest(capture) -> None:
    manifest = "observations/smn/observaciones/2026-11-10/manifest.json"
    planned, skipped = capture.plan_uploads(
        "observaciones", "2026-11-10", lambda target: target == manifest
    )
    assert planned == [
        "observations/smn/observaciones/2026-11-10/observaciones.zip",
        manifest,
    ]
    assert skipped == []


def _manifest(capture, *, dato: str, member: str, text: str, retrieved_at: str):
    payload = make_zip(member, text)
    dates = capture.parse_fechas(text)
    return capture.build_manifest(
        dato=dato,
        member=member,
        key=capture.key_for(dato, dates),
        dates=dates,
        fields=capture.fields_of(text),
        payload=payload,
        retrieved_at=datetime.strptime(retrieved_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC),
        upload_status="staged",
        requests_used=1,
        env={},
    )


def test_manifest_holds_every_required_field(capture) -> None:
    text = REGTEMP_TEXT
    manifest = _manifest(
        capture,
        dato="regtemp",
        member="registro_temperatura365d_smn.txt",
        text=text,
        retrieved_at="2026-11-12T01:41:32Z",
    )
    assert manifest["retrieved_at"] == "2026-11-12T01:41:32Z"
    assert manifest["endpoint"].endswith("dato=regtemp")
    assert manifest["served_window"] == {
        "first": "2026-11-09",
        "last": "2026-11-10",
        "distinct_days": 2,
    }
    assert manifest["data_rows"] == 3
    expected_sha = hashlib.sha256(make_zip("registro_temperatura365d_smn.txt", text)).hexdigest()
    assert manifest["sha256_zip"] == expected_sha
    assert manifest["fields"] == ["FECHA", "TMAX", "TMIN", "NOMBRE"]
    assert manifest["day_convention"] == "local_calendar"
    assert "DDMMYYYY" in manifest["day_convention_evidence"]
    assert manifest["attribution"] == "Servicio Meteorológico Nacional (SMN Argentina)"
    assert manifest["licence"] == "CC BY 2.5 AR"
    assert manifest["licence_url"] == (
        "https://creativecommons.org/licenses/by/2.5/ar/legalcode"
    )
    assert manifest["hf_target"] == "observations/smn/regtemp/2026-11-10/"
    assert manifest["hf_upload"] == "staged"
    assert manifest["capture_key"] == "2026-11-10"
    assert "payload_member" in manifest
    json.dumps(manifest)  # must be serialisable as written to disk


def test_manifest_of_the_prior_capture_records_the_later_window_start(capture) -> None:
    manifest = _manifest(
        capture,
        dato="regtemp",
        member="registro_temperatura365d_smn.txt",
        text=REGTEMP_TEXT,
        retrieved_at="2026-11-17T04:34:00Z",
    )
    prior = manifest["prior_capture"]
    assert prior["window_starts_later"] is True
    assert prior["gap_days"] == 363  # 2026-11-09 vs the capture window's 2025-11-11
    assert "later than the 2026-11-12 capture" in prior["note"]
    assert prior["target"] == "observations/smn/regtemp/2026-11-10/"


def test_the_prior_capture_itself_is_not_compared_with_itself(
    capture, monkeypatch
) -> None:
    payload = make_zip("registro_temperatura365d_smn.txt", REGTEMP_TEXT)
    monkeypatch.setitem(capture.PRIOR_CAPTURE, "sha256_zip", hashlib.sha256(payload).hexdigest())
    dates = capture.parse_fechas(REGTEMP_TEXT)
    manifest = capture.build_manifest(
        dato="regtemp",
        member="registro_temperatura365d_smn.txt",
        key=capture.key_for("regtemp", dates),
        dates=dates,
        fields=capture.fields_of(REGTEMP_TEXT),
        payload=payload,
        retrieved_at=datetime(2026, 11, 12, 1, 41, 32, tzinfo=UTC),
        upload_status="staged",
        env={},
    )
    assert "prior_capture" not in manifest


def test_daily_manifest_carries_no_prior_capture_block(capture) -> None:
    manifest = _manifest(
        capture,
        dato="datohorario",
        member="datohorario20261112.txt",
        text=DATOHORARIO_TEXT,
        retrieved_at="2026-11-13T07:17:00Z",
    )
    assert "prior_capture" not in manifest
    assert manifest["served_window"]["first"] == "2026-11-12"
    assert manifest["fields"][0] == "FECHA"


def test_manifest_records_the_actions_run_that_wrote_it(capture) -> None:
    manifest = _manifest(
        capture,
        dato="observaciones",
        member="observaciones20261110.txt",
        text=OBSERVACIONES_TEXT,
        retrieved_at="2026-11-13T07:17:00Z",
    )
    assert "github_run" not in manifest
    run = capture.run_block_from_env(
        {
            "GITHUB_RUN_ID": "43470000001",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": "schedule",
            "SCHEDULED_CRON": "17 7 * * *",
            "GITHUB_SHA": "c954fbf000000000000000000000000000000000",
            "GITHUB_REPOSITORY": "Akunimal/prisma-climate",
            "GITHUB_WORKFLOW": "Observation archive (SMN)",
        }
    )
    assert run is not None
    assert run["run_id"] == "43470000001"
    assert run["event"] == "schedule"
    assert run["scheduled_cron"] == "17 7 * * *"
    assert run["run_url"].endswith("/actions/runs/43470000001")
    assert capture.run_block_from_env({}) is None


def test_endpoints_are_ssl_smn_only(capture) -> None:
    for dato in capture.ALL_DATOS:
        assert capture.url_for(dato).startswith("https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=")
    with pytest.raises(ValueError, match="unknown payload"):
        capture.url_for("estaciones")
    with pytest.raises(ValueError, match="unknown payload"):
        capture.url_for("precipitacion")


def test_fetch_is_one_plain_request_to_ssl_smn(capture) -> None:
    calls: list[str] = []

    class FakeResponse:
        content = make_zip("observaciones20261110.txt", OBSERVACIONES_TEXT)

        def raise_for_status(self) -> None:
            return None

    def fake_get(url: str, timeout: int) -> FakeResponse:
        calls.append(url)
        assert timeout == 60
        return FakeResponse()

    payload = capture.fetch_payload("observaciones", get=fake_get)
    assert calls == ["https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=observaciones"]
    assert payload == FakeResponse.content


def test_main_requires_the_actions_secret_to_upload(tmp_path: Path, monkeypatch, capture) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    zip_path = tmp_path / "regtemp.zip"
    zip_path.write_bytes(make_zip("registro_temperatura365d_smn.txt", REGTEMP_TEXT))
    code = capture.main(
        ["--payloads", "regtemp", "--local-zip", str(zip_path), "--out", str(tmp_path), "--upload"]
    )
    assert code == 2


def test_main_stages_locally_without_touching_hugging_face(
    tmp_path: Path, monkeypatch, capture
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HF_DATASET_REPO", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    zip_path = tmp_path / "src.zip"
    zip_path.write_bytes(make_zip("datohorario20261112.txt", DATOHORARIO_TEXT))
    out = tmp_path / "staged"
    code = capture.main(
        [
            "--payloads",
            "datohorario",
            "--local-zip",
            str(zip_path),
            "--out",
            str(out),
            "--retrieved-at",
            "2026-11-13T07:17:00Z",
        ]
    )
    assert code == 0
    payload = out / "datohorario" / "2026-11-12" / "datohorario.zip"
    manifest = out / "datohorario" / "2026-11-12" / "manifest.json"
    assert payload.is_file() and manifest.is_file()
    body = json.loads(manifest.read_text(encoding="utf-8"))
    assert body["capture_key"] == "2026-11-12"
    assert body["retrieved_at"] == "2026-11-13T07:17:00Z"
    assert body["hf_upload"] == "staged"
    assert body["requests_used"] == 0
    assert "github_run" not in body
    assert payload.read_bytes() == zip_path.read_bytes()


def test_main_uploads_once_and_repeats_are_a_noop(
    tmp_path: Path, monkeypatch, capture
) -> None:
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("HF_DATASET_REPO", "Akunimal/prisma-climate")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    zip_path = tmp_path / "src.zip"
    zip_path.write_bytes(make_zip("observaciones20261110.txt", OBSERVACIONES_TEXT))
    out = tmp_path / "staged"

    class FakeHfApi:
        present: set[str] = set()
        commits: list[list[str]] = []

        def __init__(self, token: str | None = None) -> None:
            self.token = token

        def create_repo(self, repo: str, repo_type: str | None = None, exist_ok: bool = False):
            return None

        def file_exists(self, repo: str, target: str, repo_type: str | None = None) -> bool:
            return target in self.present

        def upload_folder(
            self, folder_path: str, path_in_repo: str, **_kwargs
        ) -> None:
            files = sorted(p.name for p in Path(folder_path).iterdir())
            self.commits.append([f"{path_in_repo}/{name}" for name in files])
            self.present.update(f"{path_in_repo}/{name}" for name in files)

    FakeHfApi.present.clear()
    FakeHfApi.commits.clear()
    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.HfApi = FakeHfApi  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    argv = [
        "--payloads",
        "observaciones",
        "--local-zip",
        str(zip_path),
        "--out",
        str(out),
        "--upload",
    ]
    assert capture.main(argv) == 0
    assert FakeHfApi.commits == [
        [
            "observations/smn/observaciones/2026-11-10/manifest.json",
            "observations/smn/observaciones/2026-11-10/observaciones.zip",
        ]
    ], "payload and manifest must leave in one commit"
    assert capture.main(argv) == 0
    assert len(FakeHfApi.commits) == 1, "a repeat must not commit the canonical capture again"
    assert all(path.startswith("observations/smn/") for c in FakeHfApi.commits for path in c)
    assert all("forecasts" not in path for c in FakeHfApi.commits for path in c)
    body = json.loads(
        (out / "observaciones" / "2026-11-10" / "manifest.json").read_text(encoding="utf-8")
    )
    assert body["hf_upload"] == "uploaded"
    assert body["requests_used"] == 0


def test_main_completes_a_half_written_folder_in_one_commit(
    tmp_path: Path, monkeypatch, capture
) -> None:
    """payload already on HF, manifest missing: the next run must repair it."""
    monkeypatch.setenv("HF_TOKEN", "test-token")
    monkeypatch.setenv("HF_DATASET_REPO", "Akunimal/prisma-climate")
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    zip_path = tmp_path / "src.zip"
    zip_path.write_bytes(make_zip("observaciones20261110.txt", OBSERVACIONES_TEXT))
    out = tmp_path / "staged"

    class HalfWrittenApi:
        present: set[str] = {"observations/smn/observaciones/2026-11-10/observaciones.zip"}
        commits: list[list[str]] = []

        def __init__(self, token: str | None = None) -> None:
            self.token = token

        def create_repo(self, repo: str, repo_type: str | None = None, exist_ok: bool = False):
            return None

        def file_exists(self, repo: str, target: str, repo_type: str | None = None) -> bool:
            return target in self.present

        def upload_folder(
            self, folder_path: str, path_in_repo: str, **_kwargs
        ) -> None:
            files = sorted(p.name for p in Path(folder_path).iterdir())
            self.commits.append([f"{path_in_repo}/{name}" for name in files])
            self.present.update(f"{path_in_repo}/{name}" for name in files)

    HalfWrittenApi.present = {
        "observations/smn/observaciones/2026-11-10/observaciones.zip"
    }
    HalfWrittenApi.commits = []
    fake_hub = types.ModuleType("huggingface_hub")
    fake_hub.HfApi = HalfWrittenApi  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake_hub)

    argv = [
        "--payloads",
        "observaciones",
        "--local-zip",
        str(zip_path),
        "--out",
        str(out),
        "--upload",
    ]
    assert capture.main(argv) == 0
    assert len(HalfWrittenApi.commits) == 1, "the repair must be exactly one commit"
    manifest_target = "observations/smn/observaciones/2026-11-10/manifest.json"
    assert manifest_target in HalfWrittenApi.present, "the half-written folder must be completed"
    # A repeat now sees both files and must be a no-op.
    assert capture.main(argv) == 0
    assert len(HalfWrittenApi.commits) == 1
