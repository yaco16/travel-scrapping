from __future__ import annotations

import json
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

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
    price_eur: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(64))


class ProviderStatusRow(Base):
    __tablename__ = "provider_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("search_runs.id"))
    name: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(Boolean)
    ok: Mapped[bool] = mapped_column(Boolean)
    warnings_json: Mapped[str] = mapped_column(Text, default="[]")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


def engine_from_settings(settings: Settings):
    if settings.database_url.startswith("sqlite:///"):
        Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    return create_engine(settings.database_url, future=True)


def init_db(settings: Settings) -> sessionmaker[Session]:
    engine = engine_from_settings(settings)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


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


def deal_to_row(run_id: int, deal: DealCandidate) -> Deal:
    return Deal(
        run_id=run_id,
        source=deal.source,
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
        confidence=deal.confidence,
        warnings_json=json.dumps(deal.warnings),
        raw_payload_z=compress_payload(deal.raw_payload),
        fetched_at=deal.fetched_at.replace(tzinfo=None),
    )


def save_deals(session: Session, run: SearchRun, deals: list[DealCandidate]) -> None:
    for deal in deals:
        session.add(deal_to_row(run.id, deal))
        session.add(
            PriceObservation(
                route_key=deal.route_key,
                price_eur=float(deal.total_price_eur or deal.total_price),
                source=deal.source,
            )
        )
