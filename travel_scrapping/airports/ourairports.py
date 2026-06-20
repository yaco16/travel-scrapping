from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from travel_scrapping.airports import AirportInfo, FRENCH_CITY_BY_IATA, normalize_iata
from travel_scrapping.db import OurAirport

OURAIRPORTS_URL = "https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv"
DEFAULT_CSV_PATH = Path("data/sources/ourairports/airports.csv")


@dataclass(frozen=True)
class ImportResult:
    csv_path: Path
    imported: int


def _float_or_none(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _int_or_none(value: str | None) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def ensure_airports_csv(path: Path = DEFAULT_CSV_PATH, *, force_refresh: bool = False) -> Path:
    if path.exists() and not force_refresh:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(OURAIRPORTS_URL, timeout=30)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def import_csv(session: Session, csv_path: Path) -> int:
    imported_at = datetime.now(timezone.utc).replace(tzinfo=None)
    count = 0
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            code = normalize_iata(row.get("iata_code"))
            if not code:
                continue
            values: dict[str, Any] = {
                "ident": row.get("ident") or None,
                "type": row.get("type") or None,
                "name": row.get("name") or None,
                "municipality": row.get("municipality") or None,
                "iso_country": row.get("iso_country") or None,
                "iso_region": row.get("iso_region") or None,
                "latitude_deg": _float_or_none(row.get("latitude_deg")),
                "longitude_deg": _float_or_none(row.get("longitude_deg")),
                "elevation_ft": _int_or_none(row.get("elevation_ft")),
                "scheduled_service": row.get("scheduled_service") or None,
                "source": "ourairports",
                "imported_at": imported_at,
            }
            existing = session.get(OurAirport, code)
            if existing:
                for key, value in values.items():
                    setattr(existing, key, value)
            else:
                session.add(OurAirport(iata_code=code, **values))
            count += 1
    session.flush()
    return count


def import_ourairports(session: Session, *, force_refresh: bool = False) -> ImportResult:
    csv_path = ensure_airports_csv(force_refresh=force_refresh)
    return ImportResult(csv_path=csv_path, imported=import_csv(session, csv_path))


def lookup_airport(session: Session, iata_code: str) -> AirportInfo | None:
    code = normalize_iata(iata_code)
    if not code:
        return None
    row = session.scalars(select(OurAirport).where(OurAirport.iata_code == code)).first()
    if row is None:
        return None
    return AirportInfo(
        iata=code,
        airport_name=row.name,
        city=row.municipality,
        city_fr=FRENCH_CITY_BY_IATA.get(code),
        country=row.iso_country,
        timezone=None,
        latitude=row.latitude_deg,
        longitude=row.longitude_deg,
        source="ourairports",
        raw_payload={
            "iata_code": row.iata_code,
            "ident": row.ident,
            "type": row.type,
            "name": row.name,
            "municipality": row.municipality,
            "iso_country": row.iso_country,
            "iso_region": row.iso_region,
            "latitude_deg": row.latitude_deg,
            "longitude_deg": row.longitude_deg,
            "elevation_ft": row.elevation_ft,
            "scheduled_service": row.scheduled_service,
            "source": row.source,
        },
    )
