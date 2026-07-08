from __future__ import annotations

import json
import zlib
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from travel_scrapping.airports import destination_display_name
from travel_scrapping.formatters import (
    format_clock_fr,
    format_date_fr,
    format_datetime_fr,
    format_duration,
    format_price_fr,
)

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


def clock_display(value: datetime | None) -> str:
    return format_clock_fr(value)


def price_display(value: float | int | Decimal | None) -> str:
    return format_price_fr(value, "EUR", diagnostic=True)


def airlines_display(airlines_json: str | None) -> str:
    airlines = parse_json_list(airlines_json)
    return ", ".join(airlines) if airlines else ""


def operator_display(deal: Any) -> str:
    operator_name = getattr(deal, "operator_name", None)
    if operator_name:
        return str(operator_name)
    airlines = airlines_display(getattr(deal, "airlines_json", None))
    if airlines:
        return airlines
    provider = getattr(deal, "provider", None)
    if provider:
        return str(provider)
    source = getattr(deal, "source", None)
    return str(source) if source else "Opérateur non communiqué"


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
    labels = {"flight": "Avion", "bus": "Bus", "train": "Train"}
    return labels.get(str(value or ""), "Avion")


def duration_display(minutes: int | None) -> str:
    return format_duration(minutes)


def bus_route_details(deal: Any) -> dict[str, Any]:
    if getattr(deal, "transport_mode", None) != "bus":
        return {}
    payload = _raw_payload(getattr(deal, "raw_payload_z", None))
    segments = _bus_segments(payload)
    if not segments:
        segments = [
            {
                "departure_station": _station_name(payload, "departure"),
                "arrival_station": _station_name(payload, "arrival") or destination_display(deal),
                "departure_at": getattr(deal, "outbound_departure_at", None),
                "arrival_at": getattr(deal, "outbound_arrival_at", None),
                "duration_minutes": getattr(deal, "duration_minutes", None),
            }
        ]
    stopovers = _stopovers(segments)
    return {
        "origin_station": segments[0].get("departure_station") or "Départ",
        "destination_station": segments[-1].get("arrival_station"),
        "segments": segments,
        "stopovers": stopovers,
        "unavailable_stopovers": _unavailable_stopovers(deal, payload, stopovers),
    }


def _raw_payload(value: bytes | memoryview | None) -> Any:
    if not value:
        return {}
    data = value.tobytes() if isinstance(value, memoryview) else value
    try:
        return json.loads(zlib.decompress(data).decode())
    except (TypeError, ValueError, zlib.error, json.JSONDecodeError):
        return {}


def _bus_segments(payload: Any) -> list[dict[str, Any]]:
    for row in _walk(payload):
        raw_segments = row.get("segments") or row.get("legs") or row.get("sections") or row.get("rides")
        if not isinstance(raw_segments, list):
            continue
        segments = [_segment(item) for item in raw_segments if isinstance(item, dict)]
        segments = [segment for segment in segments if segment.get("departure_station") or segment.get("arrival_station")]
        if segments:
            return segments
    return []


def _segment(row: dict[str, Any]) -> dict[str, Any]:
    departure_at = _parse_datetime(
        _value(row, "departure_at", "departure_time", "departureDateTime", "depDatetime", "start_time", "departure")
    )
    arrival_at = _parse_datetime(
        _value(row, "arrival_at", "arrival_time", "arrivalDateTime", "arrDatetime", "end_time", "arrival")
    )
    duration = _minutes(_value(row, "duration_minutes", "duration", "travel_time"))
    if duration is None and departure_at and arrival_at:
        duration = int((arrival_at - departure_at).total_seconds() // 60)
    return {
        "departure_station": _station_name(row, "departure"),
        "arrival_station": _station_name(row, "arrival"),
        "departure_at": departure_at,
        "arrival_at": arrival_at,
        "duration_minutes": duration,
    }


def _stopovers(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, (previous, current) in enumerate(zip(segments, segments[1:]), start=1):
        arrival_at = previous.get("arrival_at")
        departure_at = current.get("departure_at")
        duration = None
        if arrival_at and departure_at:
            duration = int((departure_at - arrival_at).total_seconds() // 60)
        rows.append(
            {
                "index": index,
                "station": previous.get("arrival_station") or current.get("departure_station"),
                "arrival_at": arrival_at,
                "departure_at": departure_at,
                "duration_minutes": duration,
                "inbound_duration_minutes": previous.get("duration_minutes"),
                "outbound_duration_minutes": current.get("duration_minutes"),
            }
        )
    return rows


def _unavailable_stopovers(deal: Any, payload: Any, stopovers: list[dict[str, Any]]) -> int:
    if stopovers:
        return 0
    if isinstance(payload, dict) and payload.get("stopover_details_available") is False:
        try:
            return max(0, int(getattr(deal, "stops_count", 0) or 0))
        except (TypeError, ValueError):
            return 0
    return 0


def _station_name(row: Any, prefix: str) -> str | None:
    if not isinstance(row, dict):
        return None
    direct_keys = (
        f"{prefix}_station_name",
        f"{prefix}_stop_name",
        f"{prefix}_city_name",
        f"{prefix}StationName",
        f"{prefix}StopName",
    )
    for key in direct_keys:
        value = row.get(key)
        if value:
            return str(value)
    nested = row.get(prefix) or row.get(f"{prefix}_station") or row.get(f"{prefix}_stop")
    if isinstance(nested, dict):
        for key in ("name", "station_name", "stop_name", "city_name"):
            value = nested.get(key)
            if value:
                return str(value)
    return None


def _value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("date") or value.get("value") or value.get("time")
        if value not in (None, ""):
            return value
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


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
    if value is None:
        return "Non disponible"
    return f"{int(round(float(value))):,} EUR".replace(",", " ")


def configuration_summary(settings: Any) -> str:
    start = f"du {format_date_fr(settings.search_start_date, diagnostic=True)} " if settings.search_start_date else ""
    return (
        f"Origine {settings.origin_airport} · "
        f"Budget max {budget_display(settings.max_roundtrip_price_eur)} · "
        f"{settings.min_nights}-{settings.max_nights} nuits · "
        f"départ {start}au {format_date_fr(settings.effective_search_end_date, diagnostic=True)} · "
        f"{settings.max_stops} correspondance max"
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
