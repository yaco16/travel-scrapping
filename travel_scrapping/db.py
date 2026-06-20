from __future__ import annotations

import hashlib
import json
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, and_, create_engine, or_, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker
from sqlalchemy.sql.elements import ColumnElement

from travel_scrapping.config import Settings
from travel_scrapping.schemas import DealCandidate


class Base(DeclarativeBase):
    pass


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    cheapest_price_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    deals: Mapped[list["Deal"]] = relationship(back_populates="run")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"))
    source: Mapped[str] = mapped_column(String(64))
    transport_mode: Mapped[str] = mapped_column(String(16), default="flight")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    origin_airport: Mapped[str] = mapped_column(String(8))
    destination_airport: Mapped[str] = mapped_column(String(8))
    destination_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    destination_country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    outbound_date: Mapped[object] = mapped_column(Date)
    return_date: Mapped[object] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer)
    total_price: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(8))
    total_price_eur: Mapped[float] = mapped_column(Float)
    airlines_json: Mapped[str] = mapped_column(Text, default="[]")
    flight_numbers_json: Mapped[str] = mapped_column(Text, default="[]")
    is_direct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    has_connection: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    self_transfer: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    outbound_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    return_duration_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_layover_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stops_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    actionable: Mapped[bool] = mapped_column(Boolean, default=True)
    missing_fields_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_debug_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(String(16))
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    raw_payload_z: Mapped[bytes | None] = mapped_column(nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    run: Mapped[SearchRun] = relationship(back_populates="deals")


class PriceObservation(Base):
    __tablename__ = "price_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_key: Mapped[str] = mapped_column(String(128), index=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    origin_iata: Mapped[str | None] = mapped_column(String(8), nullable=True)
    destination_iata: Mapped[str | None] = mapped_column(String(8), nullable=True)
    destination_city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    departure_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    return_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    nights: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    airline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(16), nullable=True)
    warnings: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_eur: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))


class OurAirport(Base):
    __tablename__ = "ourairports_airports"

    iata_code: Mapped[str] = mapped_column(String(8), primary_key=True)
    ident: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    municipality: Mapped[str | None] = mapped_column(String(128), nullable=True)
    iso_country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    iso_region: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_ft: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scheduled_service: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="ourairports")
    imported_at: Mapped[datetime] = mapped_column(DateTime)


def valid_price_observation_clause() -> ColumnElement[bool]:
    return and_(
        PriceObservation.run_id.is_not(None),
        PriceObservation.origin_iata.is_not(None),
        PriceObservation.destination_iata.is_not(None),
        PriceObservation.departure_date.is_not(None),
        PriceObservation.return_date.is_not(None),
        PriceObservation.nights.is_not(None),
        PriceObservation.price.is_not(None),
        PriceObservation.currency.is_not(None),
    )


def invalid_price_observation_clause() -> ColumnElement[bool]:
    return or_(
        PriceObservation.run_id.is_(None),
        PriceObservation.origin_iata.is_(None),
        PriceObservation.destination_iata.is_(None),
        PriceObservation.departure_date.is_(None),
        PriceObservation.return_date.is_(None),
        PriceObservation.nights.is_(None),
        PriceObservation.price.is_(None),
        PriceObservation.currency.is_(None),
    )


def missing_observation_fields(run_id: int | None, deal: DealCandidate) -> list[str]:
    fields = {
        "run_id": run_id,
        "origin_iata": deal.origin_airport,
        "destination_iata": deal.destination_airport,
        "departure_date": deal.outbound_date,
        "return_date": deal.return_date,
        "nights": deal.nights,
        "price": deal.total_price,
        "currency": deal.currency,
    }
    return [name for name, value in fields.items() if value is None or value == ""]


class ProviderStatusRow(Base):
    __tablename__ = "provider_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"))
    name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean)
    ok: Mapped[bool] = mapped_column(Boolean)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_present: Mapped[bool] = mapped_column(Boolean, default=False)
    attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    normalized_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    main_rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_params_json: Mapped[str] = mapped_column(Text, default="{}")
    destination_examples_json: Mapped[str] = mapped_column(Text, default="[]")


class AirportMetadata(Base):
    __tablename__ = "airport_metadata"

    iata: Mapped[str] = mapped_column(String(8), primary_key=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city_fr: Mapped[str | None] = mapped_column(String(128), nullable=True)
    airport_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


def engine_from_settings(settings: Settings):
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True)


def init_db(settings: Settings) -> sessionmaker[Session]:
    engine = engine_from_settings(settings)
    Base.metadata.create_all(engine)
    migrate_sqlite(engine)
    return sessionmaker(engine, expire_on_commit=False)


