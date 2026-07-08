from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.search.normalizer import parse_date, scrub_payload, scrub_text
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
    endpoint: str = "google_flights"
    raw_count: int = 0
    normalized_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    top_prices: list[float] | None = None
    destinations: list[str] | None = None
    probes: dict[str, str] | None = None


class SerpApiGoogleFlightsProvider(FlightProvider):
    name = "serpapi"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.last_attempted = False
        self.last_status_code: int | None = None
        self.last_raw_count = 0
        self.last_normalized_count = 0

    def status(self) -> ProviderStatus:
        if not self.settings.serpapi_api_key:
            return ProviderStatus(self.name, enabled=False, warnings=["SERPAPI_API_KEY missing"], key_present=False)
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
                    self.last_attempted = True
                    response = await client.get(SERPAPI_URL, params=params)
                    self.last_status_code = response.status_code
                    response.raise_for_status()
                    payload = response.json()
                    raw_count = sum(
                        len(payload.get(key) or [])
                        for key in ("best_flights", "other_flights", "flights")
                        if isinstance(payload.get(key), list)
                    )
                    self.last_raw_count += raw_count
                    parsed = parse_serpapi_payload(
                        payload,
                        origin=self.settings.origin_airport,
                        destination=destination.airport,
                        outbound=outbound,
                        ret=ret,
                    )
                    self.last_normalized_count += len(parsed)
                    deals.extend(parsed)
                    await asyncio.sleep(0.2)
                    if len(deals) >= limit:
                        return deals[:limit]
        return deals


class SerpApiGoogleFlightDealsProvider(FlightProvider):
    name = "serpapi_google_flights_deals"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self.last_attempted = False
        self.last_status_code: int | None = None
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_public_params: dict[str, Any] = {}
        self.last_destination_examples: list[str] = []
        self.last_debug_path: str | None = None
        self.last_ok = True
        self.last_error: str | None = None

    def status(self) -> ProviderStatus:
        if not self.settings.serpapi_api_key:
            return ProviderStatus(self.name, enabled=False, warnings=["SERPAPI_API_KEY missing"], key_present=False)
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
        requested_start = self.settings.search_start_date or (date_pairs[0][0] if date_pairs else date.today())
        start = max(requested_start, current_search_date())
        primary_params = serpapi_deals_params(
            api_key=self.settings.serpapi_api_key,
            origin=self.settings.origin_airport,
            outbound_start=start,
            outbound_end=self.settings.effective_search_end_date,
            min_nights=self.settings.min_nights,
            max_nights=self.settings.max_nights,
            max_price=int(self.settings.max_roundtrip_price_eur),
            max_stops=self.settings.max_stops,
            currency=self.settings.default_currency,
            adults=self.settings.adults,
        )
        self.last_ok = True
        self.last_error = None
        self.last_attempted = True
        if self.settings.effective_search_end_date < start:
            self.last_ok = False
            self.last_status_code = None
            self.last_raw_count = 0
            self.last_normalized_count = 0
            self.last_destination_examples = []
            self.last_error = (
                "Plage de dates invalide: "
                f"date départ max {self.settings.effective_search_end_date.isoformat()} "
                f"avant date départ min {start.isoformat()}."
            )
            self.last_public_params = {
                **public_params(primary_params),
                "http_status": None,
                "raw_count": 0,
                "normalized_count": 0,
                "payload_diagnostic": {"error": self.last_error},
                "diagnostic": self.last_error,
            }
            return []
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.get(SERPAPI_URL, params=primary_params)
            self.last_status_code = response.status_code
            try:
                payload_for_debug = response.json()
            except ValueError:
                payload_for_debug = {"error": scrub_text(getattr(response, "text", ""))[:500]}
        raw_count = count_deals_items(payload_for_debug)
        payload_diag = serpapi_payload_diagnostic(payload_for_debug)
        parsed = [] if response.status_code >= 400 else parse_google_flight_deals_payload(payload_for_debug, origin=self.settings.origin_airport)
        if response.status_code >= 400:
            self.last_ok = False
            self.last_error = scrub_text(str(payload_diag.get("error") or f"HTTP {response.status_code}"))[:500]
        elif payload_diag.get("error"):
            self.last_ok = False
            self.last_error = scrub_text(str(payload_diag["error"]))[:500]
            parsed = []
        self.last_raw_count = count_deals_items(payload_for_debug)
        self.last_debug_path = save_debug_json(
            {
                "params": public_params(primary_params),
                "http_status": self.last_status_code,
                "raw_count": raw_count,
                "normalized_count": len(parsed),
                "payload_diagnostic": serpapi_payload_diagnostic(payload_for_debug),
                "payload": payload_for_debug,
            },
            prefix="serpapi-google-flight-deals",
        )
        self.last_normalized_count = len(parsed)
        self.last_destination_examples = destination_examples(parsed)
        diagnostic = None
        if self.last_status_code == 200 and self.last_ok and self.last_raw_count == 0:
            diagnostic = "SerpApi appelé, HTTP 200, payload sans clé deals exploitable."
        elif self.last_status_code and self.last_status_code >= 400:
            diagnostic = f"SerpApi appelé, HTTP {self.last_status_code}: {self.last_error or 'erreur provider'}"
        self.last_public_params = {
            **public_params(primary_params),
            "http_status": self.last_status_code,
            "raw_count": raw_count,
            "normalized_count": len(parsed),
            "payload_diagnostic": serpapi_payload_diagnostic(payload_for_debug),
            "diagnostic": diagnostic,
        }
        return parsed[:limit]


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


