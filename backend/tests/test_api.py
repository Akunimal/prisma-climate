"""FastAPI endpoints: forecast / skill / sources /enso — synthetic fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from fastapi.testclient import TestClient

from prisma.api import create_app

QUANTILE_COLS = [
    "source",
    "variable",
    "unit",
    "location",
    "lat",
    "lon",
    "time",
    "value",
    "quality_flag",
    "member",
    "lead_day",
    "model",
    "day_convention",
    "issue_time",
    "retrieved_at",
]


def _write_region(root: Path) -> None:
    region = {
        "id": "argentina",
        "name": "Argentina",
        "timezone": "America/Argentina/Cordoba",
        "stations": [
            {"id": "ba", "name": "Buenos Aires", "lat": -34.6, "lon": -58.4},
            {"id": "rob", "name": "Rosario", "lat": -32.9, "lon": -60.7},
        ],
    }
    path = root / "configs" / "regions"
    path.mkdir(parents=True, exist_ok=True)
    (path / "argentina.yaml").write_text(yaml.safe_dump(region), encoding="utf-8")


def _write_sources(root: Path) -> None:
    registry = {
        "version": 1,
        "sources": [
            {
                "id": "openmeteo-ensemble",
                "name": "Open-Meteo Ensemble API",
                "tier": 1,
                "status": "active",
                "variables": ["t2m_max"],
                "day_convention": "local_calendar",
                "license": "Open-Meteo CC BY 4.0; free tier is non-commercial only",
                "redistributable": "yes",
                "coverage": "global",
                "update_frequency": "6 hours",
                "verified_on": "2026-11-11",
                "notes": "test",
                "options": {"member_counts": {"gfs_seamless": 31}},
            }
        ],
    }
    path = root / "configs"
    path.mkdir(parents=True, exist_ok=True)
    (path / "sources.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")


def _write_forecast(root: Path) -> None:
    rows = []
    issue = pd.Timestamp("2026-11-11 12:00:00")
    for location, lat, lon in (("Buenos Aires", -34.6, -58.4), ("Rosario", -32.9, -60.7)):
        for model, nominal in (("gfs_seamless", 31), ("ecmwf_ifs025", 51)):
            for lead in (0, 1):
                for member in range(nominal):
                    rows.append(
                        {
                            "source": "openmeteo-ensemble",
                            "variable": "t2m_max",
                            "unit": "degC",
                            "location": location,
                            "lat": lat,
                            "lon": lon,
                            "time": issue + pd.Timedelta(days=lead),
                            "value": 20.0 + member * 0.1 + lead,
                            "quality_flag": "ok",
                            "member": str(member),
                            "lead_day": lead,
                            "model": model,
                            "day_convention": "local_calendar",
                            "issue_time": issue,
                            "retrieved_at": issue,
                        }
                    )
    frame = pd.DataFrame(rows, columns=QUANTILE_COLS)
    path = root / "data" / "raw"
    path.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path / "openmeteo-ensemble.parquet", index=False)


def _write_oni(root: Path) -> None:
    rows = [
        {
            "source": "noaa-oni",
            "variable": "oni",
            "unit": "degC",
            "location": "Nino 3.4",
            "lat": -5.0,
            "lon": -150.0,
            "time": pd.Timestamp("2026-07-01"),
            "value": 1.8,
            "quality_flag": "ok",
            "member": None,
            "lead_day": None,
            "model": None,
            "day_convention": "utc",
            "issue_time": pd.NaT,
            "retrieved_at": pd.Timestamp("2026-11-11"),
        },
        {
            "source": "noaa-oni",
            "variable": "oni",
            "unit": "degC",
            "location": "Nino 3.4",
            "lat": -5.0,
            "lon": -150.0,
            "time": pd.Timestamp("2026-08-01"),
            "value": 0.3,
            "quality_flag": "ok",
            "member": None,
            "lead_day": None,
            "model": None,
            "day_convention": "utc",
            "issue_time": pd.NaT,
            "retrieved_at": pd.Timestamp("2026-11-11"),
        },
    ]
    path = root / "data" / "raw"
    path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(path / "noaa-oni.parquet", index=False)


def _write_skill(root: Path) -> None:
    out = root / "results" / "hindcast"
    out.mkdir(parents=True, exist_ok=True)
    meta = {
        "label": "hindcast",
        "provider": "NOAA GEFS (noaa-gefs-pds)",
        "retrieved_at": "2026-11-15T00:00:00Z",
        "mode": "smoke",
        "window_start": "2026-05-12",
        "window_end": "2026-05-31",
        "leads": [1],
    }
    (out / "crpss_smoke_x.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    cells = [
        {
            "label": "hindcast",
            "station_id": "ba",
            "lead_day": 1,
            "n_train": 10,
            "n_eval": 10,
            "insufficient": False,
            "crps_raw": 2.0,
            "crps_emos": 1.5,
            "crps_qm": 1.8,
            "crpss_emos_vs_raw": 0.25,
            "crpss_qm_vs_raw": 0.1,
        },
        {
            "label": "hindcast",
            "station_id": "rob",
            "lead_day": 1,
            "n_train": 10,
            "n_eval": 2,
            "insufficient": True,
            "crps_raw": 2.0,
            "crps_emos": None,
            "crps_qm": None,
            "crpss_emos_vs_raw": None,
            "crpss_qm_vs_raw": None,
        },
    ]
    pd.DataFrame(cells).to_csv(out / "crpss_smoke_x.csv", index=False)
    (out / "crpss_smoke_x.md").write_text("# hindcast report", encoding="utf-8")


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    _write_region(tmp_path)
    _write_sources(tmp_path)
    _write_forecast(tmp_path)
    _write_oni(tmp_path)
    _write_skill(tmp_path)
    app = create_app(root=tmp_path)
    return TestClient(app)


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_forecast_all_stations(client: TestClient) -> None:
    body = client.get("/forecast").json()
    assert body["issue_date"] == "2026-11-11"
    assert body["calibrated"] is False
    assert body["models"] == ["ecmwf_ifs025", "gfs_seamless"]
    assert len(body["stations"]) == 2
    ba = body["stations"][0]
    cases = ba["forecast"]["t2m_max"]["gfs_seamless"]
    assert len(cases) == 2
    ok = cases[0]
    assert ok["status"] == "ok"
    assert ok["n_members"] == 31
    assert ok["nominal_members"] == 31
    assert ok["p10"] is not None and ok["p90"] is not None
    assert ok["p10"] <= ok["p50"] <= ok["p90"]


def test_forecast_single_station(client: TestClient) -> None:
    body = client.get("/forecast", params={"station_id": "rob"}).json()
    assert len(body["stations"]) == 1
    assert body["stations"][0]["id"] == "rob"


def test_forecast_unknown_station(client: TestClient) -> None:
    assert client.get("/forecast", params={"station_id": "nope"}).status_code == 404


def test_skill_hindcast_label(client: TestClient) -> None:
    body = client.get("/skill").json()
    assert body["label"] == "hindcast"
    assert body["available"] is True
    assert body["provider"] == "NOAA GEFS (noaa-gefs-pds)"
    # mean over sufficient cells only (second cell is insufficient)
    assert body["n_cells"] == 2
    assert body["n_sufficient"] == 1
    assert body["mean_crpss_emos_vs_raw"] == 0.25
    gate = body["gate"]
    assert gate["operational_leaderboard_published"] is False
    assert gate["required_issue_dates"] == 15


def test_skill_missing(tmp_path: Path) -> None:
    _write_region(tmp_path)
    _write_sources(tmp_path)
    client = TestClient(create_app(root=tmp_path))
    body = client.get("/skill").json()
    assert body["available"] is False
    assert body["label"] == "hindcast"


def test_sources(client: TestClient) -> None:
    body = client.get("/sources").json()
    assert body["registry_version"] == 1
    entry = body["sources"][0]
    assert entry["id"] == "openmeteo-ensemble"
    assert entry["redistributable"] == "yes"
    assert "CC BY 4.0" in entry["license"]


def test_enso(client: TestClient) -> None:
    body = client.get("/enso").json()
    assert body["index"] == "oni"
    # latest row is 0.3 → neutral
    assert body["latest"] == {"time": "2026-08-01", "oni": 0.3, "state": "neutral"}
    assert len(body["series"]) == 2


def test_enso_el_nino_state(tmp_path: Path) -> None:
    from prisma.api.app import oni_state

    assert oni_state(1.2) == "el_nino"
    assert oni_state(-0.9) == "la_nina"
    assert oni_state(0.1) == "neutral"


def test_leaderboard_endpoint_locked(client: TestClient) -> None:
    resp = client.get("/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["schema_version"] == "1.0"
    assert body["gate"]["status"] == "locked"
    assert body["gate"]["open"] is False
    assert body["gate"]["operational_leaderboard_published"] is False
    assert body["cells"] == []
    assert body["summary"] is None


def test_leaderboard_endpoint_unlocked(tmp_path: Path) -> None:
    _write_region(tmp_path)
    _write_sources(tmp_path)
    _write_forecast(tmp_path)

    # Provide manifest with >= 15 dates
    manifest = tmp_path / "data" / "raw" / "_manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps([f"2026-11-{i:02d}" for i in range(1, 16)]), encoding="utf-8")

    # Provide leaderboard.csv
    v_dir = tmp_path / "results" / "verification"
    v_dir.mkdir(parents=True, exist_ok=True)
    csv_content = (
        "location,variable,model,lead_day,n_pairs,n_missing,insufficient,"
        "n_climatology,n_persistence,crps_raw,crps_climatology,crps_persistence,"
        "crpss_vs_climatology,crpss_vs_persistence\n"
        "ba,t2m_max,gfs_seamless,1,15,0,False,15,15,1.0,2.0,4.0,0.5,0.75\n"
    )
    (v_dir / "leaderboard.csv").write_text(csv_content, encoding="utf-8")

    client = TestClient(create_app(root=tmp_path))
    resp = client.get("/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gate"]["status"] == "unlocked"
    assert body["gate"]["open"] is True
    assert body["gate"]["operational_leaderboard_published"] is True
    assert body["summary"]["n_cells"] == 1
    assert body["summary"]["mean_crpss_vs_climatology"] == 0.5
    assert len(body["cells"]) == 1
    assert body["cells"][0]["location"] == "ba"


def test_forecast_with_region_filter(client: TestClient, tmp_path: Path) -> None:
    # Add an extra region file
    extra_region = {
        "id": "europe",
        "name": "Europe",
        "timezone": "Europe/Madrid",
        "stations": [
            {"id": "mad", "name": "Madrid", "lat": 40.4, "lon": -3.7},
        ],
    }
    (tmp_path / "configs" / "regions" / "europe.yaml").write_text(
        yaml.safe_dump(extra_region), encoding="utf-8"
    )

    resp_default = client.get("/forecast")
    assert resp_default.status_code == 200
    stations_default = [s["id"] for s in resp_default.json()["stations"]]
    assert "ba" in stations_default
    assert "mad" not in stations_default

    resp_eu = client.get("/forecast", params={"region": "europe"})
    assert resp_eu.status_code == 200
    body_eu = resp_eu.json()
    assert body_eu["region"] == "europe"
    stations_eu = [s["id"] for s in body_eu["stations"]]
    assert stations_eu == ["mad"]


def test_forecast_unknown_region(client: TestClient) -> None:
    resp = client.get("/forecast", params={"region": "atlantis"})
    assert resp.status_code == 404
    assert "unknown region atlantis" in resp.json()["detail"]


def test_forecast_global_region(client: TestClient, tmp_path: Path) -> None:
    extra_region = {
        "id": "oceania",
        "name": "Oceania",
        "timezone": "Australia/Sydney",
        "stations": [
            {"id": "syd", "name": "Sydney", "lat": -33.8, "lon": 151.2},
        ],
    }
    (tmp_path / "configs" / "regions" / "oceania.yaml").write_text(
        yaml.safe_dump(extra_region), encoding="utf-8"
    )

    resp_global = client.get("/forecast", params={"region": "global"})
    assert resp_global.status_code == 200
    st_ids = [s["id"] for s in resp_global.json()["stations"]]
    assert "ba" in st_ids
    assert "syd" in st_ids
