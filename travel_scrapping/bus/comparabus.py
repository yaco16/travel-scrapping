from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import httpx

from travel_scrapping.bus.base import BusProvider
from travel_scrapping.config import Settings
from travel_scrapping.schemas import Offer
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import ProviderStatus

COMPARABUS_API_KEY = "cbapp_Paid\u0410pi"


class ComparabusProvider(BusProvider):
    name = "comparabus"

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

    def status(self) -> ProviderStatus:
        if not self.settings.bus_enabled or not self.settings.comparabus_enabled:
            return ProviderStatus(self.name, enabled=False, warnings=["Comparabus désactivé"], key_present=True)
        return ProviderStatus(self.name, enabled=True, key_present=True)

    async def station_search(self, query: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            payload = await self._get_json(client, "/api/stops/departure", {"q": query, "locale": "fr_FR"})
        return _stop_rows(payload)

    async def search_roundtrip(self, origin: str, destination: str, depart: str, ret: str) -> list[Offer]:
        self.last_attempted = True
        self.last_ok = True
        self.last_error = None
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_destination_examples = [destination]
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            origin_stop = await self._resolve_departure_stop(client, origin)
            if not origin_stop:
                return self._empty(f"stop départ introuvable ou ambigu: {origin}")
            destination_stop = await self._resolve_arrival_stop(client, destination, origin_stop["id"])
            if not destination_stop:
                return self._empty(f"stop arrivée introuvable ou ambigu: {destination}")

            route_params = {
                "depStopId": origin_stop["id"],
                "depStopName": origin_stop["name"],
                "arrStopId": destination_stop["id"],
                "arrStopName": destination_stop["name"],
                "dateFrom": depart,
                "type": "bus",
                "currency": "EUR",
                "locale": "fr_FR",
            }
            routes_payload = await self._get_json(client, "/api/routes", route_params)
            routes = [route for route in _route_rows(routes_payload) if route.get("type") == "bus"]
            self.last_raw_count = len(routes)
            self.last_public_params = {
                "depStopId": origin_stop["id"],
                "arrStopId": destination_stop["id"],
                "dateFrom": depart,
                "type": "bus",
                "route_count": len(routes),
            }
            if not routes:
                return []

            offers: list[Offer] = []
            for route in routes:
                price_params = {
                    "companyId": route.get("companyId"),
                    "stopExtDep": route.get("stopExtDep"),
                    "stopExtArr": route.get("stopExtArr"),
                    "stopIdDep": route.get("stopIdDep"),
                    "stopIdArr": route.get("stopIdArr"),
                    "dateFrom": depart,
                    "dateTo": ret,
                    "currency": "EUR",
                    "locale": "fr_FR",
                    "k": COMPARABUS_API_KEY,
                }
                prices_payload = await self._get_json(client, "/api/prices", price_params)
                offers.extend(
                    _parse_price_rows(
                        prices_payload,
                        origin=origin_stop,
                        destination=destination_stop,
                        depart=depart,
                        ret=ret,
                        base_url=self.settings.comparabus_base_url.rstrip("/"),
                    )
                )
            self.last_normalized_count = len(offers)
            return offers

    async def _resolve_departure_stop(self, client: httpx.AsyncClient, query: str) -> dict[str, Any] | None:
        payload = await self._get_json(client, "/api/stops/departure", {"q": query, "locale": "fr_FR"})
        return _select_stop(query, _stop_rows(payload))

    async def _resolve_arrival_stop(self, client: httpx.AsyncClient, query: str, stop_id: Any) -> dict[str, Any] | None:
        payload = await self._get_json(
            client,
            "/api/stops/arrival",
            {"q": query, "stopId": stop_id, "locale": "fr_FR"},
        )
        return _select_stop(query, _stop_rows(payload))

    async def _get_json(self, client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
        self.last_path = path
        self.last_public_params = dict(params)
        response = await client.get(
            self.settings.comparabus_base_url.rstrip("/") + path,
            params=params,
            headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
        )
        self.last_status_code = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text[:300]}
        if response.status_code >= 400:
            self.last_ok = False
            self.last_error = str(payload.get("detail") or payload.get("error") or response.status_code)[:300]
        return payload

    def _empty(self, error: str) -> list[Offer]:
        self.last_ok = False
        self.last_error = error
        self.last_normalized_count = 0
        return []


def _stop_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        return [row for row in payload["data"] if isinstance(row, dict) and row.get("id") and row.get("name")]
    return []


def _select_stop(query: str, rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized = query.casefold().strip()
    exact = [row for row in rows if str(row.get("name", "")).casefold().strip() == normalized]
    if len(exact) == 1:
        return exact[0]
    return rows[0] if len(rows) == 1 else None


def _route_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def _parse_price_rows(
    payload: Any,
    *,
    origin: dict[str, Any],
    destination: dict[str, Any],
    depart: str,
    ret: str,
    base_url: str,
) -> list[Offer]:
    if not isinstance(payload, dict):
        return []
    rows = payload.get("outbound")
    if not isinstance(rows, list):
        return []
    offers: list[Offer] = []
    for row in rows:
        if not isinstance(row, dict) or row.get("type") != "bus" or row.get("full"):
            continue
        depart_dt = _parse_comparabus_datetime(row.get("depDatetime"))
        arrive_dt = _parse_comparabus_datetime(row.get("arrDatetime"))
        price = _price_amount(row)
        booking_url = _booking_url(row, depart=depart, ret=ret, base_url=base_url)
        operator = row.get("carrierName") or row.get("companyName")
        if depart_dt is None or arrive_dt is None or price is None or not operator or not booking_url:
            continue
        ret_dt = _parse_return_date(ret) or arrive_dt
        offers.append(
            Offer(
                id=f"comparabus:{row.get('id') or row.get('companyId')}:{depart_dt.isoformat()}",
                transport_mode="bus",
                provider="comparabus",
                source="comparabus",
                origin_code=str(origin["id"]),
                origin_name=str(origin["name"]),
                destination_code=str(destination["id"]),
                destination_name=str(destination["name"]),
                departure_at=depart_dt,
                return_at=ret_dt,
                nights=max(0, (ret_dt.date() - depart_dt.date()).days),
                price_amount=price,
                price_currency=str(row.get("currency") or "EUR"),
                operator_name=str(operator),
                duration_minutes=int(row["duration"]) if row.get("duration") is not None else None,
                stops_count=int(row.get("connection") or 0),
                booking_url=booking_url,
                confidence="medium",
                raw_payload=_route_payload(row, origin=origin, destination=destination),
            )
        )
    return offers


def _route_payload(row: dict[str, Any], *, origin: dict[str, Any], destination: dict[str, Any]) -> dict[str, Any]:
    payload = scrub_payload(row)
    departure_station = str(
        row.get("depStopName")
        or row.get("departure_station_name")
        or row.get("stopNameDep")
        or origin.get("name")
        or ""
    )
    arrival_station = str(
        row.get("arrStopName")
        or row.get("arrival_station_name")
        or row.get("stopNameArr")
        or destination.get("name")
        or ""
    )
    payload["departure_station_name"] = departure_station
    payload["arrival_station_name"] = arrival_station
    payload["legs"] = [
        {
            "departure_station_name": departure_station,
            "arrival_station_name": arrival_station,
            "departure_at": row.get("depDatetime"),
            "arrival_at": row.get("arrDatetime"),
            "duration_minutes": row.get("duration"),
        }
    ]
    try:
        connections = int(row.get("connection") or 0)
    except (TypeError, ValueError):
        connections = 0
    if connections > 0:
        payload["stopover_details_available"] = False
    return payload


def _parse_comparabus_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_return_date(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _price_amount(row: dict[str, Any]) -> float | None:
    cents = row.get("cents")
    if cents is None:
        return None
    try:
        return float(cents) / 100
    except (TypeError, ValueError):
        return None


def _booking_url(row: dict[str, Any], *, depart: str, ret: str, base_url: str) -> str | None:
    required = ("companyId", "stopExtDep", "stopExtArr", "stopIdDep", "stopIdArr", "cents", "depDatetime", "type", "link")
    if any(row.get(key) in (None, "") for key in required):
        return None
    params = {
        "companyId": row["companyId"],
        "depStopExt": row["stopExtDep"],
        "arrStopExt": row["stopExtArr"],
        "depStopId": row["stopIdDep"],
        "arrStopId": row["stopIdArr"],
        "cents": row["cents"],
        "dateFrom": depart,
        "datetimeFrom": row["depDatetime"],
        "dateTo": ret,
        "link": row["link"],
        "type": row["type"],
    }
    return f"{base_url}/fr/redirect?{urlencode(params)}"
