from __future__ import annotations

from typing import Any


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def parse_stations(payload: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    stations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in _walk(payload):
        station_id = row.get("id") or row.get("uuid") or row.get("station_id") or row.get("legacy_id")
        name = row.get("name") or row.get("station_name") or row.get("city_name")
        if not station_id or not name:
            continue
        key = str(station_id)
        if key in seen:
            continue
        seen.add(key)
        stations.append(
            {
                "id": key,
                "name": str(name),
                "city": row.get("city") or row.get("city_name") or row.get("municipality"),
                "country": row.get("country") or row.get("country_name"),
                "raw": row,
            }
        )
    return stations
