from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from travel_scrapping.airports import destination_display_name
from travel_scrapping.formatters import format_date_fr, format_datetime_fr, format_duration, format_price_fr

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


def date_time(value: date | datetime | str | None) -> str:
    return format_datetime_fr(value, diagnostic=True)


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


def budget_display(value: float | int | Decimal | None) -> str:
    return format_price_fr(value, "EUR", diagnostic=True).replace(" €", " EUR")


def configuration_summary(settings: Any) -> str:
    return (
        f"Origine {settings.origin_airport} · "
        f"Budget < {budget_display(settings.max_roundtrip_price_eur)} · "
        f"{settings.min_nights}-{settings.max_nights} nuits · "
        f"jusqu'au {format_date_fr(settings.effective_search_end_date, diagnostic=True)}"
    )


def processing_steps(run: Any | None, deals_count: int) -> list[str]:
    steps = ["Étape 01 — Configuration chargée"]
    if run is None:
        return steps
    steps.append("Étape 02 — Recherche lancée")
    if getattr(run, "status", None) in {"running", "pending"}:
        return steps
    steps.append("Étape 03 — Résultats récupérés")
    steps.append("Étape 04 — Résultats filtrés")
    label = "Résultats affichés" if deals_count else "Aucun résultat affichable"
    steps.append(f"Étape 05 — {label}")
    return steps


def yes_no(value: Any) -> str:
    return "oui" if value else "non"
