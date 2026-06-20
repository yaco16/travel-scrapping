from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.bus.base import BusProvider
from travel_scrapping.bus.parser import parse_trips
from travel_scrapping.bus.stations import parse_stations
from travel_scrapping.config import Settings
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import ProviderStatus
from travel_scrapping.schemas import Offer

STATION_PATHS = ("/locations", "/stations", "/autocomplete", "/search")
TRIP_PATHS = ("/search", "/trips", "/connections")


class FlixBusRapidApiProvider(BusProvider):
    name = "flixbus"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_status_code: int | None = None
        self.last_path: str | None = None
        self.last_error: str | None = None

    def status(self) -> ProviderStatus:
        if not self.settings.bus_enabled or not self.settings.flixbus_enabled:
            return ProviderStatus(self.name, enabled=False, warnings=["FlixBus disabled"])
        if not self.settings.rapidapi_key:
            return ProviderStatus(self.name, enabled=False, warnings=["RAPIDAPI_KEY missing"])
        return ProviderStatus(self.name, enabled=True)

    def headers(self) -> dict[str, str]:
        headers = {"X-RapidAPI-Key": self.settings.rapidapi_key}
        host = self.settings.flixbus_rapidapi_host or self.settings.flixbus_rapidapi_base_url.rstrip("/").removeprefix(
            "https://"
        ).removeprefix("http://")
        if host:
            headers["X-RapidAPI-Host"] = host
        return headers

    async def _get_first_ok(
        self, paths: tuple[str, ...], params: dict[str, Any]
    ) -> tuple[int, dict[str, Any] | list[Any], str]:
        last_status = 0
        last_payload: dict[str, Any] | list[Any] = {"error": "no endpoint returned usable response"}
        async with httpx.AsyncClient(timeout=30) as client:
            for path in paths:
                url = self.settings.flixbus_rapidapi_base_url.rstrip("/") + path
                response = await client.get(url, params=params, headers=self.headers())
                last_status = response.status_code
                self.last_status_code = response.status_code
                self.last_path = path
                if response.status_code >= 500:
                    continue
                try:
                    payload = response.json()
                except ValueError:
                    payload = {"error": response.text[:500]}
                last_payload = payload
                self.last_error = _payload_error(payload)
                return response.status_code, payload, path
        self.last_error = _payload_error(last_payload)
        return last_status, last_payload, paths[-1]

    async def station_search(self, query: str) -> list[dict[str, Any]]:
        status, payload, _path = await self._get_first_ok(STATION_PATHS, {"query": query, "q": query, "locale": "fr"})
        if self.settings.flixbus_debug_save:
            save_bus_debug(payload, prefix="flixbus-stations")
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


def _payload_error(payload: dict[str, Any] | list[Any]) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("message") or payload.get("error")
    return str(value)[:500] if value else None


def save_bus_debug(payload: dict[str, Any] | list[Any], *, prefix: str) -> str:
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    safe_payload = scrub_payload(payload) if isinstance(payload, dict) else payload
    path.write_text(json.dumps(safe_payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)
