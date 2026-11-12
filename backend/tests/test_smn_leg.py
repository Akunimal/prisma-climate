"""SMN regtemp leg tests — fixture-based, no network."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from prisma.report.smn_leg import (
    build_smn_frame,
    capture_gap_rows,
    coverage_table,
    load_capture_manifest,
    no_overlap_note,
    overlap_period,
    parse_catalogue_nro_names,
    parse_regtemp,
    render_smn_section,
    resolve_region_stations,
)


def _regtemp_line(fecha: str, tmax: str, tmin: str, nombre: str) -> str:
    """One fixed-width regtemp data line (FECHA/TMAX/TMIN/NOMBRE)."""
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
    # NRO sits at chars 110-115; pad so len(line) > 115 (wrap-join parser).
    return name.ljust(110) + nro.rjust(5) + " "


REGION = {
    "id": "toy",
    "timezone": "America/Argentina/Cordoba",
    "stations": [
        {
            "id": "salta",
            "name": "Salta Aero",
            "ghcn_id": "ARM00087047",
            "lat": -24.85,
            "lon": -65.483,
            "elevation_m": 1246,
        },
        {
            "id": "missing",
            "name": "Ghost Station",
            "ghcn_id": "AR000000000",
            "lat": -1.0,
            "lon": -1.0,
            "elevation_m": 10,
        },
    ],
}


def test_parse_regtemp_fixed_columns_and_blanks(tmp_path: Path) -> None:
    path = _write_regtemp(
        tmp_path / "regtemp.txt",
        [
            _regtemp_line("01112025", "25.1", "16.8", "SALTA AERO"),
            _regtemp_line("02112025", "", "14.0", "SALTA AERO"),  # blank TMAX
            _regtemp_line("02112025", "30.0", "", "OBERA"),  # blank TMIN
        ],
    )
    frame = parse_regtemp(path)
    assert list(frame.columns) == ["regtemp_name", "time", "t2m_max", "t2m_min"]
    assert len(frame) == 3
    salta = frame.loc[frame["regtemp_name"] == "SALTA AERO"].sort_values("time")
    assert salta.iloc[0]["t2m_max"] == pytest.approx(25.1)
    assert salta.iloc[0]["t2m_min"] == pytest.approx(16.8)
    assert pd.isna(salta.iloc[1]["t2m_max"])  # blank stays NaN, never filled
    assert salta.iloc[1]["t2m_min"] == pytest.approx(14.0)
    assert str(salta.iloc[0]["time"].date()) == "2025-11-01"
    obera = frame.loc[frame["regtemp_name"] == "OBERA"].iloc[0]
    assert obera["t2m_max"] == pytest.approx(30.0)
    assert pd.isna(obera["t2m_min"])


def test_parse_regtemp_skips_header_and_short_lines(tmp_path: Path) -> None:
    path = _write_regtemp(tmp_path / "r.txt", [_regtemp_line("01012026", "20.0", "10.0", "X AERO")])
    frame = parse_regtemp(path)
    assert len(frame) == 1  # header + separator skipped by FECHA check


def test_parse_regtemp_rejects_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.txt"
    path.write_text("FECHA    TMAX  TMIN  NOMBRE\n", encoding="latin-1")
    with pytest.raises(ValueError, match="no regtemp data rows"):
        parse_regtemp(path)


def test_load_capture_manifest_reads_sibling_json(tmp_path: Path) -> None:
    regtemp = tmp_path / "registro_temperatura365d_smn.txt"
    regtemp.write_text("x", encoding="latin-1")
    manifest = {
        "retrieved_at": "2026-11-12T01:41:32Z",
        "data_rows": 42953,
        "served_window_local": {"first": "2025-11-11", "last": "2026-11-10", "distinct_days": 365},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    assert load_capture_manifest(tmp_path / "manifest.json")["data_rows"] == 42953
    assert load_capture_manifest(tmp_path / "absent.json") == {}


def test_parse_catalogue_joins_name_wrap_fragments(tmp_path: Path) -> None:
    path = tmp_path / "estaciones.txt"
    # First line: truncated name + NRO; second: wrap fragment without NRO.
    path.write_text(
        "\n".join(
            [
                _catalogue_line("PRESIDENCIA ROQUE SAENZ P", "87344"),
                _catalogue_line("ENA AERO", "").rstrip(),
                _catalogue_line("SALTA AERO", "87047"),
            ]
        ),
        encoding="latin-1",
    )
    by_nro = parse_catalogue_nro_names(path)
    assert by_nro["87047"] == "SALTA AERO"
    assert by_nro["87344"] == "PRESIDENCIA ROQUE SAENZ PENA AERO"


def test_resolve_region_via_nro_exact_and_missing(tmp_path: Path) -> None:
    catalogue = tmp_path / "cat.txt"
    catalogue.write_text(
        "\n".join(
            [
                _catalogue_line("SALTA AERO", "87047"),
                _catalogue_line("OTRA AERO", "99999"),
            ]
        ),
        encoding="latin-1",
    )
    by_nro = parse_catalogue_nro_names(catalogue)
    names = {"SALTA AERO", "OBERA"}
    resolution = resolve_region_stations(REGION, by_nro, names)
    salta = resolution.loc[resolution["location"] == "Salta Aero"].iloc[0]
    assert salta["smn_nro"] == "87047"
    assert salta["regtemp_name"] == "SALTA AERO"
    assert salta["match_status"] == "resolved"
    ghost = resolution.loc[resolution["location"] == "Ghost Station"].iloc[0]
    assert ghost["match_status"] == "catalogue_nro_missing"
    assert ghost["regtemp_name"] == ""


def test_resolve_region_fuzzy_fallback(tmp_path: Path) -> None:
    catalogue = tmp_path / "cat.txt"
    catalogue.write_text(_catalogue_line("SALTA AERO", "87047") + "\n", encoding="latin-1")
    by_nro = parse_catalogue_nro_names(catalogue)
    # regtemp spelling differs slightly → fuzzy hit
    resolution = resolve_region_stations(REGION, by_nro, {"SALTA AEROS", "OBERA"})
    salta = resolution.loc[resolution["location"] == "Salta Aero"].iloc[0]
    assert salta["match_status"] == "resolved_fuzzy"
    assert salta["regtemp_name"] == "SALTA AEROS"


def test_resolve_region_not_in_regtemp(tmp_path: Path) -> None:
    catalogue = tmp_path / "cat.txt"
    catalogue.write_text(_catalogue_line("SALTA AERO", "87047") + "\n", encoding="latin-1")
    by_nro = parse_catalogue_nro_names(catalogue)
    resolution = resolve_region_stations(REGION, by_nro, {"ZZZZ NOMATCH STATION"})
    salta = resolution.loc[resolution["location"] == "Salta Aero"].iloc[0]
    assert salta["match_status"] == "not_in_regtemp"


def _regtemp_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "regtemp_name": "SALTA AERO",
                "time": pd.Timestamp("2025-11-01"),
                "t2m_max": 25.1,
                "t2m_min": 16.8,
            },
            {
                "regtemp_name": "SALTA AERO",
                "time": pd.Timestamp("2025-11-02"),
                "t2m_max": float("nan"),  # blank TMAX → gap
                "t2m_min": 14.0,
            },
            {
                "regtemp_name": "SALTA AERO",
                "time": pd.Timestamp("2025-11-03"),
                "t2m_max": 27.0,
                "t2m_min": 15.0,
            },
        ]
    )


def _resolution() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "location": "Salta Aero",
                "ghcn_id": "ARM00087047",
                "smn_nro": "87047",
                "catalogue_name": "SALTA AERO",
                "regtemp_name": "SALTA AERO",
                "match_status": "resolved",
            },
            {
                "location": "Ghost Station",
                "ghcn_id": "AR000000000",
                "smn_nro": "",
                "catalogue_name": "",
                "regtemp_name": "",
                "match_status": "catalogue_nro_missing",
            },
        ]
    )


def test_build_smn_frame_normalizes_and_skips_blanks() -> None:
    frame = build_smn_frame(_regtemp_frame(), _resolution())
    assert set(frame.columns) >= {
        "location",
        "variable",
        "time",
        "value",
        "quality_flag",
        "source",
        "unit",
        "day_convention",
    }
    # 3 station-days, one blank TMAX → 3 t2m_min + 2 t2m_max rows; ghost absent.
    assert len(frame) == 5
    assert set(frame["location"]) == {"Salta Aero"}
    assert set(frame["quality_flag"]) == {"ok"}
    assert set(frame["day_convention"]) == {"local_calendar"}
    assert set(frame["source"]) == {"smn-regtemp"}
    blank_day = frame.loc[
        frame["time"].eq(pd.Timestamp("2025-11-02")) & frame["variable"].eq("t2m_max")
    ]
    assert blank_day.empty  # gap, not a filled row


def test_build_smn_frame_empty_when_unresolved() -> None:
    frame = build_smn_frame(_regtemp_frame(), _resolution().iloc[0:0])
    assert frame.empty
    ghost_only = _resolution()
    ghost_only.loc[:, "match_status"] = "not_in_regtemp"
    ghost_only.loc[:, "regtemp_name"] = ""
    assert build_smn_frame(_regtemp_frame(), ghost_only).empty


def test_coverage_table_counts_missing_and_blanks() -> None:
    regtemp = _regtemp_frame()
    # Expect 5-day window for the fixture → 2 missing row-days for Salta.
    coverage = coverage_table(regtemp, _resolution(), expected_days=5)
    salta = coverage.loc[coverage["location"] == "Salta Aero"].iloc[0]
    assert salta["row_days"] == 3
    assert salta["missing_row_days"] == 2
    assert salta["t2m_max_values"] == 2
    assert salta["t2m_min_values"] == 3
    assert salta["blank_tmax_days"] == 1
    assert salta["blank_tmin_days"] == 0
    assert salta["status"] == "gaps"
    ghost = coverage.loc[coverage["location"] == "Ghost Station"].iloc[0]
    assert ghost["status"] == "unresolved"
    assert ghost["missing_row_days"] == 5


def test_capture_gap_rows_lists_partial_stations() -> None:
    regtemp = pd.concat(
        [
            _regtemp_frame(),
            pd.DataFrame(
                [
                    {
                        "regtemp_name": "OBERA",
                        "time": pd.Timestamp("2025-11-01"),
                        "t2m_max": 20.0,
                        "t2m_min": 10.0,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    gaps = capture_gap_rows(regtemp, expected_days=5)
    # Salta has 3/5, OBERA has 1/5 — both partial at expected_days=5.
    by_name = {g["regtemp_name"]: g for g in gaps}
    assert by_name["SALTA AERO"]["missing_row_days"] == 2
    assert by_name["OBERA"]["missing_row_days"] == 4
    assert len(gaps) == 2


def test_overlap_period_and_no_overlap_note() -> None:
    smn = build_smn_frame(_regtemp_frame(), _resolution())
    other = pd.DataFrame(
        [
            {
                "location": "Salta Aero",
                "variable": "t2m_max",
                "time": pd.Timestamp("2025-11-02"),
                "value": 24.0,
                "quality_flag": "ok",
            },
            {
                "location": "Salta Aero",
                "variable": "t2m_min",
                "time": pd.Timestamp("2025-11-02"),
                "value": 15.0,
                "quality_flag": "ok",
            },
        ]
    )
    period = overlap_period(smn, other)
    assert period is not None
    assert period[0] == pd.Timestamp("2025-11-02")
    assert period[1] == pd.Timestamp("2025-11-02")

    disjoint = other.assign(time=pd.Timestamp("2026-01-01"))
    assert overlap_period(smn, disjoint) is None
    note = no_overlap_note(smn, disjoint, other_label="GHCN-Daily")
    assert "No overlapping local-calendar days" in note
    assert "GHCN-Daily" in note
    assert "nothing is interpolated" in note


def test_render_smn_section_states_convention_provenance_and_gaps() -> None:
    smn = build_smn_frame(_regtemp_frame(), _resolution())

    def _pair(
        day: str,
        smn_max: float,
        smn_min: float,
        other_max: float,
        other_min: float,
    ) -> list[dict]:
        ts = pd.Timestamp(day)
        return [
            {
                "location": "Salta Aero",
                "variable": "t2m_max",
                "time": ts,
                "value": smn_max,
                "quality_flag": "ok",
            },
            {
                "location": "Salta Aero",
                "variable": "t2m_min",
                "time": ts,
                "value": smn_min,
                "quality_flag": "ok",
            },
            {
                "location": "Salta Aero",
                "variable": "t2m_max",
                "time": ts,
                "value": other_max,
                "quality_flag": "ok",
            },
            {
                "location": "Salta Aero",
                "variable": "t2m_min",
                "time": ts,
                "value": other_min,
                "quality_flag": "ok",
            },
        ]

    # Split into smn-shaped vs other-shaped frames: build smn from fixture,
    # era5 as the counterpart values.
    era5 = pd.DataFrame(
        [
            {
                "location": "Salta Aero",
                "variable": variable,
                "time": pd.Timestamp(day),
                "value": value,
                "quality_flag": "ok",
            }
            for day, values in (
                ("2025-11-01", (24.0, 15.0)),
                ("2025-11-02", (26.0, 13.0)),
                ("2025-11-03", (28.0, 16.0)),
            )
            for variable, value in zip(("t2m_max", "t2m_min"), values, strict=True)
        ]
    )
    from prisma.report.discrepancies import compare

    table = compare(smn, era5, source_a="smn", source_b="era5")
    provenance = {
        "retrieved_at": "2026-11-12T01:41:32Z",
        "data_rows": 3,
        "sha256_txt": "abc123",
        "endpoint": "https://ssl.smn.gob.ar/dpd/zipopendata.php?dato=regtemp",
        "day_convention_evidence": "FECHA is DDMMYYYY with no hour column",
        "served_window_local": {
            "first": "2025-11-01",
            "last": "2025-11-03",
            "distinct_days": 3,
        },
    }
    coverage = coverage_table(_regtemp_frame(), _resolution(), expected_days=5)
    gaps = capture_gap_rows(_regtemp_frame(), expected_days=5)
    empty_other = pd.DataFrame(columns=["time"])
    section = render_smn_section(
        smn_vs_era5=table,
        smn_vs_ghcn=None,
        era5_no_overlap=None,
        ghcn_no_overlap=no_overlap_note(
            smn,
            empty_other,
            other_label="GHCN-Daily",
        ),
        provenance=provenance,
        resolution=_resolution(),
        coverage=coverage,
        capture_gaps=gaps,
        regtemp_path=Path("data/smn_probe/regtemp/registro_temperatura365d_smn.txt"),
        era5_overlap=(pd.Timestamp("2025-11-01"), pd.Timestamp("2025-11-03")),
    )
    assert "day_convention: local_calendar" in section
    assert "Diagnostic, not skill" in section
    assert "15-issue-date gate" in section
    assert "2026-11-12T01:41:32Z" in section
    assert "abc123" in section
    assert "42953" not in section  # fixture provenance, not the real file
    assert "missing station-days" in section
    assert "never filled" in section or "not filled" in section
    assert "SALTA AERO" in section
    assert "### SMN vs ERA5" in section
    assert "### SMN vs GHCN-Daily" in section
    assert "No overlapping local-calendar days" in section
    assert "not** merged into this" in section or "not merged into this" in section
    assert "regtemp has no precipitation" in section
    # Same flag scheme appears when a group is flagged; here bias may not flag.
    assert "SMN vs ERA5" in section


def test_render_smn_section_without_capture_is_not_used_here() -> None:
    # Guard: render requires explicit inputs; empty resolution still renders.
    note = (
        "No overlapping local-calendar days: SMN regtemp has no values; "
        "ERA5 ok rows end 2026-11-05."
    )
    section = render_smn_section(
        smn_vs_era5=None,
        smn_vs_ghcn=None,
        era5_no_overlap=note,
        ghcn_no_overlap="No overlapping local-calendar days.",
        provenance={},
        resolution=_resolution().iloc[0:0],
        coverage=pd.DataFrame(),
        capture_gaps=[],
        regtemp_path=Path("missing/regtemp.txt"),
        era5_overlap=None,
    )
    assert "### Capture provenance (regtemp)" in section
    assert "unknown" in section  # empty provenance degrades honestly
