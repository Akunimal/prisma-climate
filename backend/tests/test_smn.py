"""SMN connector tests — local payloads only, no network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prisma.ingest.smn import (
    SmnObservations,
    match_region,
    parse_estaciones,
    parse_observaciones,
)

# The real files carry name/province merged with a single space and orphan
# fragment lines; values below mirror data/smn_probe/estaciones/estaciones_smn.txt.
CATALOGUE_TEXT = "\n".join(
    [
        "NOMBRE  PROVINCIA  LATITUD  LONGITUD  ALTURA  NRO  NroOACI",
        "  [gr]  [min]  [gr]  [min]  [m]",
        "SALTA AERO  SALTA  -24  51  -65  29  1246  87047  SASA",
        "TUCUMAN AERO  TUCUMAN  -26  50  -65  6  450  87121  SANT",
        "PRESIDENCIA ROQUE SAENZ PENA A CHACO  -26  44  -60  29  93  87148 SARS",
        "ERO",
        "",
    ]
)


def _obs_line(
    fecha: str = "10112026",
    tmax: str | None = "25.1",
    tmin: str | None = "16.8",
    nombre: str = "SALTA AERO",
) -> str:
    """One observaciones data line with the real fixed column windows."""
    return (
        " "
        + fecha
        + " "
        + ((tmax or "").rjust(5))
        + " "
        + ((tmin or "").rjust(5))
        + " "
        + nombre
    )


def test_parse_observaciones_reads_fixed_columns() -> None:
    text = "\n".join(
        [
            " FECHA    TMAX  TMIN  NOMBRE",
            " -------- ----- ----- ----------------------------------------",
            _obs_line(),
            _obs_line(tmax=None, tmin="12.6", nombre="CAMPO DE MAYO AERO"),
            _obs_line(tmax=None, tmin=None, nombre="MARIANO MORENO AERO"),
            "",
        ]
    )
    table = parse_observaciones(text)

    assert len(table) == 3
    salta = table.loc[table["smn_name"] == "SALTA AERO"].iloc[0]
    assert salta["t2m_max"] == pytest.approx(25.1)
    assert salta["t2m_min"] == pytest.approx(16.8)
    assert pd.Timestamp(salta["time"]) == pd.Timestamp("2026-11-10")

    # Blank TMAX sits in the TMIN window; the parser must not shift columns.
    campo = table.loc[table["smn_name"] == "CAMPO DE MAYO AERO"].iloc[0]
    assert pd.isna(campo["t2m_max"])
    assert campo["t2m_min"] == pytest.approx(12.6)

    both_blank = table.loc[table["smn_name"] == "MARIANO MORENO AERO"].iloc[0]
    assert pd.isna(both_blank["t2m_max"])
    assert pd.isna(both_blank["t2m_min"])


def test_parse_observaciones_rejects_payload_without_rows() -> None:
    with pytest.raises(ValueError, match="no observations"):
        parse_observaciones(" FECHA    TMAX  TMIN  NOMBRE\n -------- ----- -----")


def test_parse_estaciones_text_skips_orphans_and_merges_single_space_rows() -> None:
    table = parse_estaciones(CATALOGUE_TEXT)

    assert len(table) == 3
    presidencia = table.loc[table["smn_nro"] == 87148].iloc[0]
    assert presidencia["smn_name"].startswith("PRESIDENCIA ROQUE SAENZ")
    assert table["smn_nro"].tolist() == [87047, 87121, 87148]


def test_match_region_resolves_by_nro_and_skips_missing_values() -> None:
    catalogue = parse_estaciones(CATALOGUE_TEXT)
    observations = parse_observaciones(
        "\n".join(
            [
                _obs_line(nombre="SALTA AERO"),
                _obs_line(tmax=None, tmin="18.0", nombre="TUCUMAN AERO"),
                _obs_line(nombre="UNRELATED STATION"),
            ]
        )
    )
    region = {
        "id": "toy",
        "stations": [
            {"name": "Salta Aero", "ghcn_id": "AR000870470", "lat": -24.85, "lon": -65.483},
            {"name": "Tucuman", "ghcn_id": "ARM00087121", "lat": -26.841, "lon": -65.105},
            {"name": "Missing", "ghcn_id": "ARM00000000", "lat": 0.0, "lon": 0.0},
        ],
    }
    frame = match_region(region, catalogue, observations)

    salta = frame.loc[frame["location"] == "Salta Aero"]
    assert sorted(salta["variable"]) == ["t2m_max", "t2m_min"]
    assert salta["value"].tolist() == [25.1, 16.8]

    # Blank TMAX produces no t2m_max row rather than a NaN value row.
    tucuman = frame.loc[frame["location"] == "Tucuman"]
    assert tucuman["variable"].tolist() == ["t2m_min"]

    assert "Missing" not in set(frame["location"])
    assert (frame["quality_flag"] == "ok").all()


def test_run_merges_new_day_into_existing_parquet(tmp_path: Path) -> None:
    region = {
        "id": "toy",
        "stations": [
            {"name": "Salta Aero", "ghcn_id": "AR000870470", "lat": -24.85, "lon": -65.483},
        ],
    }

    def _frame(day: int) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "variable": "t2m_max",
                    "location": "Salta Aero",
                    "lat": -24.85,
                    "lon": -65.483,
                    "time": pd.Timestamp(f"2026-11-{day:02d}"),
                    "value": 30.0 + day,
                    "quality_flag": "ok",
                }
            ]
        )

    connector = SmnObservations()
    original = SmnObservations.fetch

    try:
        SmnObservations.fetch = lambda self, reg, **kw: _frame(9)  # type: ignore[method-assign]
        connector.run(region, tmp_path)
        SmnObservations.fetch = lambda self, reg, **kw: _frame(10)  # type: ignore[method-assign]
        path = connector.run(region, tmp_path)
    finally:
        SmnObservations.fetch = original  # type: ignore[method-assign]

    out = pd.read_parquet(path)
    assert out["time"].dt.day.tolist() == [9, 10]
    assert out["value"].tolist() == [39.0, 40.0]
    assert out["day_convention"].unique().tolist() == ["local_calendar"]
