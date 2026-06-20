from __future__ import annotations

from typing import Any

import httpx

from travel_scrapping.airports import AirportInfo, FRENCH_CITY_BY_IATA, normalize_iata
from travel_scrapping.config import Settings, get_settings

AIRPORTS_URL = "https://api.api-ninjas.com/v1/airports"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _info_from_payload(payload: dict[str, Any], code: str) -> AirportInfo:
    city = payload.get("city")
    return AirportInfo(
        iata=code,
        airport_name=str(payload["name"]) if payload.get("name") else None,
        city=str(city) if city else None,
        city_fr=FRENCH_CITY_BY_IATA.get(code),
        country=str(payload["country"]) if payload.get("country") else None,
        timezone=str(payload["timezone"]) if payload.get("timezone") else None,
        latitude=_float_or_none(payload.get("latitude")),
        longitude=_float_or_none(payload.get("longitude")),
        source="api_ninjas",
        raw_payload=payload,
    )


def fetch_airport_by_iata(iata_code: str, settings: Settings | None = None) -> AirportInfo | None:
    settings = settings or get_settings()
    code = normalize_iata(iata_code)
    if not code or not settings.api_ninjas_api_key:
        return None
    try:
        response = httpx.get(
            AIRPORTS_URL,
            params={"iata": code},
            headers={"X-Api-Key": settings.api_ninjas_api_key},
            timeout=5.0,
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, list):
        return None
    for item in payload:
        if not isinstance(item, dict):
            continue
        if normalize_iata(item.get("iata")) == code:
            return _info_from_payload(item, code)
    return None
