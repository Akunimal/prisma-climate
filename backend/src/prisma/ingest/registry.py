"""Resolve connectors declared in configs/sources.yaml."""

from __future__ import annotations

from typing import Any

from .base import Connector, is_valid_day_convention, load_yaml
from .ghcn import GhcnDaily
from .indices import NoaaOni, NoaaSam
from .openmeteo import OpenMeteoEnsemble, OpenMeteoEra5
from .smn import SmnObservations

CONNECTORS: dict[str, type[Connector]] = {
    "openmeteo.OpenMeteoEra5": OpenMeteoEra5,
    "openmeteo.OpenMeteoEnsemble": OpenMeteoEnsemble,
    "ghcn.GhcnDaily": GhcnDaily,
    "indices.NoaaOni": NoaaOni,
    "indices.NoaaSam": NoaaSam,
    "smn.SmnObservations": SmnObservations,
}


def load_registry(path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    if "sources" not in data:
        raise ValueError(f"{path} has no 'sources' key")
    for entry in data["sources"]:
        convention = entry.get("day_convention")
        if not convention or not is_valid_day_convention(convention):
            raise ValueError(
                f"{path}: source {entry.get('id')!r} has invalid day_convention {convention!r}"
            )
    return data["sources"]


def select_sources(
    registry: list[dict[str, Any]],
    *,
    tier: int | None = None,
    ids: list[str] | None = None,
    include_planned: bool = False,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for entry in registry:
        if ids:
            if entry["id"] in ids:
                selected.append(entry)
            continue
        if not include_planned and entry.get("status") != "active":
            continue
        if tier is not None and entry.get("tier") != tier:
            continue
        selected.append(entry)
    if ids:
        missing = [requested for requested in ids if requested not in {e["id"] for e in selected}]
        if missing:
            raise ValueError(f"unknown source ids: {missing}")
    return selected


def build(entry: dict[str, Any]) -> Connector:
    key = entry.get("connector")
    if key not in CONNECTORS:
        raise NotImplementedError(
            f"source {entry['id']!r} declares connector {key!r}, which is not implemented "
            f"(status: {entry.get('status')!r})"
        )
    return CONNECTORS[key]()
