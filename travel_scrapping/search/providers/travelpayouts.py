from __future__ import annotations

from typing import Any

import httpx

from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus
from travel_scrapping.schemas import DealCandidate, Destination


class TravelpayoutsProvider(FlightProvider):
    name = "travelpayouts"

    def status(self) -> ProviderStatus:
        if not self.settings.travelpayouts_token:
            return ProviderStatus(self.name, enabled=False, warnings=["TRAVELPAYOUTS_TOKEN missing"])
        warnings = []
        if not self.settings.travelpayouts_marker:
            warnings.append("TRAVELPAYOUTS_MARKER missing; deeplinks disabled")
        return ProviderStatus(self.name, enabled=True, warnings=warnings)

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        if not self.status().enabled:
            return []
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://api.travelpayouts.com/v2/prices/latest",
                params={
                    "origin": self.settings.origin_airport,
                    "currency": self.settings.default_currency,
                    "limit": min(limit, 50),
                    "token": self.settings.travelpayouts_token,
                },
            )
            response.raise_for_status()
            return parse_travelpayouts_payload(
                response.json(),
                origin=self.settings.origin_airport,
                marker=self.settings.travelpayouts_marker,
            )


def _extract_airlines(row: dict[str, Any]) -> list[str]:
    airlines: list[str] = []
    for key in ("airline", "airlines", "carrier", "carriers", "airline_iata"):
        value = row.get(key)
        if not value:
            continue
        if isinstance(value, str):
            airlines.append(value)
        elif isinstance(value, list):
            airlines.extend(str(item) for item in value if item)
    return sorted(set(airlines))


def _extract_booking_url(row: dict[str, Any], marker: str | None) -> str | None:
    for key in ("deep_link", "booking_url", "url"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    if marker:
        generated = row.get("link")
        if isinstance(generated, str) and generated.startswith(("http://", "https://")):
            return generated
    return None


def parse_travelpayouts_payload(payload: dict[str, Any], *, origin: str, marker: str | None = None) -> list[DealCandidate]:
    deals: list[DealCandidate] = []
    for row in payload.get("data", []):
        try:
            depart = row["depart_date"]
            ret = row.get("return_date")
            if not ret:
                continue
            from travel_scrapping.search.normalizer import parse_date, scrub_payload

            outbound = parse_date(depart)
            return_date = parse_date(ret)
            airlines = _extract_airlines(row)
            warnings = ["cached or indicative fare; verify before booking"]
            if not airlines:
                warnings.append("airline missing from source")
            booking_url = _extract_booking_url(row, marker)
            if not booking_url and not marker:
                warnings.append("travelpayouts marker missing")
            deals.append(
                DealCandidate(
                    source="travelpayouts",
                    origin_airport=origin,
                    destination_airport=row["destination"],
                    destination_city=row.get("destination_city") or row.get("city"),
                    outbound_date=outbound,
                    return_date=return_date,
                    nights=(return_date - outbound).days,
                    total_price=float(row["value"]),
                    currency=row.get("currency", "EUR"),
                    airlines=airlines,
                    booking_url=booking_url,
                    raw_payload=scrub_payload(row),
                    confidence="low",
                    warnings=warnings,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return deals
