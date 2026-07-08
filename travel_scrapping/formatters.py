from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP


def format_date_fr(value: date | datetime | str | None, *, diagnostic: bool = False) -> str:
    if value is None:
        return "Non disponible" if diagnostic else ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = date.fromisoformat(value[:10])
            except ValueError:
                return "Non disponible" if diagnostic else ""
    return value.strftime("%d/%m/%y")


def format_datetime_fr(value: date | datetime | str | None, *, diagnostic: bool = False) -> str:
    if value is None:
        return "Non disponible" if diagnostic else ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return format_date_fr(value, diagnostic=diagnostic)
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%y %H:%M")
    return value.strftime("%d/%m/%y")


def format_price_fr(amount: float | int | Decimal | None, currency: str = "EUR", *, diagnostic: bool = False) -> str:
    if amount is None:
        return "Non disponible" if diagnostic else ""
    decimal = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    formatted = f"{decimal:,.2f}".replace(",", " ").replace(".", ",")
    symbol = "€" if currency == "EUR" else currency
    return f"{formatted} {symbol}".strip()


def format_clock_fr(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.strftime("%H:%M")


def format_duration(minutes: int | None, *, diagnostic: bool = False) -> str:
    if minutes is None:
        return "Non disponible" if diagnostic else ""
    hours, mins = divmod(minutes, 60)
    return f"{hours}h{mins:02d}"
