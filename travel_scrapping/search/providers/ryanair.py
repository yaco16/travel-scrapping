from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus

RYANAIR_FARES_URL = "https://services-api.ryanair.com/farfnd/v4/roundTripFares"
RYANAIR_BOOKING_URL = (
    "https://www.ryanair.com/fr/fr/trip/flights/select"
    "?adults=1&teens=0&children=0&infants=0"
    "&dateOut={out}&dateIn={ret}"
    "&originIata={origin}&destinationIata={dest}"
    "&raf=false&isConnectedFlight=false"
)


class RyanairProvider(FlightProvider):
    name = "ryanair"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.last_attempted = False
        self.last_status_code: int | None = None
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_public_params: dict[str, Any] = {}
        self.last_destination_examples: list[str] = []
        self.last_ok = True
        self.last_error: str | None = None

    def status(self) -> ProviderStatus:
        if not self.settings.ryanair_enabled:
            return ProviderStatus(self.name, enabled=False, warnings=["RYANAIR_ENABLED=false"], key_present=True)
        return ProviderStatus(self.name, enabled=True, key_present=True)

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        if not self.status().enabled:
            return []

        start = max(self.settings.search_start_date or date.today(), date.today())
        end = self.settings.effective_search_end_date
        inbound_end = end + timedelta(days=self.settings.max_nights)

        params: dict[str, Any] = {
            "departureAirportIataCode": self.settings.origin_airport,
            "outboundDepartureDateFrom": start.isoformat(),
            "outboundDepartureDateTo": end.isoformat(),
            "inboundDepartureDateFrom": (start + timedelta(days=self.settings.min_nights)).isoformat(),
            "inboundDepartureDateTo": inbound_end.isoformat(),
            "language": "fr",
            "limit": min(limit, 100),
            "maxPrice": int(self.settings.max_roundtrip_price_eur),
            "offset": 0,
            "currency": self.settings.default_currency,
        }
        self.last_attempted = True
        self.last_ok = True
        self.last_error = None

        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; travel-scrapping/1.0)",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(RYANAIR_FARES_URL, params=params, headers=headers)
            self.last_status_code = response.status_code
            response.raise_for_status()
            payload = response.json()

        fares = payload.get("fares") or []
        self.last_raw_count = len(fares)
        self.last_public_params = {k: v for k, v in params.items() if k != "apiKey"}

        _save_debug(
            {"params": self.last_public_params, "http_status": self.last_status_code, "raw_count": len(fares)},
            prefix="ryanair-roundtrip",
        )

        deals = _parse_fares(fares, origin=self.settings.origin_airport)
        self.last_normalized_count = len(deals)
        self.last_destination_examples = [d.destination_airport for d in deals[:5]]
        return deals[:limit]


def _parse_fares(fares: list[dict[str, Any]], *, origin: str) -> list[DealCandidate]:
    deals: list[DealCandidate] = []
    for fare in fares:
        try:
            outbound = fare.get("outbound") or {}
            inbound = fare.get("inbound") or {}
            summary = fare.get("summary") or {}

            dest_iata = (outbound.get("arrivalAirport") or {}).get("iataCode", "")
            dest_name = (outbound.get("arrivalAirport") or {}).get("name")
            dest_country = (outbound.get("arrivalAirport") or {}).get("countryName")

            outbound_date_raw = outbound.get("departureDate") or ""
            return_date_raw = inbound.get("departureDate") or ""

            out_date = _parse_date(outbound_date_raw)
            ret_date = _parse_date(return_date_raw)

            if not dest_iata or out_date is None or ret_date is None:
                continue

            price_data = summary.get("price") or outbound.get("price") or {}
            price_val: float | None = None
            if isinstance(price_data, dict):
                price_val = _float_or_none(price_data.get("value"))
            if price_val is None:
                price_val = _float_or_none(price_data)
            if price_val is None:
                continue

            currency = (price_data.get("currencyCode") if isinstance(price_data, dict) else None) or "EUR"
            nights = (ret_date - out_date).days

            booking_url = RYANAIR_BOOKING_URL.format(
                out=out_date.isoformat(),
                ret=ret_date.isoformat(),
                origin=origin,
                dest=dest_iata,
            )

            deals.append(
                DealCandidate(
                    source="ryanair",
                    origin_airport=origin,
                    destination_airport=dest_iata,
                    destination_city=dest_name,
                    destination_country=dest_country,
                    outbound_date=out_date,
                    return_date=ret_date,
                    nights=nights,
                    total_price=price_val,
                    currency=currency,
                    airlines=["Ryanair"],
                    is_direct=True,
                    has_connection=False,
                    booking_url=booking_url,
                    raw_payload=scrub_payload(fare),
                    confidence="high",
                    transport_mode="flight",
                    provider="ryanair",
                    operator_name="Ryanair",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return deals


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _save_debug(payload: dict[str, Any], *, prefix: str) -> str:
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = debug_dir / f"{prefix}-{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)
