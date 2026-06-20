from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.search.normalizer import parse_date, scrub_payload
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus
from travel_scrapping.schemas import DealCandidate, Destination

SERPAPI_URL = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class SerpApiSmokeResult:
    params: dict[str, Any]
    status_code: int | None
    metadata_status: str | None
    error: str | None
    best_flights: int
    other_flights: int
    departure_tokens: int
    booking_tokens: int
    booking_options: int
    debug_path: str | None


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
        async with httpx.AsyncClient(timeout=30) as client:
            for destination in destinations[: max(1, min(len(destinations), limit))]:
                for outbound, ret, _nights in date_pairs[:1]:
                    params = serpapi_base_params(
                        api_key=self.settings.serpapi_api_key,
                        origin=self.settings.origin_airport,
                        destination=destination.airport,
                        depart=outbound,
                        ret=ret,
                        currency=self.settings.default_currency,
                        adults=self.settings.adults,
                        bags=self.settings.checked_bags,
                    )
                    response = await client.get(SERPAPI_URL, params=params)
                    response.raise_for_status()
                    payload = response.json()
                    parsed = parse_serpapi_payload(
                        payload,
                        origin=self.settings.origin_airport,
                        destination=destination.airport,
                        outbound=outbound,
                        ret=ret,
                    )
                    deals.extend([deal for deal in parsed if deal.actionable])
                    await asyncio.sleep(0.2)
                    if len(deals) >= limit:
                        return deals[:limit]
        return deals


def serpapi_base_params(
    *,
    api_key: str,
    origin: str,
    destination: str,
    depart: date | str,
    ret: date | str,
    currency: str = "EUR",
    adults: int = 1,
    bags: int = 0,
) -> dict[str, Any]:
    return {
        "engine": "google_flights",
        "type": "1",
        "departure_id": origin,
        "arrival_id": destination,
        "outbound_date": depart.isoformat() if isinstance(depart, date) else depart,
        "return_date": ret.isoformat() if isinstance(ret, date) else ret,
        "currency": currency,
        "hl": "fr",
        "gl": "fr",
        "adults": adults,
        "bags": bags,
        "stops": "1",
        "show_hidden": "true",
        "deep_search": "true",
        "api_key": api_key,
    }


def public_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: ("***" if key == "api_key" else value) for key, value in params.items()}


def _first_date(value: Any, fallback: date | None) -> date:
    if value:
        return parse_date(str(value))
    if fallback:
        return fallback
    raise ValueError("missing date")


def _flight_operator(item: dict[str, Any]) -> str | None:
    airlines = item.get("airlines") or item.get("airline")
    if isinstance(airlines, str):
        return airlines
    if isinstance(airlines, list) and airlines:
        return str(airlines[0])
    flights = item.get("flights") or []
    if isinstance(flights, list):
        for flight in flights:
            if isinstance(flight, dict):
                airline = flight.get("airline") or flight.get("airline_name")
                if airline:
                    return str(airline)
    return None


def _airport_code(value: Any) -> str | None:
    if isinstance(value, dict):
        return str(value.get("id") or value.get("iata") or "") or None
    if isinstance(value, str):
        return value
    return None


