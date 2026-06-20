from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

FRENCH_CITY_BY_IATA = {
    "BTS": "Bratislava",
    "VCE": "Venise",
    "SVQ": "Séville",
    "BCN": "Barcelone",
    "VIE": "Vienne",
    "BRU": "Bruxelles",
    "PRG": "Prague",
    "MAD": "Madrid",
    "FCO": "Rome",
    "CIA": "Rome",
    "MXP": "Milan",
}

WARNING_LABELS = {
    "cached or indicative fare; verify before booking": "Prix indicatif : à vérifier avant réservation",
    "connection status unknown": "Correspondance non vérifiée",
    "layover unknown": "Durée d’escale inconnue",
    "airline missing from source": "Compagnie non fournie par la source",
    "travelpayouts marker missing": "Lien indisponible : TRAVELPAYOUTS_MARKER manquant",
}


def parse_json_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item]


def destination_display(deal: Any) -> str:
    display_name = getattr(deal, "destination_display_name", None)
    if display_name:
        return str(display_name)
    city = getattr(deal, "destination_city", None)
    airport = str(getattr(deal, "destination_airport", "") or "")
    code = airport.upper()
    if code in FRENCH_CITY_BY_IATA:
        return FRENCH_CITY_BY_IATA[code]
    if city:
        return str(city)
    return f"{code} inconnu" if code else "Destination inconnue"


def short_date(value: date | datetime | str | None) -> str:
    if not value:
        return "Non disponible"
    if isinstance(value, str):
        try:
            value = date.fromisoformat(value[:10])
        except ValueError:
            return "Non disponible"
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%y")
    return "Non disponible"


def price_display(value: float | int | Decimal | None) -> str:
    if value is None:
        return "Non disponible"
    amount = Decimal(str(value))
    if amount == amount.to_integral():
        return f"{int(amount):,}".replace(",", " ")
    formatted = f"{amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    return formatted.replace(",", " ").replace(".", ",")


def airlines_display(airlines_json: str | None) -> str:
    airlines = parse_json_list(airlines_json)
    return ", ".join(airlines) if airlines else "Non communiqué"


def warnings_display(warnings_json: str | None) -> list[str]:
    return [WARNING_LABELS.get(warning, warning) for warning in parse_json_list(warnings_json)]


def booking_display(deal: Any) -> str:
    if getattr(deal, "booking_url", None):
        return ""
    warnings = parse_json_list(getattr(deal, "warnings_json", None))
    if "travelpayouts marker missing" in warnings:
        return WARNING_LABELS["travelpayouts marker missing"]
    return "Lien indisponible : source sans URL"
