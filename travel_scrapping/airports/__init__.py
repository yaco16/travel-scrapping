from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from travel_scrapping.config import Settings
from travel_scrapping.db import AirportMetadata, OurAirport, PriceObservation

FRENCH_CITY_BY_IATA = {
    "VCE": "Venise",
    "SVQ": "Séville",
    "BTS": "Bratislava",
    "BCN": "Barcelone",
    "NCE": "Nice",
    "CDG": "Paris",
    "ORY": "Paris",
    "BVA": "Paris",
    "LYS": "Lyon",
    "MRS": "Marseille",
    "TLS": "Toulouse",
    "BOD": "Bordeaux",
    "NTE": "Nantes",
    "LIL": "Lille",
    "GVA": "Genève",
    "BRU": "Bruxelles",
    "FCO": "Rome",
    "CIA": "Rome",
    "MXP": "Milan",
    "LIN": "Milan",
    "BGY": "Milan",
    "MAD": "Madrid",
    "LIS": "Lisbonne",
    "OPO": "Porto",
    "LHR": "Londres",
    "LGW": "Londres",
    "STN": "Londres",
    "LTN": "Londres",
    "AMS": "Amsterdam",
    "BER": "Berlin",
    "PRG": "Prague",
    "BUD": "Budapest",
    "VIE": "Vienne",
    "ATH": "Athènes",
    "IST": "Istanbul",
}


@dataclass(frozen=True)
class AirportInfo:
    iata: str
    airport_name: str | None
    city: str | None
    country: str | None
    timezone: str | None
    latitude: float | None
    longitude: float | None
    source: str
    city_fr: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def display_name(self) -> str:
        return self.city_fr or self.city or f"{self.iata} inconnu"


@dataclass(frozen=True)
class AirportResolveResult:
    info: AirportInfo
    cache_hit: bool = False


def normalize_iata(iata_code: str | None) -> str:
    return str(iata_code or "").strip().upper()


def fallback_airport(iata_code: str) -> AirportInfo | None:
    code = normalize_iata(iata_code)
    city_fr = FRENCH_CITY_BY_IATA.get(code)
    if not city_fr:
        return None
    return AirportInfo(
        iata=code,
        airport_name=None,
        city=city_fr,
        city_fr=city_fr,
        country=None,
        timezone=None,
        latitude=None,
        longitude=None,
        source="fallback",
    )


def unknown_airport(iata_code: str) -> AirportInfo:
    code = normalize_iata(iata_code) or "???"
    return AirportInfo(
        iata=code,
        airport_name=None,
        city=None,
        city_fr=None,
        country=None,
        timezone=None,
        latitude=None,
        longitude=None,
        source="unknown",
    )


def info_from_cache(row: AirportMetadata) -> AirportInfo:
    raw_payload = None
    if row.raw_payload:
        try:
            parsed = json.loads(row.raw_payload)
            raw_payload = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            raw_payload = None
    return AirportInfo(
        iata=row.iata,
        airport_name=row.airport_name,
        city=row.city,
        city_fr=row.city_fr,
        country=row.country,
        timezone=row.timezone,
        latitude=row.latitude,
        longitude=row.longitude,
        source=row.source,
        raw_payload=raw_payload,
    )


def cache_airport(session: Session, info: AirportInfo) -> None:
    try:
        payload = json.dumps(info.raw_payload, ensure_ascii=True) if info.raw_payload is not None else None
        row = session.get(AirportMetadata, info.iata)
        values = {
            "city": info.city,
            "city_fr": info.city_fr,
            "airport_name": info.airport_name,
            "country": info.country,
            "timezone": info.timezone,
            "latitude": info.latitude,
            "longitude": info.longitude,
            "source": info.source,
            "fetched_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "raw_payload": payload,
        }
        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            session.add(AirportMetadata(iata=info.iata, **values))
        session.flush()
    except SQLAlchemyError:
        session.rollback()


def resolve_airport(
    iata_code: str | None,
    settings: Settings,
    session: Session | None = None,
    *,
    force: bool = False,
) -> AirportResolveResult:
    code = normalize_iata(iata_code)
    if not code:
        return AirportResolveResult(unknown_airport(code))

    order = [part.strip().lower() for part in settings.airport_resolver_order.split(",") if part.strip()]

    info = None
    api_attempted = False
    for source in order:
        if source == "cache" and session is not None and not force:
            try:
                cached = session.get(AirportMetadata, code)
                if cached:
                    return AirportResolveResult(info_from_cache(cached), cache_hit=True)
            except SQLAlchemyError:
                session.rollback()
        elif source == "ourairports" and session is not None and settings.ourairports_enabled:
            from travel_scrapping.airports.ourairports import lookup_airport

            info = lookup_airport(session, code)
            if info is not None:
                break
        elif source in {"ninja", "api_ninjas"} and settings.api_ninjas_enabled and settings.api_ninjas_api_key:
            from travel_scrapping.providers.api_ninjas_airports import fetch_airport_by_iata

            api_attempted = True
            info = fetch_airport_by_iata(code, settings=settings)
            if info is not None:
                break
        elif source == "fallback":
            info = fallback_airport(code)
            if info is not None:
                break

    if info is None and settings.api_ninjas_enabled and settings.api_ninjas_api_key and "ninja" not in order:
        from travel_scrapping.providers.api_ninjas_airports import fetch_airport_by_iata

        api_attempted = True
        info = fetch_airport_by_iata(code, settings=settings)

    if info is None:
        info = fallback_airport(code) or unknown_airport(code)

    should_cache = info.source != "unknown" or api_attempted
    if session is not None and should_cache:
        cache_airport(session, info)

    return AirportResolveResult(info)


def count_cached_airports(session: Session) -> int:
    return session.scalar(select(func.count(AirportMetadata.iata))) or 0


def count_ourairports(session: Session) -> int:
    return session.scalar(select(func.count(OurAirport.iata_code))) or 0


def destination_display_name(iata_code: str | None, city: str | None = None) -> str:
    code = normalize_iata(iata_code)
    fallback = fallback_airport(code)
    if fallback:
        return fallback.display_name
    if city:
        return city
    return f"{code} inconnu" if code else "Destination inconnue"


def collect_observation_iata_codes(session: Session, origin_airport: str) -> list[str]:
    codes = {normalize_iata(origin_airport)}
    rows = session.execute(select(PriceObservation.origin_iata, PriceObservation.destination_iata))
    for row in rows:
        for airport_code in (row.origin_iata, row.destination_iata):
            code = normalize_iata(airport_code)
            if code:
                codes.add(code)
    return sorted(codes)
