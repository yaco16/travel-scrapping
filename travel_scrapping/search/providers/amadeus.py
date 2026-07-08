from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.normalizer import scrub_payload
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus

AMADEUS_TOKEN_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_INSPIRE_URL = "https://test.api.amadeus.com/v1/shopping/flight-destinations"
AMADEUS_BOOKING_TPL = (
    "https://www.amadeus.com/en/flights?origin={origin}&destination={dest}"
    "&departureDate={out}&returnDate={ret}&adults=1"
)


class AmadeusProvider(FlightProvider):
    name = "amadeus"

    def __init__(self, settings) -> None:
        super().__init__(settings)
        self._token: str | None = None
        self._token_expiry: datetime | None = None
        self.last_attempted = False
        self.last_status_code: int | None = None
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_public_params: dict[str, Any] = {}
        self.last_destination_examples: list[str] = []
        self.last_ok = True
        self.last_error: str | None = None

    def status(self) -> ProviderStatus:
        if not self.settings.amadeus_client_id or not self.settings.amadeus_client_secret:
            return ProviderStatus(
                self.name,
                enabled=False,
                warnings=["AMADEUS_CLIENT_ID ou AMADEUS_CLIENT_SECRET manquant"],
                key_present=False,
            )
        return ProviderStatus(self.name, enabled=True, key_present=True)

    async def _get_token(self, client: httpx.AsyncClient) -> str:
        now = datetime.now(timezone.utc)
        if self._token and self._token_expiry and now < self._token_expiry:
            return self._token
        response = await client.post(
            AMADEUS_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self.settings.amadeus_client_id,
                "client_secret": self.settings.amadeus_client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response.raise_for_status()
        data = response.json()
        self._token = data["access_token"]
        expires_in = int(data.get("expires_in", 1799))
        self._token_expiry = datetime(now.year, now.month, now.day, now.hour, now.minute, now.second, tzinfo=timezone.utc)
        from datetime import timedelta
        self._token_expiry = now + timedelta(seconds=expires_in - 30)
        return self._token  # type: ignore[return-value]

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        if not self.status().enabled:
            return []

        start = self.settings.search_start_date
        if start is None and date_pairs:
            start = date_pairs[0][0]
        if start is None:
            start = date.today()
        start = max(start, date.today())

        params: dict[str, Any] = {
            "origin": self.settings.origin_airport,
            "maxPrice": int(self.settings.max_roundtrip_price_eur),
            "currency": self.settings.default_currency,
            "viewBy": "DESTINATION",
        }
        if start:
            params["departureDate"] = start.isoformat()

        self.last_attempted = True
        self.last_ok = True
        self.last_error = None

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                token = await self._get_token(client)
            except Exception as exc:
                self.last_ok = False
                self.last_error = f"token error: {exc}"[:300]
                return []

            headers = {"Authorization": f"Bearer {token}"}
            response = await client.get(AMADEUS_INSPIRE_URL, params=params, headers=headers)
            self.last_status_code = response.status_code
            response.raise_for_status()
            payload = response.json()

        data = payload.get("data") or []
        self.last_raw_count = len(data)
        self.last_public_params = {k: v for k, v in params.items()}

        _save_debug(
            {"params": self.last_public_params, "http_status": self.last_status_code, "raw_count": len(data)},
            prefix="amadeus-inspire",
        )

        deals = _parse_inspire(
            data,
            origin=self.settings.origin_airport,
            min_nights=self.settings.min_nights,
            max_nights=self.settings.max_nights,
        )
        self.last_normalized_count = len(deals)
        self.last_destination_examples = [d.destination_airport for d in deals[:5]]
        return deals[:limit]


def _parse_inspire(
    data: list[dict[str, Any]], *, origin: str, min_nights: int = 1, max_nights: int = 7
) -> list[DealCandidate]:
    deals: list[DealCandidate] = []
    for item in data:
        try:
            dest = str(item.get("destination") or "")
            if not dest:
                continue
            depart_raw = str(item.get("departureDate") or "")
            return_raw = str(item.get("returnDate") or "")
            out_date = _parse_date(depart_raw)
            ret_date = _parse_date(return_raw)
            if out_date is None or ret_date is None:
                continue
            price_data = item.get("price") or {}
            price_val = _float_or_none(price_data.get("total") if isinstance(price_data, dict) else price_data)
            if price_val is None:
                continue
            nights = (ret_date - out_date).days
            if not min_nights <= nights <= max_nights:
                continue
            booking_url = AMADEUS_BOOKING_TPL.format(
                origin=origin, dest=dest, out=out_date.isoformat(), ret=ret_date.isoformat()
            )
            links = item.get("links") or {}
            if isinstance(links, dict) and links.get("flightDates"):
                booking_url = str(links["flightDates"])
            deals.append(
                DealCandidate(
                    source="amadeus",
                    origin_airport=origin,
                    destination_airport=dest,
                    outbound_date=out_date,
                    return_date=ret_date,
                    nights=nights,
                    total_price=price_val,
                    currency="EUR",
                    airlines=[],
                    booking_url=booking_url,
                    raw_payload=scrub_payload(item),
                    confidence="medium",
                    transport_mode="flight",
                    provider="amadeus",
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return deals


def _parse_date(value: str):
    if not value:
        return None
    from datetime import date
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
