from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.bus.base import BusProvider
from travel_scrapping.config import Settings
from travel_scrapping.schemas import Offer
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import ProviderStatus

FLIXBUS_CITY_URL = "https://global.api.flixbus.com/search/service/cities/details"
FLIXBUS_SEARCH_URL = "https://global.api.flixbus.com/search/service/v4/search"
FLIXBUS_BOOKING_TPL = "https://shop.flixbus.com/search?departureCity={from_id}&arrivalCity={to_id}&rideDate={date}&adult=1"


class FlixBusOpenApiProvider(BusProvider):
    name = "flixbus_openapi"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_status_code: int | None = None
        self.last_path: str | None = None
        self.last_error: str | None = None
        self._city_cache: dict[str, str | None] = {}

    def status(self) -> ProviderStatus:
        if not self.settings.bus_enabled or not self.settings.flixbus_openapi_enabled:
            return ProviderStatus(
                self.name,
                enabled=False,
                warnings=["FlixBus Open API désactivé"],
                key_present=True,
            )
        return ProviderStatus(self.name, enabled=True, key_present=True)

    async def station_search(self, query: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(
                FLIXBUS_CITY_URL,
                params={"q": query, "lang": "fr"},
                headers=_headers(),
            )
            self.last_status_code = resp.status_code
            if resp.status_code >= 400:
                return []
            return resp.json() if isinstance(resp.json(), list) else []

    async def _resolve_city_id(self, client: httpx.AsyncClient, name: str) -> str | None:
        if name in self._city_cache:
            return self._city_cache[name]
        try:
            resp = await client.get(
                FLIXBUS_CITY_URL,
                params={"q": name, "lang": "fr"},
                headers=_headers(),
            )
            self.last_status_code = resp.status_code
            if resp.status_code >= 400:
                self._city_cache[name] = None
                return None
            data = resp.json()
            if isinstance(data, list) and data:
                city_id = str(data[0].get("id") or data[0].get("legacy_id") or "")
                self._city_cache[name] = city_id or None
                return self._city_cache[name]
        except Exception:
            pass
        self._city_cache[name] = None
        return None

    async def search_roundtrip(self, origin: str, destination: str, depart: str, ret: str) -> list[Offer]:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            from_id = await self._resolve_city_id(client, origin)
            to_id = await self._resolve_city_id(client, destination)

            if not from_id or not to_id:
                self.last_error = f"city not found: {origin!r} or {destination!r}"
                return []

            params: dict[str, Any] = {
                "from_city_id": from_id,
                "to_city_id": to_id,
                "departure_date": depart,
                "number_adult": 1,
                "search_by": "cities",
                "currency": "EUR",
            }
            self.last_path = FLIXBUS_SEARCH_URL
            resp = await client.get(FLIXBUS_SEARCH_URL, params=params, headers=_headers())
            self.last_status_code = resp.status_code

            payload: Any
            try:
                payload = resp.json()
            except ValueError:
                payload = {"error": resp.text[:300]}

            if self.settings.flixbus_debug_save:
                _save_debug(payload if isinstance(payload, dict) else {"raw": payload}, prefix="flixbus-openapi")

            if resp.status_code >= 400:
                self.last_error = str(payload.get("message") or payload.get("error") or "")[:300]
                return []

            return _parse_trips(payload, origin=origin, destination=destination, from_id=from_id, to_id=to_id, ret=ret)


def _parse_trips(
    payload: Any,
    *,
    origin: str,
    destination: str,
    from_id: str,
    to_id: str,
    ret: str,
) -> list[Offer]:
    trips = []
    if isinstance(payload, dict):
        trips = payload.get("trips") or payload.get("results") or payload.get("data") or []
    elif isinstance(payload, list):
        trips = payload

    offers: list[Offer] = []
    for trip in trips:
        if not isinstance(trip, dict):
            continue
        try:
            depart_raw = trip.get("departure_at") or trip.get("departure") or trip.get("start_datetime") or ""
            arrive_raw = trip.get("arrival_at") or trip.get("arrival") or trip.get("end_datetime") or ""
            depart_dt = _parse_dt(depart_raw)
            arrive_dt = _parse_dt(arrive_raw)
            if depart_dt is None or arrive_dt is None:
                continue

            price_raw = trip.get("price") or trip.get("total") or {}
            price_val = _float_or_none(price_raw.get("amount") if isinstance(price_raw, dict) else price_raw)
            if price_val is None:
                continue

            ret_dt = _parse_dt(ret)
            if ret_dt is None:
                ret_dt = arrive_dt

            booking_url = FLIXBUS_BOOKING_TPL.format(
                from_id=from_id,
                to_id=to_id,
                date=depart_dt.strftime("%d.%m.%Y"),
            )

            duration = int((arrive_dt - depart_dt).total_seconds() // 60)
            nights = max(0, (ret_dt.date() - depart_dt.date()).days)
            trip_id = str(trip.get("uid") or trip.get("id") or f"flixbus-oa:{origin}:{destination}:{depart_dt.isoformat()}")

            offers.append(
                Offer(
                    id=trip_id,
                    transport_mode="bus",
                    provider="flixbus_openapi",
                    source="flixbus",
                    origin_code=origin,
                    origin_name=origin,
                    destination_code=destination,
                    destination_name=destination,
                    departure_at=depart_dt,
                    return_at=ret_dt,
                    nights=nights,
                    price_amount=price_val,
                    price_currency="EUR",
                    operator_name="FlixBus",
                    duration_minutes=duration,
                    stops_count=0,
                    booking_url=booking_url,
                    confidence="high" if booking_url else "medium",
                    raw_payload=scrub_payload(trip),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return offers


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            from datetime import date
            d = date.fromisoformat(str(value)[:10])
            dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; travel-scrapping/1.0)",
        "Accept": "application/json",
    }


def _save_debug(payload: dict[str, Any], *, prefix: str) -> None:
    debug_dir = Path("data/debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = debug_dir / f"{prefix}-{ts}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
