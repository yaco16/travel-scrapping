from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.bus.base import BusProvider
from travel_scrapping.bus.parser import parse_trips
from travel_scrapping.bus.stations import parse_stations
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import ProviderStatus
from travel_scrapping.schemas import Offer

STATION_PATHS = ("/locations", "/stations", "/autocomplete", "/search")
TRIP_PATHS = ("/search", "/trips", "/connections")


class FlixBusRapidApiProvider(BusProvider):
    name = "flixbus"

    def status(self) -> ProviderStatus:
        if not self.settings.bus_enabled or not self.settings.flixbus_enabled:
            return ProviderStatus(self.name, enabled=False, warnings=["FlixBus disabled"])
        if not self.settings.rapidapi_key:
            return ProviderStatus(self.name, enabled=False, warnings=["RAPIDAPI_KEY missing"])
        return ProviderStatus(self.name, enabled=True)

    def headers(self) -> dict[str, str]:
        headers = {"X-RapidAPI-Key": self.settings.rapidapi_key}
        if self.settings.flixbus_rapidapi_host:
            headers["X-RapidAPI-Host"] = self.settings.flixbus_rapidapi_host
        return headers

    async def _get_first_ok(self, paths: tuple[str, ...], params: dict[str, Any]) -> tuple[int, dict[str, Any] | list[Any], str]:
        last_status = 0
        async with httpx.AsyncClient(timeout=30) as client:
            for path in paths:
                url = self.settings.flixbus_rapidapi_base_url.rstrip("/") + path
                response = await client.get(url, params=params, headers=self.headers())
                last_status = response.status_code
                if response.status_code >= 500:
                    continue
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"error": response.text[:500]}
                return response.status_code, payload, path
        return last_status, {"error": "no endpoint returned usable response"}, paths[-1]

    async def station_search(self, query: str) -> list[dict[str, Any]]:
        status, payload, _path = await self._get_first_ok(STATION_PATHS, {"query": query, "q": query, "locale": "fr"})
        if status >= 400:
            return []
        return parse_stations(payload)

    async def search_roundtrip(self, origin: str, destination: str, depart: str, ret: str) -> list[Offer]:
        status, payload, _path = await self._get_first_ok(
            TRIP_PATHS,
            {
                "from": origin,
                "to": destination,
                "origin": origin,
                "destination": destination,
                "departure_date": depart,
                "return_date": ret,
                "currency": "EUR",
            },
        )
        debug_path = save_bus_debug(payload, prefix="flixbus-search") if self.settings.flixbus_debug_save else None
        if status >= 400:
            return []
        return parse_trips(payload, origin=origin, destination=destination, raw_debug_path=debug_path)


def save_bus_debug(payload: dict[str, Any] | list[Any], *, prefix: str) -> str:
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    safe_payload = scrub_payload(payload) if isinstance(payload, dict) else payload
    path.write_text(json.dumps(safe_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)
