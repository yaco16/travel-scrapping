from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal


Confidence = Literal["high", "medium", "low"]
TransportMode = Literal["flight", "bus", "train"]


@dataclass(slots=True)
class Offer:
    id: str
    transport_mode: TransportMode
    provider: str
    source: str
    origin_code: str
    origin_name: str | None
    destination_code: str
    destination_name: str | None
    departure_at: datetime
    return_at: datetime
    nights: int
    price_amount: float | None
    price_currency: str
    operator_name: str | None
    duration_minutes: int | None = None
    stops_count: int | None = None
    booking_url: str | None = None
    actionable: bool = False
    confidence: Confidence = "low"
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    raw_debug_path: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        missing = list(self.missing_fields)
        required = {
            "price_amount": self.price_amount,
            "price_currency": self.price_currency,
            "operator_name": self.operator_name,
            "origin_code": self.origin_code,
            "destination_code": self.destination_code,
            "booking_url": self.booking_url,
        }
        for name, value in required.items():
            if value is None or value == "":
                missing.append(name)
        if self.price_currency != "EUR":
            missing.append("price_currency_eur")
        self.missing_fields = sorted(set(missing))
        self.actionable = not self.missing_fields

    def to_deal_candidate(self) -> "DealCandidate":
        airlines = [self.operator_name] if self.operator_name else []
        return DealCandidate(
            source=self.source,
            origin_airport=self.origin_code,
            destination_airport=self.destination_code,
            outbound_date=self.departure_at.date(),
            return_date=self.return_at.date(),
            nights=self.nights,
            total_price=float(self.price_amount or 0),
            currency=self.price_currency,
            destination_city=self.destination_name,
            outbound_departure_at=self.departure_at,
            outbound_arrival_at=(
                self.departure_at + timedelta(minutes=self.duration_minutes) if self.duration_minutes else None
            ),
            airlines=airlines,
            is_direct=(self.stops_count == 0 if self.stops_count is not None else None),
            has_connection=(self.stops_count > 0 if self.stops_count is not None else None),
            outbound_duration_hours=(self.duration_minutes / 60 if self.duration_minutes else None),
            booking_url=self.booking_url,
            raw_payload=self.raw_payload,
            fetched_at=self.created_at,
            confidence=self.confidence,
            warnings=self.warnings,
            transport_mode=self.transport_mode,
            provider=self.provider,
            operator_name=self.operator_name,
            duration_minutes=self.duration_minutes,
            stops_count=self.stops_count,
            actionable=self.actionable,
            missing_fields=self.missing_fields,
            raw_debug_path=self.raw_debug_path,
        )


@dataclass(slots=True)
class DealCandidate:
    source: str
    origin_airport: str
    destination_airport: str
    outbound_date: date
    return_date: date
    nights: int
    total_price: float
    currency: str = "EUR"
    total_price_eur: float | None = None
    destination_city: str | None = None
    destination_country: str | None = None
    airlines: list[str] = field(default_factory=list)
    flight_numbers: list[str] = field(default_factory=list)
    is_direct: bool | None = None
    has_connection: bool | None = None
    self_transfer: bool | None = None
    outbound_duration_hours: float | None = None
    return_duration_hours: float | None = None
    max_layover_hours: float | None = None
    has_overnight_airport: bool | None = None
    outbound_departure_at: datetime | None = None
    outbound_arrival_at: datetime | None = None
    booking_url: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: Confidence = "low"
    warnings: list[str] = field(default_factory=list)
    transport_mode: TransportMode = "flight"
    provider: str | None = None
    operator_name: str | None = None
    duration_minutes: int | None = None
    stops_count: int | None = None
    average_price: float | None = None
    discount_percent: float | None = None
    image_url: str | None = None
    actionable: bool = True
    missing_fields: list[str] = field(default_factory=list)
    raw_debug_path: str | None = None

    def __post_init__(self) -> None:
        if self.total_price_eur is None and self.currency == "EUR":
            self.total_price_eur = self.total_price
        if self.operator_name is None and self.airlines:
            self.operator_name = self.airlines[0]
        missing = list(self.missing_fields)
        required = {
            "total_price": self.total_price,
            "currency": self.currency,
            "operator_name": self.operator_name,
            "booking_url": self.booking_url,
        }
        for name, value in required.items():
            if value is None or value == "":
                missing.append(name)
        if self.currency != "EUR":
            missing.append("currency_eur")
        self.missing_fields = sorted(set(missing))
        self.actionable = not self.missing_fields

    @property
    def route_key(self) -> str:
        return f"{self.origin_airport}-{self.destination_airport}:{self.outbound_date}:{self.return_date}"


@dataclass(frozen=True, slots=True)
class Destination:
    airport: str
    city: str
    country: str
