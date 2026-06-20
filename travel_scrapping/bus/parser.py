from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.schemas import Offer


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("amount") or value.get("value")
    if isinstance(value, str):
        value = value.replace("€", "").replace("EUR", "").replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _booking_url(row: dict[str, Any]) -> str | None:
    for key in ("booking_url", "deeplink", "deep_link", "url", "link"):
        value = row.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


def _operator(row: dict[str, Any]) -> str | None:
    for key in ("operator", "operator_name", "brand", "carrier", "company"):
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("name")
        if value:
            return str(value)
    return None


def parse_trips(
    payload: dict[str, Any] | list[Any],
    *,
    origin: str,
    destination: str,
    return_at: datetime | None = None,
    raw_debug_path: str | None = None,
) -> list[Offer]:
    offers: list[Offer] = []
    for row in _walk(payload):
        depart = _datetime(row.get("departure_at") or row.get("departure") or row.get("start_time"))
        arrive = _datetime(row.get("arrival_at") or row.get("arrival") or row.get("end_time"))
        price = _float_or_none(row.get("price") or row.get("total") or row.get("amount"))
        currency = str(row.get("currency") or row.get("price_currency") or "EUR")
        booking_url = _booking_url(row)
        operator = _operator(row) or "FlixBus"
        if depart is None or arrive is None:
            continue
        duration = int((arrive - depart).total_seconds() // 60)
        return_dt = return_at or arrive
        offers.append(
            Offer(
                id=str(row.get("id") or row.get("trip_id") or f"flixbus:{origin}:{destination}:{depart.isoformat()}"),
                transport_mode="bus",
                provider="flixbus_rapidapi",
                source="flixbus",
                origin_code=origin,
                origin_name=origin,
                destination_code=destination,
                destination_name=destination,
                departure_at=depart,
                return_at=return_dt,
                nights=max(0, (return_dt.date() - depart.date()).days),
                price_amount=price,
                price_currency=currency,
                operator_name=operator,
                duration_minutes=duration,
                stops_count=0,
                booking_url=booking_url,
                confidence="high" if price and booking_url else "medium",
                raw_debug_path=raw_debug_path,
                raw_payload=scrub_payload(row),
            )
        )
    return offers
