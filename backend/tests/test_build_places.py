"""Tests for scripts/build_places.py: filtering, admin1 names, ordering, registry.

Fixtures are synthetic GeoNames-shaped rows written to a temporary ZIP; no
network is used and no real dump is read.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "build_places.py"

ADMIN1 = """\
AR.01\tBuenos Aires\tBuenos Aires\t-36.0\t-60.0\t0
AR.02\tCordoba\tCordoba\t-31.0\t-64.0\t0
"""


def load_module():
    spec = importlib.util.spec_from_file_location("build_places", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def row(
    name: str,
    *,
    feature: str = "P",
    lat: float = -34.0,
    lon: float = -58.0,
    admin1: str = "01",
    population: int = 0,
) -> str:
    fields = [
        "1",  # geonameid
        name,
        name,
        "",
        str(lat),
        str(lon),
        feature,
        "PPL",
        "AR",
        "",
        admin1,
        "",
        "",
        "",
        str(population),
        "",
        "",
        "America/Argentina/Buenos_Aires",
        "2026-11-14",
    ]
    return "\t".join(fields)


def write_dump(path: Path, rows: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("AR.txt", "\n".join(rows) + "\n")
    return path


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_builds_country_file_and_registry(tmp_path: Path) -> None:
    module = load_module()
    dump = write_dump(
        tmp_path / "AR.zip",
        [
            row("Small Town", population=150),
            row("Big City", population=5000),
            row("Mid City", population=500),
            row("Not A Place", feature="A", population=9999),
            row("Dropped", population=10),
            row("Big City", population=5000),  # duplicate record
        ],
    )
    admin1 = tmp_path / "admin1CodesASCII.txt"
    admin1.write_text(ADMIN1, encoding="utf-8")

    written = module.build_gazetteer(
        country="AR",
        region_id="argentina",
        min_population=100,
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "places",
        dump_path=dump,
        admin1_path=admin1,
    )

    country_path = tmp_path / "places" / "ar.json"
    index_path = tmp_path / "places" / "index.json"
    assert written == [country_path, index_path]

    document = read_json(country_path)
    assert document["schema_version"] == "1.0"
    assert document["country"] == "AR"
    assert document["source"] == "geonames"
    assert document["licence"] == "CC BY 4.0"
    assert document["attribution_url"] == "https://www.geonames.org/"
    assert document["place_count"] == 3
    assert [place["name"] for place in document["places"]] == [
        "Big City",
        "Mid City",
        "Small Town",
    ]
    assert document["places"][0]["admin1"] == "Buenos Aires"
    assert document["places"][1]["population"] == 500

    index = read_json(index_path)
    assert index["schema_version"] == "1.0"
    assert index["sources"]["geonames"]["licence"] == "CC BY 4.0"
    assert index["regions"]["argentina"] == {
        "file": "ar.json",
        "country": "AR",
        "source": "geonames",
        "place_count": 3,
    }


def test_registry_keeps_other_regions(tmp_path: Path) -> None:
    module = load_module()
    out = tmp_path / "places"
    out.mkdir()
    (out / "index.json").write_text(
        json.dumps({"schema_version": "1.0", "regions": {"other": {"file": "xx.json"}}}),
        encoding="utf-8",
    )
    dump = write_dump(tmp_path / "AR.zip", [row("One", population=1)])
    admin1 = tmp_path / "admin1CodesASCII.txt"
    admin1.write_text(ADMIN1, encoding="utf-8")

    module.build_gazetteer(
        country="AR",
        region_id="argentina",
        cache_dir=tmp_path / "cache",
        out_dir=out,
        dump_path=dump,
        admin1_path=admin1,
    )

    index = read_json(out / "index.json")
    assert set(index["regions"]) == {"other", "argentina"}
    assert index["regions"]["other"]["file"] == "xx.json"


def test_output_is_deterministic(tmp_path: Path) -> None:
    module = load_module()
    dump = write_dump(
        tmp_path / "AR.zip",
        [row("Zeta", population=10), row("Alfa", population=10)],
    )
    admin1 = tmp_path / "admin1CodesASCII.txt"
    admin1.write_text(ADMIN1, encoding="utf-8")
    kwargs = {
        "country": "AR",
        "region_id": "argentina",
        "cache_dir": tmp_path / "cache",
        "out_dir": tmp_path / "places",
        "dump_path": dump,
        "admin1_path": admin1,
    }

    module.build_gazetteer(**kwargs)
    first = (tmp_path / "places" / "ar.json").read_bytes()
    module.build_gazetteer(**kwargs)
    second = (tmp_path / "places" / "ar.json").read_bytes()

    assert first == second
    names = [place["name"] for place in read_json(tmp_path / "places" / "ar.json")["places"]]
    assert names == ["Alfa", "Zeta"]
