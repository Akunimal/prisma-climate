"""Tests for scripts/export_site_data.py: tree, 80 % rule, quantiles, licence block.

Every fixture is synthetic: a temporary repository root with its own
``configs/`` and ``results/`` files, a hand-built forecast parquet and a
hand-built regtemp ZIP in the served fixed-width layout. No network is used and
no real archive is read.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "export_site_data.py"

SOURCES_YAML = """\
version: 1
sources:
  - id: openmeteo-ensemble
    options:
      member_counts: {gfs_seamless: 5, ecmwf_ifs025: 4}
"""

REGION_YAML = """\
id: testland
name: Testland
timezone: America/Argentina/Cordoba
stations:
  - id: estacion_uno
    name: "Estacion Uno"
    zone: "Test zone"
    lat: -1.0
    lon: -2.0
  - id: estacion_dos
    name: "Estacion Dos"
    zone: "Other zone"
    lat: -3.0
    lon: -4.0
"""

RESOLUTION_CSV = """\
location,smn_nro,smn_name,catalogue_name,regtemp_name,days,status
Estacion Uno,1,U1,U1,ESTACION UNO,365,resolved
Estacion Dos,2,U2,U2,ESTACION DOS,365,resolved
"""


@pytest.fixture(scope="module")
def export():
    spec = importlib.util.spec_from_file_location("export_site_data", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["export_site_data"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "configs" / "regions").mkdir(parents=True)
    (root / "results" / "regtemp_names").mkdir(parents=True)
    (root / "configs" / "sources.yaml").write_text(SOURCES_YAML, encoding="utf-8")
    (root / "configs" / "regions" / "argentina.yaml").write_text(
        REGION_YAML, encoding="utf-8"
    )
    (root / "results" / "regtemp_names" / "region_resolution.csv").write_text(
        RESOLUTION_CSV, encoding="utf-8"
    )
    return root


def _forecast(rows: list[dict[str, Any]], issue: str = "2026-11-14 00:16:46") -> pd.DataFrame:
    records = [
        {
            "source": "openmeteo-ensemble",
            "unit": "degC",
            "variable": row["variable"],
            "location": row["location"],
            "lat": -1.0,
            "lon": -2.0,
            "time": pd.Timestamp(row["time"]),
            "value": row["value"],
            "quality_flag": row.get("flag", "ok"),
            "member": row["member"],
            "lead_day": row["lead_day"],
            "model": row["model"],
            "day_convention": "local_calendar",
            "issue_time": pd.Timestamp(issue),
            "retrieved_at": pd.Timestamp(issue),
        }
        for row in rows
    ]
    return pd.DataFrame.from_records(records)


def _case(
    location: str,
    variable: str,
    model: str,
    lead_day: int,
    day: str,
    values: list[float],
    flag: str = "ok",
) -> list[dict[str, Any]]:
    return [
        {
            "location": location,
            "variable": variable,
            "model": model,
            "lead_day": lead_day,
            "time": day,
            "value": value,
            "member": index,
            "flag": flag,
        }
        for index, value in enumerate(values)
    ]


def _standard_frame() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    rows += _case("Estacion Uno", "t2m_max", "gfs_seamless", 0, "2026-11-13", [10, 11, 12, 13, 14])
    rows += _case("Estacion Uno", "t2m_max", "gfs_seamless", 1, "2026-11-14", [12, 13, 14, 15, 16])
    rows += _case("Estacion Uno", "t2m_min", "gfs_seamless", 0, "2026-11-13", [0, 1, 2, 3, 4])
    rows += _case("Estacion Uno", "precip", "gfs_seamless", 0, "2026-11-13", [0, 0.5, 2, 10, 15])
    rows += _case("Estacion Uno", "t2m_max", "ecmwf_ifs025", 0, "2026-11-13", [20, 21, 22, 23])
    rows += _case("Estacion Uno", "t2m_min", "ecmwf_ifs025", 0, "2026-11-13", [5, 6, 7])
    rows += _case("Estacion Dos", "t2m_max", "gfs_seamless", 0, "2026-11-13", [30, 31, 32, 33, 34])
    return _forecast(rows)


def _regtemp_line(day: str, tmax: float | None, tmin: float | None, name: str) -> str:
    tmax_text = "     " if tmax is None else f"{tmax:>5.1f}"
    tmin_text = "     " if tmin is None else f"{tmin:>5.1f}"
    return f"{day}  {tmax_text} {tmin_text} {name}"


def _write_regtemp_zip(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(["FECHA    TMAX  TMIN NOMBRE", *lines])
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("registro_temperatura365d_smn.txt", payload.encode("latin-1"))
    return path


def _regtemp_days(count: int = 40) -> list[str]:
    start = pd.Timestamp("2026-10-04")
    lines = []
    for offset in range(count):
        day = start + pd.Timedelta(days=offset)
        lines.append(
            _regtemp_line(day.strftime("%d%m%Y"), 20.0 + offset, 10.0 + offset, "ESTACION UNO")
        )
        lines.append(
            _regtemp_line(day.strftime("%d%m%Y"), 30.0, 15.0, "ESTACION DOS")
        )
    return lines


def _paths() -> list[str]:
    return [
        "forecasts/2026-11-14/openmeteo-ensemble_2026-11-14.parquet",
        "observations/smn/regtemp/2026-11-12/regtemp.zip",
    ]


def _run_export(
    export,
    workspace: Path,
    tmp_path: Path,
    frame: pd.DataFrame | None = None,
    lines: list[str] | None = None,
    listing: list[str] | None = None,
    generated_at: str = "2026-11-14T03:00:00Z",
) -> tuple[Path, list[Path], Path]:
    forecast_path = tmp_path / "forecast.parquet"
    (frame if frame is not None else _standard_frame()).to_parquet(forecast_path, index=False)
    zip_path = _write_regtemp_zip(tmp_path / "regtemp.zip", lines or _regtemp_days())

    def download(repo_id: str, repo_path: str) -> Path:
        return forecast_path if repo_path.endswith(".parquet") else zip_path

    out = tmp_path / "data"
    written = export.export_site_data(
        root=workspace,
        list_files=lambda: list(listing or _paths()),
        download=download,
        out_dir=out,
        generated_at=generated_at,
    )
    return out, written, forecast_path


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _keys(document: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(document, dict):
        for key, value in document.items():
            found.add(str(key).lower())
            found |= _keys(value)
    elif isinstance(document, list):
        for value in document:
            found |= _keys(value)
    return found


def test_member_share_ok_boundaries(export) -> None:
    assert export.member_share_ok(24, 31) is False
    assert export.member_share_ok(25, 31) is True
    assert export.member_share_ok(40, 51) is False
    assert export.member_share_ok(41, 51) is True
    assert export.member_share_ok(3, 5) is False
    assert export.member_share_ok(4, 5) is True


def test_latest_forecast_picks_the_newest_date(export) -> None:
    listing = [
        "forecasts/2026-11-12/openmeteo-ensemble_2026-11-12.parquet",
        "forecasts/2026-11-14/openmeteo-ensemble_2026-11-14.parquet",
        "forecasts/2026-11-13/README.md",
    ]
    assert export.latest_forecast(listing) == (
        "2026-11-14",
        "forecasts/2026-11-14/openmeteo-ensemble_2026-11-14.parquet",
    )


def test_latest_forecast_rejects_duplicates_and_empty_listing(export) -> None:
    with pytest.raises(ValueError, match="one canonical forecast"):
        export.latest_forecast(
            [
                "forecasts/2026-11-14/a.parquet",
                "forecasts/2026-11-14/b.parquet",
            ]
        )
    with pytest.raises(ValueError, match="no forecasts/"):
        export.latest_forecast(["observations/smn/regtemp/2026-11-12/regtemp.zip"])


def test_latest_regtemp_picks_the_newest_snapshot(export) -> None:
    listing = [
        "observations/smn/regtemp/2026-11-05/regtemp.zip",
        "observations/smn/regtemp/2026-11-12/regtemp.zip",
        "observations/smn/regtemp/2026-11-12/manifest.json",
        "observations/smn/observaciones/2026-11-20/observaciones.zip",
    ]
    assert export.latest_regtemp(listing) == (
        "2026-11-12",
        "observations/smn/regtemp/2026-11-12/regtemp.zip",
    )


def test_latest_regtemp_rejects_an_empty_listing(export) -> None:
    with pytest.raises(ValueError, match="no observations/smn/regtemp/"):
        export.latest_regtemp(["forecasts/2026-11-14/openmeteo-ensemble_2026-11-14.parquet"])


def test_forecast_cases_quantiles_per_model(export) -> None:
    frame = _standard_frame()
    station = frame.loc[frame["location"].eq("Estacion Uno")]
    cases = export.forecast_cases(
        station, ["ecmwf_ifs025", "gfs_seamless"], {"gfs_seamless": 5, "ecmwf_ifs025": 4}
    )

    first = cases["t2m_max"]["gfs_seamless"][0]
    assert first["lead_day"] == 0
    assert first["valid_local_date"] == "2026-11-13"
    assert first["n_members"] == 5
    assert first["nominal_members"] == 5
    assert first["status"] == "ok"
    assert first["p10"] == 10.4
    assert first["p25"] == 11.0
    assert first["p50"] == 12.0
    assert first["p75"] == 13.0
    assert first["p90"] == 13.6
    assert first["min"] == 10.0
    assert first["max"] == 14.0

    assert cases["t2m_max"]["gfs_seamless"][1]["valid_local_date"] == "2026-11-14"


def test_forecast_cases_apply_the_80_percent_rule(export) -> None:
    frame = _standard_frame()
    station = frame.loc[frame["location"].eq("Estacion Uno")]
    cases = export.forecast_cases(
        station, ["ecmwf_ifs025", "gfs_seamless"], {"gfs_seamless": 5, "ecmwf_ifs025": 4}
    )
    missing = cases["t2m_min"]["ecmwf_ifs025"][0]
    assert missing["status"] == "missing_members"
    assert missing["n_members"] == 3
    assert missing["nominal_members"] == 4
    assert missing["p10"] is None
    assert missing["p50"] is None
    assert missing["max"] is None
    assert "fraction_ge_1mm" not in missing


def test_forecast_cases_exclude_non_ok_members(export) -> None:
    rows = _case("Estacion Uno", "t2m_max", "gfs_seamless", 0, "2026-11-13", [1, 2, 3, 4, 5])
    rows[3]["flag"] = "suspect"
    rows[4]["flag"] = "fail"
    frame = _forecast(rows)
    cases = export.forecast_cases(
        frame, ["gfs_seamless"], {"gfs_seamless": 5}
    )
    case = cases["t2m_max"]["gfs_seamless"][0]
    assert case["n_members"] == 3
    assert case["status"] == "missing_members"
    assert case["p50"] is None


def test_forecast_cases_precip_fractions(export) -> None:
    frame = _standard_frame()
    station = frame.loc[frame["location"].eq("Estacion Uno")]
    cases = export.forecast_cases(
        station, ["gfs_seamless"], {"gfs_seamless": 5}
    )
    case = cases["precip"]["gfs_seamless"][0]
    assert case["fraction_ge_1mm"] == 0.6
    assert case["fraction_ge_10mm"] == 0.4


def test_forecast_cases_reject_two_dates_in_one_case(export) -> None:
    rows = _case("Estacion Uno", "t2m_max", "gfs_seamless", 0, "2026-11-13", [1, 2, 3, 4, 5])
    rows += _case("Estacion Uno", "t2m_max", "gfs_seamless", 0, "2026-11-14", [1, 2, 3, 4, 5])
    with pytest.raises(ValueError, match="exactly one is required"):
        export.forecast_cases(_forecast(rows), ["gfs_seamless"], {"gfs_seamless": 5})


def test_observed_series_takes_the_last_30_days(export, tmp_path: Path) -> None:
    zip_path = _write_regtemp_zip(tmp_path / "regtemp.zip", _regtemp_days())
    frame = export._parse_payload_zip(zip_path, "regtemp")
    series = export.observed_series(frame, "ESTACION UNO")
    assert len(series) == 30
    assert series[0]["date"] == "2026-10-14"
    assert series[-1]["date"] == "2026-11-12"
    assert series[-1]["t2m_max"] == 59.0
    assert export.observed_series(frame, "DESCONOCIDA") == []
    assert export.observed_series(frame, None) == []


def test_observed_series_keeps_gaps_null(export, tmp_path: Path) -> None:
    lines = [
        _regtemp_line("10112026", 25.0, 12.0, "ESTACION UNO"),
        _regtemp_line("11112026", None, 11.0, "ESTACION UNO"),
    ]
    zip_path = _write_regtemp_zip(tmp_path / "regtemp.zip", lines)
    frame = export._parse_payload_zip(zip_path, "regtemp")
    series = export.observed_series(frame, "ESTACION UNO")
    assert series[0]["t2m_max"] == 25.0
    assert series[1]["t2m_max"] is None
    assert series[1]["t2m_min"] == 11.0


def test_export_writes_the_tree(export, workspace: Path, tmp_path: Path) -> None:
    out, written, _ = _run_export(export, workspace, tmp_path)

    assert sorted(path.name for path in written) == [
        "about.json",
        "estacion_dos.json",
        "estacion_uno.json",
        "latest.json",
    ]

    latest = _read(out / "latest.json")
    assert latest["schema_version"] == "1.0"
    assert latest["generated_at"] == "2026-11-14T03:00:00Z"
    assert latest["issue_date"] == "2026-11-14"
    assert latest["issue_time"] == "2026-11-14T00:16:46Z"
    assert latest["models"] == ["ecmwf_ifs025", "gfs_seamless"]
    assert latest["stations"] == [
        {
            "id": "estacion_uno",
            "name": "Estacion Uno",
            "lat": -1.0,
            "lon": -2.0,
            "climate_zone": "Test zone",
        },
        {
            "id": "estacion_dos",
            "name": "Estacion Dos",
            "lat": -3.0,
            "lon": -4.0,
            "climate_zone": "Other zone",
        },
    ]

    about = _read(out / "about.json")
    sources = {source["id"]: source for source in about["sources"]}
    assert sources["openmeteo-ensemble"]["licence"] == "CC BY 4.0"
    assert sources["openmeteo-ensemble"]["attribution"] == "Weather data by Open-Meteo.com"
    assert sources["smn-argentina"]["licence"] == "CC BY 2.5 AR"
    assert about["status"]["smn_snapshot_date"] == "2026-11-12"
    assert "15-issue-date gate" in about["status"]["verification"]
    assert "not calibrated" in about["status"]["forecasts"]


def test_export_station_document(export, workspace: Path, tmp_path: Path) -> None:
    out, _written, _path = _run_export(export, workspace, tmp_path)
    document = _read(out / "stations" / "estacion_uno.json")

    assert document["station"]["id"] == "estacion_uno"
    assert document["issue_time"] == "2026-11-14T00:16:46Z"
    assert document["models"] == ["ecmwf_ifs025", "gfs_seamless"]

    forecast = document["forecast"]
    assert set(forecast) == {"t2m_max", "t2m_min", "precip"}
    assert [case["lead_day"] for case in forecast["t2m_max"]["gfs_seamless"]] == [0, 1]
    assert forecast["t2m_max"]["ecmwf_ifs025"][0]["p50"] == 21.5
    assert forecast["t2m_min"]["ecmwf_ifs025"][0]["status"] == "missing_members"
    assert forecast["t2m_min"]["gfs_seamless"][0]["p50"] == 2.0
    assert forecast["precip"]["gfs_seamless"][0]["fraction_ge_1mm"] == 0.6
    assert forecast["precip"]["ecmwf_ifs025"] == []

    assert len(document["observed"]) == 30
    assert document["observed"][-1]["date"] == "2026-11-12"


def test_export_second_station_has_no_ecmwf_cases(export, workspace: Path, tmp_path: Path) -> None:
    out, _written, _path = _run_export(export, workspace, tmp_path)
    document = _read(out / "stations" / "estacion_dos.json")
    assert document["forecast"]["t2m_max"]["gfs_seamless"][0]["p50"] == 32.0
    assert document["forecast"]["t2m_max"]["ecmwf_ifs025"] == []
    assert document["observed"][-1]["t2m_max"] == 30.0


def test_export_rejects_issue_date_mismatch(export, workspace: Path, tmp_path: Path) -> None:
    frame = _standard_frame()
    frame["issue_time"] = pd.Timestamp("2026-11-13 12:00:00")
    with pytest.raises(ValueError, match="does not match the issue-date folder"):
        _run_export(export, workspace, tmp_path, frame=frame)


def test_export_rejects_unknown_model(export, workspace: Path, tmp_path: Path) -> None:
    rows = _case("Estacion Uno", "t2m_max", "modelo_desconocido", 0, "2026-11-13", [1, 2, 3])
    frame = _forecast(rows)
    with pytest.raises(ValueError, match="no nominal member count for model"):
        _run_export(export, workspace, tmp_path, frame=frame)


def test_export_warns_but_writes_when_a_station_has_no_rows(
    export, workspace: Path, tmp_path: Path, capsys
) -> None:
    frame = _standard_frame()
    frame = frame.loc[frame["location"].eq("Estacion Uno")]
    out, _written, _path = _run_export(export, workspace, tmp_path, frame=frame)
    assert "no forecast rows for station estacion_dos" in capsys.readouterr().out
    document = _read(out / "stations" / "estacion_dos.json")
    assert document["forecast"]["t2m_max"]["gfs_seamless"] == []


def test_export_carries_no_skill_metric_fields(export, workspace: Path, tmp_path: Path) -> None:
    out, written, _path = _run_export(export, workspace, tmp_path)
    forbidden = {"crps", "crpss", "brier", "reliability", "coverage", "skill", "leaderboard"}
    for path in written:
        found = _keys(_read(path))
        assert not (found & forbidden), f"{path.name} exposes a skill-metric field"
    assert out.exists()


def test_main_prints_the_written_count(export, workspace: Path, tmp_path: Path, capsys) -> None:
    out = tmp_path / "site"
    forecast_path = tmp_path / "forecast.parquet"
    _standard_frame().to_parquet(forecast_path, index=False)
    zip_path = _write_regtemp_zip(tmp_path / "regtemp.zip", _regtemp_days())

    def download(repo_id: str, repo_path: str) -> Path:
        return forecast_path if repo_path.endswith(".parquet") else zip_path

    code = export.main(
        ["--root", str(workspace), "--out-dir", str(out)],
        list_files=lambda: list(_paths()),
        download=download,
    )
    assert code == 0
    assert "wrote 4 file(s)" in capsys.readouterr().out
    assert (out / "stations" / "estacion_uno.json").is_file()
