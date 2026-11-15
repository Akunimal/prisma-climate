"""Build the shipped place gazetteer under ``data/places/`` from GeoNames.

The app ships its own place list so that place search never calls a geocoding
service at runtime. This script reads the public GeoNames dump for one country,
keeps the populated-place feature class (``P``), resolves first-level divisions
from ``admin1CodesASCII.txt`` and writes a compact, deterministic JSON file:

- ``data/places/<country>.json`` — ``name``, ``admin1``, ``lat``, ``lon`` and
  ``population`` per place, plus the source, licence and attribution strings.
- ``data/places/index.json`` — the registry the app reads to find the file for
  a region id, so a new country only needs a new data file and an index entry.

GeoNames is licensed CC BY 4.0; every file carries the attribution and its URL.
The dump is cached under ``data/cache/geonames/`` (gitignored). Records are
sorted by population (descending), then name, province and coordinates, so a
rebuild without source changes produces the same bytes.

Usage::

    python scripts/build_places.py
    python scripts/build_places.py --country AR --region-id argentina \\
        --min-population 1000

The default keeps every populated place. The file is expected to stay under
2 MB for Argentina; use ``--min-population`` if a country dump exceeds the
phone budget, and record the threshold in ``docs/SITE_DATA.md``.
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.request
import zipfile
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

GEONAMES_BASE = "https://download.geonames.org/export/dump"
DUMP_URL = GEONAMES_BASE + "/{country}.zip"
ADMIN1_URL = GEONAMES_BASE + "/admin1CodesASCII.txt"
SCHEMA_VERSION = "1.0"
SOURCE = "geonames"
ATTRIBUTION = "Place data from GeoNames"
ATTRIBUTION_URL = "https://www.geonames.org/"
LICENCE = "CC BY 4.0"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
DEFAULT_COUNTRY = "AR"
DEFAULT_REGION_ID = "argentina"
MAX_PLACES = 25_000


def download(url: str, cache_dir: Path) -> Path:
    """Download ``url`` once and return the cached file."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / url.rsplit("/", 1)[-1]
    if not path.is_file():
        print(f"downloading {url}")
        with urllib.request.urlopen(url) as response:
            path.write_bytes(response.read())
    return path


def read_country_rows(archive_path: Path, country: str) -> Iterator[list[str]]:
    """Yield tab-separated rows of ``<country>.txt`` from the dump ZIP."""
    with (
        zipfile.ZipFile(archive_path) as archive,
        archive.open(f"{country}.txt") as handle,
        io.TextIOWrapper(handle, encoding="utf-8") as text,
    ):
        for line in text:
            yield line.rstrip("\n").split("\t")


def load_admin1(path: Path) -> dict[str, str]:
    """``AR.01`` -> province name, from ``admin1CodesASCII.txt``."""
    mapping: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0]:
            mapping[parts[0]] = parts[1]
    return mapping


def place_records(
    rows: Iterable[list[str]],
    admin1: dict[str, str],
    min_population: int,
) -> Iterator[dict[str, Any]]:
    """Yield normalised populated places, sorted and de-duplicated by the caller."""
    seen: set[tuple[str, str, float, float]] = set()
    for fields in rows:
        if len(fields) < 15 or fields[6] != "P":
            continue
        name = fields[1].strip()
        if not name:
            continue
        try:
            population = int(fields[14] or 0)
        except ValueError:
            population = 0
        if population < min_population:
            continue
        try:
            lat = round(float(fields[4]), 4)
            lon = round(float(fields[5]), 4)
        except ValueError:
            continue
        admin_code = fields[10].strip()
        province = admin1.get(f"{fields[8]}.{admin_code}", admin_code)
        key = (name, province, lat, lon)
        if key in seen:
            continue
        seen.add(key)
        yield {
            "name": name,
            "admin1": province,
            "lat": lat,
            "lon": lon,
            "population": population,
        }


def sort_key(place: dict[str, Any]) -> tuple[int, str, str, float, float]:
    return (
        -int(place["population"]),
        str(place["name"]).casefold(),
        str(place["admin1"]).casefold(),
        float(place["lat"]),
        float(place["lon"]),
    )


def build_gazetteer(
    *,
    country: str = DEFAULT_COUNTRY,
    region_id: str = DEFAULT_REGION_ID,
    min_population: int = 0,
    cache_dir: Path | None = None,
    out_dir: Path | None = None,
    dump_path: Path | None = None,
    admin1_path: Path | None = None,
) -> list[Path]:
    """Write the country file and update the registry; return written paths."""
    out = Path(out_dir) if out_dir is not None else Path("data") / "places"
    cache = Path(cache_dir) if cache_dir is not None else Path("data") / "cache" / "geonames"
    country = country.upper()
    if dump_path is None:
        dump_path = download(DUMP_URL.format(country=country), cache)
    if admin1_path is None:
        admin1_path = download(ADMIN1_URL, cache)

    admin1 = load_admin1(Path(admin1_path))
    places = sorted(
        place_records(read_country_rows(Path(dump_path), country), admin1, min_population),
        key=sort_key,
    )
    if len(places) > MAX_PLACES:
        raise ValueError(
            f"{country}: {len(places)} places exceeds MAX_PLACES={MAX_PLACES}; "
            "raise --min-population and record the threshold in docs/SITE_DATA.md"
        )

    out.mkdir(parents=True, exist_ok=True)
    filename = f"{country.lower()}.json"
    country_document = {
        "schema_version": SCHEMA_VERSION,
        "country": country,
        "source": SOURCE,
        "attribution": ATTRIBUTION,
        "attribution_url": ATTRIBUTION_URL,
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
        "place_count": len(places),
        "places": places,
    }
    written = [_write_json(out / filename, country_document, compact=True)]

    index_path = out / "index.json"
    index = _read_json(index_path) if index_path.is_file() else {}
    index["schema_version"] = SCHEMA_VERSION
    sources = index.setdefault("sources", {})
    sources[SOURCE] = {
        "attribution": ATTRIBUTION,
        "attribution_url": ATTRIBUTION_URL,
        "licence": LICENCE,
        "licence_url": LICENCE_URL,
    }
    regions = index.setdefault("regions", {})
    regions[region_id] = {
        "file": filename,
        "country": country,
        "source": SOURCE,
        "place_count": len(places),
    }
    written.append(_write_json(index_path, index))
    return written


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return data


def _write_json(path: Path, document: dict[str, Any], *, compact: bool = False) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(document, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(document, indent=2, ensure_ascii=False)
    path.write_text(text + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", default=DEFAULT_COUNTRY, help="ISO country code")
    parser.add_argument(
        "--region-id", default=DEFAULT_REGION_ID, help="region id from configs/regions"
    )
    parser.add_argument(
        "--min-population",
        type=int,
        default=0,
        help="drop places below this population (default: keep all)",
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("data") / "cache" / "geonames")
    parser.add_argument("--out-dir", type=Path, default=Path("data") / "places")
    parser.add_argument("--dump", type=Path, default=None, help="use a local dump ZIP")
    parser.add_argument(
        "--admin1", type=Path, default=None, help="use a local admin1CodesASCII.txt"
    )
    args = parser.parse_args(argv)

    written = build_gazetteer(
        country=args.country,
        region_id=args.region_id,
        min_population=args.min_population,
        cache_dir=args.cache_dir,
        out_dir=args.out_dir,
        dump_path=args.dump,
        admin1_path=args.admin1,
    )
    for path in written:
        size = path.stat().st_size
        print(f"wrote {path} ({size / 1024:.1f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