def current_search_date() -> date:
    return date.today()


def serpapi_deals_params(
    *,
    api_key: str,
    origin: str,
    outbound_start: date | str,
    outbound_end: date | str,
    min_nights: int,
    max_nights: int,
    max_price: int,
    max_stops: int,
    currency: str = "EUR",
    adults: int = 1,
) -> dict[str, Any]:
    start = outbound_start.isoformat() if isinstance(outbound_start, date) else outbound_start
    end = outbound_end.isoformat() if isinstance(outbound_end, date) else outbound_end
    return {
        "engine": "google_flights_deals",
        "departure_id": origin,
        "type": "1",
        "outbound_date": f"{start},{end}",
        "trip_length": f"{min_nights},{max_nights}",
        "max_price": str(max_price),
        "stops": str(max_stops + 1),
        "currency": currency,
        "gl": "fr",
        "hl": "fr",
        "adults": adults,
        "api_key": api_key,
    }


def public_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key != "api_key"}


def serpapi_payload_diagnostic(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("search_metadata")
    pagination = payload.get("serpapi_pagination")
    diagnostic: dict[str, Any] = {
        "search_metadata_status": metadata.get("status") if isinstance(metadata, dict) else None,
        "top_level_keys": list(payload.keys()),
    }
    if payload.get("error"):
        diagnostic["error"] = scrub_text(str(payload["error"]))[:500]
    if pagination:
        diagnostic["serpapi_pagination"] = scrub_payload(pagination)
    return diagnostic


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
    for key in ("booking_url", "link", "url", "google_flights_link", "serpapi_link", "flight_link", "serpapi_flight_link"):
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
    value = item.get("price") or item.get("total_price") or item.get("extracted_price")
    if isinstance(value, dict):
        value = value.get("value") or value.get("amount") or value.get("extracted")
    if isinstance(value, str):
        value = value.replace("€", "").replace("EUR", "").replace(" ", "").replace(",", ".")
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _float_value(item: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, dict):
            value = value.get("value") or value.get("amount") or value.get("extracted")
        if isinstance(value, str):
            value = value.replace("%", "").replace("€", "").replace("EUR", "").replace(" ", "").replace(",", ".")
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _duration_minutes(item: dict[str, Any]) -> int | None:
    value = item.get("total_duration") or item.get("duration") or item.get("flight_duration")
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


def _text_value(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
        if isinstance(value, dict):
            for nested_key in ("name", "city", "id", "iata", "code", "link", "url"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested:
                    return nested
    return None


def _date_value(item: dict[str, Any], fallback: date | None, *keys: str) -> date:
    for key in keys:
        value = item.get(key)
        if value:
            return parse_date(str(value))
    return _first_date(None, fallback)


def _image_url(item: dict[str, Any]) -> str | None:
    value = item.get("image") or item.get("thumbnail") or item.get("image_url")
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("url", "thumbnail", "image"):
            nested = value.get(key)
            if isinstance(nested, str):
                return nested
    return None


def _destination_code(item: dict[str, Any]) -> str | None:
    code = (
        _airport_code(item.get("destination_airport"))
        or _airport_code(item.get("arrival_airport"))
        or _airport_code(item.get("destination"))
        or _text_value(item, "arrival_airport_code", "destination_airport_code", "arrival_id", "iata", "airport_code")
    )
    if code and len(code) == 3 and code.isalpha():
        return code.upper()
    route = _text_value(item, "route", "title")
    if route:
        for sep in ("-", "→", "->"):
            if sep in route:
                tail = route.split(sep)[-1].strip()[:3]
                if len(tail) == 3 and tail.isalpha():
                    return tail.upper()
    return code.upper() if code else None


def _deal_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    value = payload.get("deals")
    if not isinstance(value, list):
        return items
    for row in value:
        if not isinstance(row, dict):
            continue
        nested = row.get("flights") or row.get("offers")
        if isinstance(nested, list):
            for nested_row in nested:
                if isinstance(nested_row, dict):
                    merged = dict(row)
                    merged.update(nested_row)
                    items.append(merged)
        else:
            items.append(row)
    return items


def count_deals_items(payload: dict[str, Any]) -> int:
    return len(_deal_items(payload))


def destination_examples(deals: list[DealCandidate], limit: int = 10) -> list[str]:
    examples: list[str] = []
    for deal in deals:
        label = deal.destination_city or deal.destination_airport
        if label and label not in examples:
            examples.append(label)
        if len(examples) >= limit:
            break
    return examples


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


def parse_google_flight_deals_payload(payload: dict[str, Any], *, origin: str) -> list[DealCandidate]:
    deals: list[DealCandidate] = []
    for item in _deal_items(payload):
        try:
            depart_date = _date_value(item, None, "outbound_date", "departure_date", "depart_date")
            return_date = _date_value(item, None, "return_date", "inbound_date")
            destination_code = _destination_code(item) or ""
            destination_city = _text_value(item, "destination_city", "city", "destination_name", "name")
            destination_country = _text_value(item, "country", "destination_country")
            operator = _flight_operator(item) or "Google Flight Deals"
            price = _price(item)
            booking_url = _booking_url(item) or "https://www.google.com/travel/flights"
            stops = _stops(item)
            duration = _duration_minutes(item)
            missing = []
            if not destination_code:
                missing.append("destination_airport")
            if price is None:
                missing.append("price_amount")
            deals.append(
                DealCandidate(
                    source="serpapi_google_flights_deals",
                    provider="serpapi_google_flights_deals",
                    origin_airport=origin,
                    destination_airport=destination_code,
                    destination_city=destination_city,
                    destination_country=destination_country,
                    outbound_date=depart_date,
                    return_date=return_date,
                    nights=(return_date - depart_date).days,
                    total_price=float(price or 0),
                    currency=str(item.get("currency") or payload.get("currency") or "EUR"),
                    airlines=[operator],
                    is_direct=(stops == 0 if stops is not None else None),
                    has_connection=(stops > 0 if stops is not None else None),
                    outbound_duration_hours=(duration / 60 if duration else None),
                    duration_minutes=duration,
                    stops_count=stops,
                    booking_url=booking_url,
                    operator_name=operator,
                    average_price=_float_value(item, "average_price", "typical_price", "price_average"),
                    discount_percent=_float_value(
                        item, "discount_percent", "discount_percentage", "price_drop_percent", "percentage_drop"
                    ),
                    image_url=_image_url(item),
                    raw_payload=scrub_payload(item),
                    confidence="high" if price and destination_code else "medium",
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
