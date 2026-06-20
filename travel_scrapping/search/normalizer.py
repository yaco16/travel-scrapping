from __future__ import annotations

from datetime import date
import re
from typing import Any

from travel_scrapping.schemas import DealCandidate


def parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value[:10])


def scrub_payload(payload: dict[str, Any]) -> dict[str, Any]:
    secret_words = ("key", "token", "secret", "api")
    scrubbed: dict[str, Any] = {}
    for key, value in payload.items():
        if any(word in key.lower() for word in secret_words):
            scrubbed[key] = "***"
        elif isinstance(value, dict):
            scrubbed[key] = scrub_payload(value)
        elif isinstance(value, list):
            scrubbed[key] = [scrub_payload(v) if isinstance(v, dict) else v for v in value[:20]]
        else:
            scrubbed[key] = value
    return scrubbed


def scrub_text(value: str) -> str:
    patterns = (
        (r"([?&](?:api_key|key|token|secret)=)[^&\s]+", r"\1***"),
        (r"(?<![?&])\bapi_key\b", "***"),
    )
    scrubbed = value
    for pattern, replacement in patterns:
        scrubbed = re.sub(pattern, replacement, scrubbed, flags=re.IGNORECASE)
    return scrubbed


def normalize_serpapi_item(item: dict[str, Any], *, origin: str) -> DealCandidate:
    price = float(item.get("price") or item.get("total_price") or 0)
    destination = item.get("destination_airport") or item.get("arrival_airport") or {}
    if isinstance(destination, dict):
        destination_airport = destination.get("id") or destination.get("iata") or ""
        destination_city = destination.get("city") or destination.get("name")
    else:
        destination_airport = str(destination)
        destination_city = None
    outbound_value = item.get("outbound_date") or item.get("departure_date")
    return_value = item.get("return_date")
    if outbound_value is None or return_value is None:
        raise ValueError("missing dates")
    outbound = parse_date(outbound_value)
    ret = parse_date(return_value)
    airlines = item.get("airlines") or item.get("airline") or []
    if isinstance(airlines, str):
        airlines = [airlines]
    nights = (ret - outbound).days
    return DealCandidate(
        source="serpapi",
        origin_airport=origin,
        destination_airport=destination_airport,
        destination_city=destination_city,
        outbound_date=outbound,
        return_date=ret,
        nights=nights,
        total_price=price,
        currency=item.get("currency", "EUR"),
        airlines=list(airlines),
        is_direct=item.get("stops") == 0 if "stops" in item else item.get("is_direct"),
        has_connection=item.get("stops", 0) > 0 if "stops" in item else item.get("has_connection"),
        outbound_duration_hours=item.get("outbound_duration_hours"),
        return_duration_hours=item.get("return_duration_hours"),
        max_layover_hours=item.get("max_layover_hours"),
        booking_url=item.get("booking_url") or item.get("link"),
        raw_payload=scrub_payload(item),
        confidence="high" if price and destination_airport else "medium",
    )
