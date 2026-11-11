"""Station cross-check tests — local files only, no network."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from prisma.ingest.smn import candidate_nros
from prisma.report.station_crosscheck import (
    crosscheck_region,
    parse_smn_estaciones,
    render_markdown,
)

# Mirrors the SMN fixed layout: name, province, lat gr/min, lon gr/min,
# elevation, NRO, OACI — two-or-more-space separators (values from the real
# data/smn_probe/estaciones/estaciones_smn.txt, except CORDOBA OACI).
CATALOGUE_TEXT = "\n".join(
    [
        "NOMBRE  PROVINCIA  LATITUD  LONGITUD  ALTURA  NRO  NroOACI",
        "  [gr]  [min]  [gr]  [min]  [m]",
        "SALTA AERO  SALTA  -24  51  -65  29  1246  87047  SASA",
        "USHUAIA AERO  TIERRA DEL FUEGO  -54  50  -68  18  57  87938  SAWH",
        "LA QUIACA OBSERVATORIO  JUJUY  -22  6  -65  36  3459  87007  SASQ",
        "CORDOBA AERO  CORDOBA  -31  19  -64  13  474  87344  SACO",
        "",
    ]
)


def _write_catalogue(tmp_path: Path, text: str = CATALOGUE_TEXT) -> Path:
    path = tmp_path / "estaciones_smn.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_parse_smn_estaciones_signs_and_fields(tmp_path: Path) -> None:
    table = parse_smn_estaciones(_write_catalogue(tmp_path))
    assert len(table) == 4
    salta = table.loc[table["smn_nro"] == 87047].iloc[0]
    # −24°51′ → −24.85; −65°29′ → −65.4833…
    assert salta["smn_lat"] == pytest.approx(-24.85)
    assert salta["smn_lon"] == pytest.approx(-(65 + 29 / 60))
    assert salta["smn_elevation_m"] == 1246
    assert salta["smn_name"] == "SALTA AERO"


def test_parse_smn_estaciones_row_with_single_space_and_junk_line(
    tmp_path: Path,
) -> None:
    # Two real rows run name and province together with a single space, and
    # the file carries orphan fragment lines that are not stations.
    text = "\n".join(
        [
            "NOMBRE  PROVINCIA  LATITUD  LONGITUD  ALTURA  NRO  NroOACI",
            "PRESIDENCIA ROQUE SAENZ PENA A CHACO  -26  44  -60  29  93  87148 SARS",
            "ERO",
            "",
        ]
    )
    table = parse_smn_estaciones(_write_catalogue(tmp_path, text))
    assert len(table) == 1
    row = table.iloc[0]
    assert row["smn_nro"] == 87148
    assert row["smn_elevation_m"] == 93
    assert row["smn_lat"] == pytest.approx(-(26 + 44 / 60))
    assert row["smn_lon"] == pytest.approx(-(60 + 29 / 60))


def test_crosscheck_region_flags_coordinate_offset(tmp_path: Path) -> None:
    catalogue = parse_smn_estaciones(_write_catalogue(tmp_path))
    region = {
        "id": "toy",
        "stations": [
            # Exact NRO match, tiny offsets → no flags.
            {
                "name": "Salta Aero",
                "ghcn_id": "AR000870470",
                "lat": -24.85,
                "lon": -65.483,
                "elevation_m": 1246,
            },
            # Latitude 0.13° off and elevation 63 m off → flags; longitude
            # offset 0.004° stays under the threshold.
            {
                "name": "Ushuaia Malvinas Argentinas",
                "ghcn_id": "ARM00087938",
                "lat": -54.70,
                "lon": -68.296,
                "elevation_m": 120,
            },
            # Known GHCN id → NRO match.
            {
                "name": "La Quiaca Observatorio",
                "ghcn_id": "AR000087007",
                "lat": -22.10,
                "lon": -65.60,
                "elevation_m": 3479,
            },
        ],
    }
    table = crosscheck_region(region, catalogue)

    assert list(table["matched_by"]) == ["nro", "nro", "nro"]
    salta = table.loc[table["location"] == "Salta Aero"].iloc[0]
    assert salta["flags"] == ""
    assert abs(salta["delta_lon"]) < 0.01

    ushuaia = table.loc[table["location"] == "Ushuaia Malvinas Argentinas"].iloc[0]
    assert "|Δlat|" in ushuaia["flags"]
    assert "|Δelev|" in ushuaia["flags"]
    assert "|Δlon|" not in ushuaia["flags"]  # lon offset 0.004° < 0.05°

    la_quiaca = table.loc[table["location"] == "La Quiaca Observatorio"].iloc[0]
    assert la_quiaca["flags"] == ""


def test_crosscheck_nearest_fallback_when_nro_absent(tmp_path: Path) -> None:
    catalogue = parse_smn_estaciones(_write_catalogue(tmp_path))
    region = {
        "id": "toy",
        "stations": [
            {
                "name": "Salta Aero",
                "ghcn_id": None,
                "lat": -24.85,
                "lon": -65.483,
                "elevation_m": 1246,
            }
        ],
    }
    table = crosscheck_region(region, catalogue)
    assert table.iloc[0]["matched_by"] == "nearest"
    assert int(table.iloc[0]["smn_nro"]) == 87047


def test_render_markdown_mentions_thresholds(tmp_path: Path) -> None:
    catalogue = parse_smn_estaciones(_write_catalogue(tmp_path))
    region = {
        "id": "toy",
        "stations": [
            {
                "name": "Salta Aero",
                "ghcn_id": "AR000870470",
                "lat": -24.85,
                "lon": -65.483,
                "elevation_m": 1246,
            }
        ],
    }
    table = crosscheck_region(region, catalogue)
    report = render_markdown(table, generated_at=pd.Timestamp("2026-11-11"), region_id="toy")
    assert "0.05°" in report
    assert "50 m" in report
    assert "No station exceeded" in report


def test_candidate_nros_deterministic_id_patterns() -> None:
    # network 0, ``000`` + WMO (readme: station field 8 chars).
    assert candidate_nros("AR000087007") == [87007]
    assert candidate_nros("AR000087860") == [87860]
    # network 0, two leading zeros + WMO + trailing zero.
    assert candidate_nros("AR000870470") == [87047]
    assert candidate_nros("AR000875850") == [87585]
    # network M: last five characters are the WMO number.
    assert candidate_nros("ARM00087938") == [87938]
    assert candidate_nros("ARM00087121") == [87121]
    # Malformed ids yield no candidates (fallback: nearest coordinates).
    assert candidate_nros(None) == []
    assert candidate_nros("") == []
    assert candidate_nros("TOOSHORT") == []
