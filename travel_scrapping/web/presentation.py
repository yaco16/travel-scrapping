from __future__ import annotations

import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

FRENCH_CITY_BY_IATA = {
    "BTS": "Bratislava",
    "VIE": "Vienne",
    "BRU": "Bruxelles",
    "PRG": "Prague",
    "BCN": "Barcelone",
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
    city = getattr(deal, "destination_city", None)
    airport = str(getattr(deal, "destination_airport", "") or "")
    return FRENCH_CITY_BY_IATA.get(airport.upper()) or city or airport


def short_date(value: date) -> str:
    return value.strftime("%d/%m/%y")


def price_display(value: float | int | Decimal | None) -> str:
    if value is None:
        return ""
    amount = Decimal(str(value))
    if amount == amount.to_integral():
        return str(int(amount))
    return str(amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


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
