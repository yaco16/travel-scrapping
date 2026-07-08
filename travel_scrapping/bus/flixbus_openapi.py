from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.bus.base import BusProvider
from travel_scrapping.bus.flixbus_autocomplete import (
    AUTOCOMPLETE_URL,
    AutocompleteDiagnostic,
    autocomplete_city,
    find_cached_mapping,
    mapping_from_result,
)
from travel_scrapping.config import Settings
from travel_scrapping.schemas import Offer
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import ProviderStatus

FLIXBUS_SEARCH_URL = "https://global.api.flixbus.com/search/service/v4/search"


@dataclass(frozen=True)
class CityLookupDiagnostic:
    query: str
    endpoint: str
    params: dict[str, Any]
    status_code: int | None
    raw_summary: str
    city_id: str | None
    legacy_id: str | None
    error: str | None
    results: list[dict[str, Any]]
    source: str
    id_kind: str = "uuid"
    ambiguous: bool = False


class FlixBusOpenApiProvider(BusProvider):
    name = "flixbus_openapi"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_status_code: int | None = None
        self.last_path: str | None = None
        self.last_error: str | None = None
        self.last_attempted = False
        self.last_ok = True
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_public_params: dict[str, Any] = {}
        self.last_destination_examples: list[str] = []
        self.last_city_lookups: list[CityLookupDiagnostic] = []
        self._city_cache: dict[str, str | None] = {}
        self.last_lookup_source = "none"
        self.last_lookup_ambiguous = False
        self.last_lookup_status_code: int | None = None
        self.last_search_status_code: int | None = None
        self.last_from_city_id: str | None = None
        self.last_to_city_id: str | None = None
        self.last_from_legacy_id: str | None = None
        self.last_to_legacy_id: str | None = None
        self.last_id_kind = "uuid"

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
            lookup = await self.city_search(client, query)
            return lookup.results

    async def city_search(self, client: httpx.AsyncClient, query: str) -> CityLookupDiagnostic:
        self.last_attempted = True
        self.last_path = AUTOCOMPLETE_URL
        cached = find_cached_mapping(query)
        if cached:
            reservation_city_id = str(cached.get("id") or "")
            legacy_id = str(cached.get("legacy_id") or "") or None
            lookup = CityLookupDiagnostic(
                query=query,
                endpoint="cache:data/cache/flixbus_city_ids.json",
                params={"query": query},
                status_code=None,
                raw_summary="cache hit",
                city_id=reservation_city_id or None,
                legacy_id=legacy_id,
                error=None,
                results=[cached],
                source="cache",
                id_kind="uuid",
            )
            self.last_city_lookups.append(lookup)
            self.last_lookup_source = "cache"
            self.last_raw_count = 1
            self.last_normalized_count = 1
            self.last_error = None
            return lookup

        diagnostic = await autocomplete_city(query, client=client)
        lookup = _lookup_from_autocomplete(diagnostic)
        self.last_status_code = diagnostic.status_code
        self.last_lookup_status_code = diagnostic.status_code
        self.last_public_params = dict(diagnostic.params)
        self.last_lookup_source = "autocomplete" if diagnostic.status_code is not None else "none"
        self.last_lookup_ambiguous = self.last_lookup_ambiguous or diagnostic.ambiguous
        self.last_raw_count = diagnostic.raw_count
        self.last_normalized_count = 1 if lookup.city_id else 0
        self.last_error = lookup.error
        self.last_ok = lookup.error is None
        self.last_city_lookups.append(lookup)
        return lookup

    async def _resolve_city_id(self, client: httpx.AsyncClient, name: str, *, use_legacy_id: bool = False) -> str | None:
        if name in self._city_cache:
            return self._city_cache[name]
        lookup = await self.city_search(client, name)
        resolved = lookup.legacy_id if use_legacy_id else lookup.city_id
        self._city_cache[name] = resolved
        return resolved

    async def search_roundtrip(
        self,
        origin: str,
        destination: str,
        depart: str,
        ret: str,
        *,
        use_legacy_id: bool = False,
    ) -> list[Offer]:
        self.last_city_lookups = []
        self._city_cache = {}
        self.last_lookup_source = "none"
        self.last_lookup_ambiguous = False
        self.last_lookup_status_code = None
        self.last_search_status_code = None
        self.last_from_city_id = None
        self.last_to_city_id = None
        self.last_from_legacy_id = None
        self.last_to_legacy_id = None
        self.last_id_kind = "legacy" if use_legacy_id else "uuid"
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            from_id = await self._resolve_city_id(client, origin, use_legacy_id=use_legacy_id)
            to_id = await self._resolve_city_id(client, destination, use_legacy_id=use_legacy_id)
            self.last_from_city_id = from_id
            self.last_to_city_id = to_id
            if self.last_city_lookups:
                self.last_from_legacy_id = self.last_city_lookups[0].legacy_id
            if len(self.last_city_lookups) > 1:
                self.last_to_legacy_id = self.last_city_lookups[1].legacy_id

            if not from_id or not to_id:
                self.last_ok = False
                detail = "; ".join(
                    f"{lookup.query}: {lookup.error or 'city_id absent'}"
                    for lookup in self.last_city_lookups[-2:]
                    if not lookup.city_id
                )
                missing_label = "legacy_id" if use_legacy_id else "id UUID"
                self.last_error = f"{missing_label} absent: {origin!r} or {destination!r}"
                if detail:
                    self.last_error = f"{self.last_error} ({detail})"
                self.last_public_params = {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": depart,
                    "return_date": ret,
                    "lookup_source": self.last_lookup_source,
                    "from_city_id": from_id,
                    "from_legacy_id": self.last_from_legacy_id,
                    "to_city_id": to_id,
                    "to_legacy_id": self.last_to_legacy_id,
                    "id_kind": self.last_id_kind,
                    "lookup_ambiguous": self.last_lookup_ambiguous,
                    "note": "stop_id GTFS != id reservation",
                }
                self.last_normalized_count = 0
                return []

            params: dict[str, Any] = {
                "from_city_id": from_id,
                "to_city_id": to_id,
                "departure_date": _search_date(depart),
                "number_adult": 1,
                "products": json.dumps({"adult": 1}, separators=(",", ":")),
                "search_by": "cities",
                "currency": "EUR",
            }
            self.last_path = FLIXBUS_SEARCH_URL
            self.last_attempted = True
            self.last_public_params = {
                **params,
                "from_legacy_id": self.last_from_legacy_id,
                "to_legacy_id": self.last_to_legacy_id,
                "id_kind": self.last_id_kind,
                "lookup_source": self.last_lookup_source,
                "lookup_ambiguous": self.last_lookup_ambiguous,
            }
            self.last_destination_examples = [destination]
            resp = await client.get(FLIXBUS_SEARCH_URL, params=params, headers=_headers())
            self.last_status_code = resp.status_code
            self.last_search_status_code = resp.status_code

            payload: Any
            try:
                payload = resp.json()
            except ValueError:
                payload = {"error": resp.text[:300]}

            if self.settings.flixbus_debug_save:
                _save_debug(payload if isinstance(payload, dict) else {"raw": payload}, prefix="flixbus-openapi")

            if resp.status_code >= 400:
                self.last_ok = False
                self.last_raw_count = _trip_count(payload)
                self.last_normalized_count = 0
                self.last_error = str(payload.get("message") or payload.get("error") or "")[:300]
                return []

            self.last_raw_count = _trip_count(payload)
            offers = _parse_trips(payload, origin=origin, destination=destination, from_id=from_id, to_id=to_id, ret=ret)
            self.last_normalized_count = len(offers)
            self.last_ok = True
            return offers