def migrate_sqlite(engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    columns = {
        "transport_mode": "VARCHAR(16) DEFAULT 'flight'",
        "provider": "VARCHAR(64)",
        "run_id": "INTEGER",
        "origin_iata": "VARCHAR(8)",
        "destination_iata": "VARCHAR(8)",
        "destination_city": "VARCHAR(128)",
        "departure_date": "DATE",
        "return_date": "DATE",
        "nights": "INTEGER",
        "price": "FLOAT",
        "currency": "VARCHAR(8)",
        "airline": "VARCHAR(64)",
        "confidence": "VARCHAR(16)",
        "warnings": "TEXT",
        "booking_url": "TEXT",
        "raw_payload_hash": "VARCHAR(64)",
    }
    deal_columns = {
        "transport_mode": "VARCHAR(16) DEFAULT 'flight'",
        "provider": "VARCHAR(64)",
        "operator_name": "VARCHAR(128)",
        "duration_minutes": "INTEGER",
        "stops_count": "INTEGER",
        "average_price": "FLOAT",
        "discount_percent": "FLOAT",
        "image_url": "TEXT",
        "actionable": "BOOLEAN DEFAULT 1",
        "missing_fields_json": "TEXT DEFAULT '[]'",
        "raw_debug_path": "TEXT",
    }
    provider_status_columns = {
        "key_present": "BOOLEAN DEFAULT 0",
        "attempted": "BOOLEAN DEFAULT 0",
        "http_status": "INTEGER",
        "raw_count": "INTEGER DEFAULT 0",
        "normalized_count": "INTEGER DEFAULT 0",
        "accepted_count": "INTEGER DEFAULT 0",
        "rejected_count": "INTEGER DEFAULT 0",
        "main_rejection_reason": "TEXT",
        "request_params_json": "TEXT DEFAULT '{}'",
        "destination_examples_json": "TEXT DEFAULT '[]'",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(price_observations)"))}
        for name, column_type in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE price_observations ADD COLUMN {name} {column_type}"))
        existing_deals = {row[1] for row in conn.execute(text("PRAGMA table_info(deals)"))}
        for name, column_type in deal_columns.items():
            if name not in existing_deals:
                conn.execute(text(f"ALTER TABLE deals ADD COLUMN {name} {column_type}"))
        existing_statuses = {row[1] for row in conn.execute(text("PRAGMA table_info(provider_statuses)"))}
        for name, column_type in provider_status_columns.items():
            if name not in existing_statuses:
                conn.execute(text(f"ALTER TABLE provider_statuses ADD COLUMN {name} {column_type}"))


@contextmanager
def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def compress_payload(payload: dict) -> bytes:
    data = json.dumps(payload, ensure_ascii=True)[:20_000].encode()
    return zlib.compress(data)


def raw_payload_hash(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode()
    return hashlib.sha256(data).hexdigest()


def deal_to_row(run_id: int, deal: DealCandidate) -> Deal:
    return Deal(
        run_id=run_id,
        source=deal.source,
        transport_mode=deal.transport_mode,
        provider=deal.provider or deal.source,
        origin_airport=deal.origin_airport,
        destination_airport=deal.destination_airport,
        destination_city=deal.destination_city,
        destination_country=deal.destination_country,
        outbound_date=deal.outbound_date,
        return_date=deal.return_date,
        nights=deal.nights,
        total_price=deal.total_price,
        currency=deal.currency,
        total_price_eur=float(deal.total_price_eur or deal.total_price),
        airlines_json=json.dumps(deal.airlines),
        flight_numbers_json=json.dumps(deal.flight_numbers),
        is_direct=deal.is_direct,
        has_connection=deal.has_connection,
        self_transfer=deal.self_transfer,
        outbound_duration_hours=deal.outbound_duration_hours,
        return_duration_hours=deal.return_duration_hours,
        max_layover_hours=deal.max_layover_hours,
        booking_url=deal.booking_url,
        operator_name=deal.operator_name,
        duration_minutes=deal.duration_minutes,
        stops_count=deal.stops_count,
        average_price=deal.average_price,
        discount_percent=deal.discount_percent,
        image_url=deal.image_url,
        actionable=deal.actionable,
        missing_fields_json=json.dumps(deal.missing_fields),
        raw_debug_path=deal.raw_debug_path,
        confidence=deal.confidence,
        warnings_json=json.dumps(deal.warnings),
        raw_payload_z=compress_payload(deal.raw_payload),
        fetched_at=deal.fetched_at.replace(tzinfo=None),
    )


def save_deals(session: Session, run: SearchRun, deals: list[DealCandidate]) -> int:
    inserted = 0
    for deal in deals:
        if not deal.actionable:
            continue
        missing = missing_observation_fields(run.id, deal)
        if missing:
            continue
        session.add(deal_to_row(run.id, deal))
        session.add(
            PriceObservation(
                route_key=deal.route_key,
                observed_at=deal.fetched_at.replace(tzinfo=None),
                run_id=run.id,
                origin_iata=deal.origin_airport,
                destination_iata=deal.destination_airport,
                destination_city=deal.destination_city or deal.destination_airport,
                departure_date=deal.outbound_date,
                return_date=deal.return_date,
                nights=deal.nights,
                price=deal.total_price,
                currency=deal.currency,
                airline=", ".join(deal.airlines) if deal.airlines else "Non communiqué",
                confidence=deal.confidence,
                warnings=json.dumps(deal.warnings),
                booking_url=deal.booking_url,
                raw_payload_hash=raw_payload_hash(deal.raw_payload),
                price_eur=float(deal.total_price_eur or deal.total_price),
                source=deal.source,
            )
        )
        inserted += 1
    return inserted
