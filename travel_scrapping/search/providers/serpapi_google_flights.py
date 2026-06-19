from __future__ import annotations

import asyncio
from typing import Any

import httpx

from travel_scrapping.search.normalizer import normalize_serpapi_item
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus
from travel_scrapping.schemas import DealCandidate, Destination


class SerpApiGoogleFlightsProvider(FlightProvider):
    name = "serpapi"

    def status(self) -> ProviderStatus:
        if not self.settings.serpapi_api_key:
            return ProviderStatus(self.name, enabled=False, warnings=["SERPAPI_API_KEY missing"])
        return ProviderStatus(self.name, enabled=True)

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        if not self.status().enabled:
            return []
        deals: list[DealCandidate] = []
        async with httpx.AsyncClient(timeout=20) as client:
            for destination in destinations[: max(1, min(len(destinations), limit))]:
                for outbound, ret, _nights in date_pairs[:1]:
                    params: dict[str, Any] = {
                        "engine": "google_flights",
                        "departure_id": self.settings.origin_airport,
                        "arrival_id": destination.airport,
                        "outbound_date": outbound.isoformat(),
                        "return_date": ret.isoformat(),
                        "currency": self.settings.default_currency,
                        "hl": self.settings.default_locale,
                        "api_key": self.settings.serpapi_api_key,
                    }
                    response = await client.get("https://serpapi.com/search.json", params=params)
                    response.raise_for_status()
                    payload = response.json()
                    deals.extend(parse_serpapi_payload(payload, origin=self.settings.origin_airport))
                    await asyncio.sleep(0.2)
                    if len(deals) >= limit:
                        return deals[:limit]
        return deals


def parse_serpapi_payload(payload: dict[str, Any], *, origin: str) -> list[DealCandidate]:
    items = payload.get("best_flights") or payload.get("other_flights") or payload.get("flights") or []
    deals: list[DealCandidate] = []
    for item in items:
        try:
            deals.append(normalize_serpapi_item(item, origin=origin))
        except (KeyError, TypeError, ValueError):
            continue
    return deals