def _trip_count(payload: Any) -> int:
    if isinstance(payload, dict):
        trips = payload.get("trips") or payload.get("results") or payload.get("data") or []
    elif isinstance(payload, list):
        trips = payload
    else:
        trips = []
    if isinstance(trips, list):
        total = 0
        for trip in trips:
            if isinstance(trip, dict) and isinstance(trip.get("results"), dict):
                total += len(trip["results"])
            else:
                total += 1
        return total
    return len(trips) if isinstance(trips, dict) else 0


def _payload_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("message") or payload.get("error")
    return str(value)[:300] if value else None


def _payload_summary(payload: Any) -> str:
    if isinstance(payload, list):
        first = payload[0] if payload and isinstance(payload[0], dict) else {}
        keys = ",".join(sorted(first.keys())[:8])
        return f"list count={len(payload)} first_keys={keys}"
    if isinstance(payload, dict):
        keys = ",".join(sorted(payload.keys())[:8])
        message = payload.get("message") or payload.get("error")
        suffix = f" message={str(message)[:120]}" if message else ""
        return f"dict keys={keys}{suffix}"
    if payload in ({}, None):
        return "empty"
    return type(payload).__name__


def _lookup_from_autocomplete(diagnostic: AutocompleteDiagnostic) -> CityLookupDiagnostic:
    city_id: str | None = None
    legacy_id: str | None = None
    error = diagnostic.error
    if diagnostic.selected and diagnostic.selected.get("id"):
        mapping = mapping_from_result(diagnostic.query, diagnostic.selected)
        city_id = str(mapping["id"])
        legacy_id = str(mapping.get("legacy_id") or "") or None
        error = None
    elif diagnostic.ambiguous:
        error = "autocomplete ambiguous"
    elif not error:
        error = "id UUID absent dans autocomplete"
    raw_summary = f"autocomplete count={diagnostic.raw_count}"
    return CityLookupDiagnostic(
        query=diagnostic.query,
        endpoint=diagnostic.endpoint,
        params=diagnostic.params,
        status_code=diagnostic.status_code,
        raw_summary=raw_summary,
        city_id=city_id,
        legacy_id=legacy_id,
        error=error,
        results=diagnostic.results,
        source="autocomplete",
        id_kind="uuid",
        ambiguous=diagnostic.ambiguous,
    )


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
    for trip in _iter_trip_rows(trips):
        if not isinstance(trip, dict):
            continue
        try:
            depart_raw = _date_value(trip.get("departure_at") or trip.get("departure") or trip.get("start_datetime"))
            arrive_raw = _date_value(trip.get("arrival_at") or trip.get("arrival") or trip.get("end_datetime"))
            depart_dt = _parse_dt(depart_raw)
            arrive_dt = _parse_dt(arrive_raw)
            if depart_dt is None or arrive_dt is None:
                continue

            price_raw = trip.get("price") or trip.get("total") or {}
            price_val = _float_or_none(_price_value(price_raw))
            if price_val is None:
                continue
            currency = str(
                trip.get("currency")
                or (price_raw.get("currency") if isinstance(price_raw, dict) else "")
                or "EUR"
            )

            operator_raw = trip.get("operator") or trip.get("provider") or trip.get("carrier") or trip.get("brand")
            operator = (
                str(operator_raw.get("name") or "")
                if isinstance(operator_raw, dict)
                else str(operator_raw or "")
            )
            if not operator:
                continue

            booking_url = str(
                trip.get("booking_url")
                or trip.get("url")
                or trip.get("link")
                or trip.get("booking_link")
                or trip.get("deeplink")
                or ""
            )
            if not booking_url:
                continue

            ret_dt = _parse_dt(ret)
            if ret_dt is None:
                ret_dt = arrive_dt

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
                    price_currency=currency,
                    operator_name=operator,
                    duration_minutes=duration,
                    stops_count=0,
                    booking_url=booking_url,
                    confidence="high",
                    raw_payload=scrub_payload(trip),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return offers


def _iter_trip_rows(trips: Any) -> list[dict[str, Any]]:
    if not isinstance(trips, list):
        return []
    rows: list[dict[str, Any]] = []
    for trip in trips:
        if not isinstance(trip, dict):
            continue
        nested = trip.get("results")
        if isinstance(nested, dict):
            rows.extend(row for row in nested.values() if isinstance(row, dict))
        else:
            rows.append(trip)
    return rows


def _date_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("date")
    return value


def _price_value(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return value.get("amount") or value.get("total") or value.get("total_with_platform_fee")


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


def _search_date(value: str) -> str:
    parsed = _parse_dt(value)
    if parsed is None:
        return value
    return parsed.strftime("%d.%m.%Y")


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
