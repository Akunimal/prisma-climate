"""SMN-leg diagnostics tests (T26a 1.0b) — fixture-based, no network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prisma.report.smn_leg import (
    parse_catalogue_nro_names,
    parse_regtemp,
    resolve_region_stations,
)
from prisma.report.smn_leg_diagnostics import (
    build_diagnostics,
    pair_sources,
    render_diagnostics_markdown,
)


def _regtemp_line(fecha: str, tmax: str, tmin: str, nombre: str) -> str:
    return f"{fecha:<8}{tmax:>6}{tmin:>6} {nombre}"


def _write_regtemp(path: Path, lines: list[str]) -> Path:
    path.write_text(
        "\n".join(
            [
                "",
                "FECHA    TMAX  TMIN  NOMBRE",
                "-------- ----- ----- ----------------------------------------",
                *lines,
                "",
            ]
        ),
        encoding="latin-1",
    )
    return path


def _catalogue_line(name: str, nro: str) -> str:
    return name.ljust(110) + nro.rjust(5) + " "


def _resolution(location: str, status: str = "resolved") -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "location": location,
                "ghcn_id": "AR000875850",
                "smn_nro": "87585",
                "catalogue_name": "BUENOS AIRES OBSERVATORIO",
                "regtemp_name": "BUENOS AIRES OBSERVATORIO" if status != "not_in_regtemp" else "",
                "match_status": status,
            }
        ]
    )


def _era5(*rows: tuple[str, str, str, float]) -> pd.DataFrame:
    """rows: (location, variable, day, value)."""
    return pd.DataFrame.from_records(
        [
            {
                "location": location,
                "variable": variable,
                "time": pd.Timestamp(day),
                "value": value,
                "quality_flag": "ok",
            }
            for location, variable, day, value in rows
        ]
    )


def test_pair_and_bias_sign_is_era5_minus_smn() -> None:
    regtemp = pd.DataFrame.from_records(
        [
            {
                "regtemp_name": "BUENOS AIRES OBSERVATORIO",
                "time": pd.Timestamp("2026-01-01"),
                "t2m_max": 30.0,
                "t2m_min": 20.0,
            },
            {
                "regtemp_name": "BUENOS AIRES OBSERVATORIO",
                "time": pd.Timestamp("2026-01-02"),
                "t2m_max": 32.0,
                "t2m_min": 22.0,
            },
        ]
    )
    era5 = _era5(
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", 28.0),
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", 30.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-01", 19.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-02", 21.0),
    )
    resolution = _resolution("Buenos Aires Observatorio")
    frame = build_diagnostics(era5, regtemp, resolution)
    row = frame.iloc[0]
    # SMN is warmer (30/32 vs 28/30) → ERA5 − SMN must be negative.
    assert row["bias_era5_minus_smn_t2m_max"] == pytest.approx(-2.0)
    assert row["bias_era5_minus_smn_t2m_min"] == pytest.approx(-1.0)
    assert row["mean_smn_t2m_max"] == pytest.approx(31.0)
    assert row["mean_era5_t2m_max"] == pytest.approx(29.0)
    assert row["paired_n_max"] == 2
    assert row["paired_first"] == "2026-01-01"
    assert row["paired_last"] == "2026-01-02"
    assert row["m01"] == 2
    assert row["m02"] == 0
    assert "month_zero" in row["flags"]
    assert "n_days_t2m_max<300" in row["flags"]


def test_paired_means_use_same_days_only() -> None:
    # ERA5 has an extra day that SMN lacks: it must NOT enter the means.
    regtemp = pd.DataFrame.from_records(
        [
            {
                "regtemp_name": "BUENOS AIRES OBSERVATORIO",
                "time": pd.Timestamp("2026-03-10"),
                "t2m_max": 26.0,
                "t2m_min": 16.0,
            }
        ]
    )
    era5 = _era5(
        ("Buenos Aires Observatorio", "t2m_max", "2026-03-10", 24.0),
        ("Buenos Aires Observatorio", "t2m_max", "2026-03-11", 99.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-03-10", 14.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-03-11", 99.0),
    )
    frame = build_diagnostics(era5, regtemp, _resolution("Buenos Aires Observatorio"))
    row = frame.iloc[0]
    assert row["paired_n_max"] == 1
    assert row["mean_era5_t2m_max"] == pytest.approx(24.0)  # 99.0 excluded
    assert row["mean_smn_t2m_max"] == pytest.approx(26.0)


def test_tmax_le_tmin_flag_counts_days() -> None:
    regtemp = pd.DataFrame.from_records(
        [
            {
                "regtemp_name": "BUENOS AIRES OBSERVATORIO",
                "time": pd.Timestamp("2026-01-01"),
                "t2m_max": 20.0,
                "t2m_min": 18.5,  # tmax - tmin = 1.5 <= 3 → violation
            }
        ]
    )
    era5 = _era5(("Buenos Aires Observatorio", "t2m_max", "2026-01-01", 20.0))
    frame = build_diagnostics(era5, regtemp, _resolution("Buenos Aires Observatorio"))
    row = frame.iloc[0]
    assert row["smn_tmax_le_tmin_plus3_days"] == 1
    # Daily low-range days stay a plain column; only the capture-wide mean
    # inversion (20.0 <= 18.5 + 3) raises the structural flag.
    assert "smn_mean_tmax<=tmin+3C" in row["flags"]
    assert "1d" not in row["flags"]


def test_unresolved_identity_flag_and_zero_pairs() -> None:
    regtemp = pd.DataFrame.from_records(
        [
            {
                "regtemp_name": "BUENOS AIRES OBSERVATORIO",
                "time": pd.Timestamp("2026-01-01"),
                "t2m_max": 20.0,
                "t2m_min": 10.0,
            }
        ]
    )
    era5 = _era5(("Buenos Aires Observatorio", "t2m_max", "2026-01-01", 20.0))
    resolution = _resolution("Buenos Aires Observatorio", status="not_in_regtemp")
    frame = build_diagnostics(era5, regtemp, resolution)
    row = frame.iloc[0]
    assert "unresolved_identity" in row["flags"]
    assert row["paired_n_max"] == 0
    assert row["regtemp_row_days"] == 0  # no rows attributed to an unresolved station


def test_pair_sources_skips_non_ok_quality() -> None:
    smn = pd.DataFrame.from_records(
        [
            {
                "location": "X",
                "variable": "t2m_max",
                "time": pd.Timestamp("2026-01-01"),
                "value": 20.0,
                "quality_flag": "ok",
            },
            {
                "location": "X",
                "variable": "t2m_max",
                "time": pd.Timestamp("2026-01-02"),
                "value": 21.0,
                "quality_flag": "suspect",
            },
        ]
    )
    era5 = _era5(
        ("X", "t2m_max", "2026-01-01", 19.0),
        ("X", "t2m_max", "2026-01-02", 20.0),
    )
    paired = pair_sources(smn, era5)
    assert len(paired) == 1
    assert str(paired.iloc[0]["time"].date()) == "2026-01-01"


def test_markdown_renders_sign_note_and_ba_spot_check(tmp_path: Path) -> None:
    path = _write_regtemp(
        tmp_path / "regtemp.txt",
        [
            _regtemp_line("01012026", "30.0", "20.0", "BUENOS AIRES OBSERVATORIO"),
            _regtemp_line("02012026", "31.0", "21.0", "BUENOS AIRES OBSERVATORIO"),
        ],
    )
    regtemp = parse_regtemp(path)
    era5 = _era5(
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-01", 28.0),
        ("Buenos Aires Observatorio", "t2m_max", "2026-01-02", 29.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-01", 19.0),
        ("Buenos Aires Observatorio", "t2m_min", "2026-01-02", 20.0),
    )
    frame = build_diagnostics(era5, regtemp, _resolution("Buenos Aires Observatorio"))
    md = render_diagnostics_markdown(
        frame,
        regtemp=regtemp,
        regtemp_path=path,
        provenance={"retrieved_at": "2026-11-12T01:41:32Z", "served_window_local": {}},
        generated_at=pd.Timestamp("2026-11-13 14:00:00"),
    )
    assert "ERA5 − SMN" in md
    assert "DDMMYYYY" in md
    assert "BUENOS AIRES OBSERVATORIO" in md
    assert "Paired t2m_max days per calendar month" in md
    assert "30.0" in md  # raw TMAX slice shown


def test_resolve_chain_feeds_diagnostics(tmp_path: Path) -> None:
    """End-to-end identity chain: GHCN id → NRO → catalogue → regtemp."""
    regtemp_path = _write_regtemp(
        tmp_path / "regtemp.txt",
        [_regtemp_line("01112025", "25.1", "16.8", "BUENOS AIRES OBSERVATORIO")],
    )
    catalogue = tmp_path / "estaciones_smn.txt"
    catalogue.write_text(
        _catalogue_line("BUENOS AIRES OBSERVATORIO", "87585") + "\n",
        encoding="latin-1",
    )
    region = {
        "stations": [
            {
                "name": "Buenos Aires Observatorio",
                "ghcn_id": "AR000875850",
                "lat": -34.583,
                "lon": -58.483,
                "elevation_m": 25,
            }
        ]
    }
    resolution = resolve_region_stations(
        region,
        parse_catalogue_nro_names(catalogue),
        set(parse_regtemp(regtemp_path)["regtemp_name"]),
    )
    assert resolution.iloc[0]["match_status"] == "resolved"
    assert resolution.iloc[0]["smn_nro"] == "87585"

    era5 = _era5(("Buenos Aires Observatorio", "t2m_max", "2025-11-01", 24.0))
    frame = build_diagnostics(era5, parse_regtemp(regtemp_path), resolution)
    assert frame.iloc[0]["paired_n_max"] == 1
    assert frame.iloc[0]["bias_era5_minus_smn_t2m_max"] == pytest.approx(24.0 - 25.1)
