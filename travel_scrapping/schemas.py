from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Literal


Confidence = Literal["high", "medium", "low"]


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
    booking_url: str | None = None
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: Confidence = "low"
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.total_price_eur is None and self.currency == "EUR":
            self.total_price_eur = self.total_price

    @property
    def route_key(self) -> str:
        return f"{self.origin_airport}-{self.destination_airport}:{self.outbound_date}:{self.return_date}"


@dataclass(frozen=True, slots=True)
class Destination:
    airport: str
    city: str
    country: str