def _booking_url(item: dict[str, Any]) -> str | None:
    for key in ("booking_url", "link", "url"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    options = item.get("booking_options")
    if isinstance(options, list):
        for option in options:
            if not isinstance(option, dict):
                continue
            for key in ("booking_url", "link", "url"):
                value = option.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
    return None


def _price(item: dict[str, Any]) -> float | None:
    value = item.get("price") or item.get("total_price")
    if isinstance(value, str):
        value = value.replace("€", "").replace("EUR", "").replace(" ", "").replace(",", ".")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duration_minutes(item: dict[str, Any]) -> int | None:
    value = item.get("total_duration") or item.get("duration")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _stops(item: dict[str, Any]) -> int | None:
    if "stops" in item:
        try:
            return int(item["stops"])
        except (TypeError, ValueError):
            return None
    layovers = item.get("layovers")
    if isinstance(layovers, list):
        return len(layovers)
    flights = item.get("flights")
    if isinstance(flights, list) and flights:
        return max(0, len(flights) - 1)
    return None


def parse_serpapi_payload(
    payload: dict[str, Any],
    *,
    origin: str,
    destination: str | None = None,
    outbound: date | None = None,
    ret: date | None = None,
) -> list[DealCandidate]:
    items: list[dict[str, Any]] = []
    for key in ("best_flights", "other_flights", "flights"):
        value = payload.get(key)
        if isinstance(value, list):
            items.extend(item for item in value if isinstance(item, dict))
    booking_options = payload.get("booking_options")
    if isinstance(booking_options, list) and items:
        for item in items:
            item.setdefault("booking_options", booking_options)
    deals: list[DealCandidate] = []
    for item in items:
        try:
            depart_date = _first_date(item.get("outbound_date") or item.get("departure_date"), outbound)
            return_date = _first_date(item.get("return_date"), ret)
            destination_code = (
                destination
                or _airport_code(item.get("destination_airport"))
                or _airport_code(item.get("arrival_airport"))
                or ""
            )
            operator = _flight_operator(item)
            price = _price(item)
            booking_url = _booking_url(item)
            stops = _stops(item)
            duration = _duration_minutes(item)
            warnings: list[str] = []
            missing = []
            if not operator:
                missing.append("operator_name")
                warnings.append("airline missing from source")
            if not booking_url:
                missing.append("booking_url")
            if price is None:
                missing.append("price_amount")
            deals.append(
                DealCandidate(
                    source="serpapi",
                    provider="serpapi",
                    origin_airport=origin,
                    destination_airport=destination_code,
                    destination_city=item.get("destination_city"),
                    outbound_date=depart_date,
                    return_date=return_date,
                    nights=(return_date - depart_date).days,
                    total_price=float(price or 0),
                    currency=str(item.get("currency") or payload.get("currency") or "EUR"),
                    airlines=[operator] if operator else [],
                    is_direct=(stops == 0 if stops is not None else None),
                    has_connection=(stops > 0 if stops is not None else None),
                    outbound_duration_hours=(duration / 60 if duration else None),
                    duration_minutes=duration,
                    stops_count=stops,
                    booking_url=booking_url,
                    operator_name=operator,
                    raw_payload=scrub_payload(item),
                    confidence="high" if price and operator and booking_url else "medium",
                    warnings=warnings,
                    missing_fields=missing,
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return deals


def count_tokens(payload: dict[str, Any]) -> tuple[int, int, int]:
    departure_tokens = 0
    booking_tokens = 0
    booking_options = 0
    for key in ("best_flights", "other_flights", "flights"):
        value = payload.get(key)
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            if item.get("departure_token"):
                departure_tokens += 1
            if item.get("booking_token"):
                booking_tokens += 1
            options = item.get("booking_options")
            if isinstance(options, list):
                booking_options += len(options)
    root_options = payload.get("booking_options")
    if isinstance(root_options, list):
        booking_options += len(root_options)
    return departure_tokens, booking_tokens, booking_options


def save_debug_json(payload: dict[str, Any], *, prefix: str) -> str:
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    path = debug_dir / f"{prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(scrub_payload(payload), indent=2, ensure_ascii=True), encoding="utf-8")
    return str(path)


async def serpapi_smoke(
    *,
    api_key: str,
    origin: str,
    destination: str,
    depart: date,
    ret: date,
) -> SerpApiSmokeResult:
    params = serpapi_base_params(api_key=api_key, origin=origin, destination=destination, depart=depart, ret=ret)
    payloads: list[dict[str, Any]] = []
    status_code: int | None = None
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.get(SERPAPI_URL, params=params)
        status_code = response.status_code
        payload = response.json()
        payloads.append(payload)
        departure_tokens = [
            item.get("departure_token")
            for group in (payload.get("best_flights") or [], payload.get("other_flights") or [])
            for item in group
            if isinstance(item, dict) and item.get("departure_token")
        ][:3]
        for token in departure_tokens:
            token_params = dict(params)
            token_params["departure_token"] = token
            token_response = await client.get(SERPAPI_URL, params=token_params)
            token_payload = token_response.json()
            payloads.append(token_payload)
            booking_tokens = [
                item.get("booking_token")
                for group in (token_payload.get("best_flights") or [], token_payload.get("other_flights") or [])
                for item in group
                if isinstance(item, dict) and item.get("booking_token")
            ][:3]
            for booking_token in booking_tokens:
                booking_params = dict(params)
                booking_params["booking_token"] = booking_token
                booking_response = await client.get(SERPAPI_URL, params=booking_params)
                payloads.append(booking_response.json())
    merged = {"params": public_params(params), "payloads": payloads}
    debug_path = save_debug_json(merged, prefix="serpapi-smoke")
    first = payloads[0] if payloads else {}
    departure_count = booking_count = booking_options_count = 0
    for payload in payloads:
        d_count, b_count, options_count = count_tokens(payload)
        departure_count += d_count
        booking_count += b_count
        booking_options_count += options_count
    return SerpApiSmokeResult(
        params=public_params(params),
        status_code=status_code,
        metadata_status=(first.get("search_metadata") or {}).get("status") if isinstance(first, dict) else None,
        error=str(first.get("error")) if isinstance(first, dict) and first.get("error") else None,
        best_flights=len(first.get("best_flights") or []) if isinstance(first, dict) else 0,
        other_flights=len(first.get("other_flights") or []) if isinstance(first, dict) else 0,
        departure_tokens=departure_count,
        booking_tokens=booking_count,
        booking_options=booking_options_count,
        debug_path=debug_path,
    )


def midnight(value: date) -> datetime:
    return datetime.combine(value, time.min, tzinfo=timezone.utc)
