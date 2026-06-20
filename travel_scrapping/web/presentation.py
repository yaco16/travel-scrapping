from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from travel_scrapping.airports import destination_display_name
from travel_scrapping.formatters import format_date_fr, format_duration, format_price_fr

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
    return destination_display_name(
        getattr(deal, "destination_airport", None),
        getattr(deal, "destination_city", None),
    )


def short_date(value: date | datetime | str | None) -> str:
    return format_date_fr(value, diagnostic=True)


def price_display(value: float | int | Decimal | None) -> str:
    return format_price_fr(value, "EUR", diagnostic=True)


def airlines_display(airlines_json: str | None) -> str:
    airlines = parse_json_list(airlines_json)
    return ", ".join(airlines) if airlines else ""


def warnings_display(warnings_json: str | None) -> list[str]:
    return [WARNING_LABELS.get(warning, warning) for warning in parse_json_list(warnings_json)]


def booking_display(deal: Any) -> str:
    if getattr(deal, "booking_url", None):
        return ""
    warnings = parse_json_list(getattr(deal, "warnings_json", None))
    if "travelpayouts marker missing" in warnings:
        return WARNING_LABELS["travelpayouts marker missing"]
    return "Lien indisponible : source sans URL"


def mode_display(value: str | None) -> str:
    return "Bus" if value == "bus" else "Avion"


def duration_display(minutes: int | None) -> str:
    return format_duration(minutes)


def provider_status_display(status: Any | None) -> str:
    if not status:
        return "Non disponible"
    if not getattr(status, "enabled", False):
        return "Désactivé"
    if getattr(status, "ok", False):
        return "OK"
    error = getattr(status, "error", None)
    if error:
        return str(error)
    return "Erreur"
