from __future__ import annotations

import asyncio
import json
from datetime import date
from types import SimpleNamespace
from typing import cast

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import (
    OurAirport,
    Deal,
    PriceObservation,
    ProviderStatusRow,
    SearchRun,
    init_db,
    invalid_price_observation_clause,
    run_config_data,
    session_scope,
    valid_price_observation_clause,
)
from travel_scrapping.email.brevo import send_deals_email
from travel_scrapping.search.engine import create_search_run, run_search_sync
from travel_scrapping.airports import resolve_airport
from travel_scrapping.web import presentation

COUNTRY_LABELS = {
    "AT": "Autriche",
    "BE": "Belgique",
    "CH": "Suisse",
    "CZ": "Tchéquie",
    "DE": "Allemagne",
    "DK": "Danemark",
    "ES": "Espagne",
    "FR": "France",
    "GB": "Royaume-Uni",
    "GR": "Grèce",
    "HU": "Hongrie",
    "IE": "Irlande",
    "IT": "Italie",
    "MA": "Maroc",
    "MT": "Malte",
    "NL": "Pays-Bas",
    "NO": "Norvège",
    "PL": "Pologne",
    "PT": "Portugal",
    "SE": "Suède",
    "SK": "Slovaquie",
    "TR": "Turquie",
    "UK": "Royaume-Uni",
}


def country_display(value: str | None) -> str:
    if not value:
        return ""
    label = str(value).strip()
    return COUNTRY_LABELS.get(label.upper(), label)


def wants_results_partial(request: Request) -> bool:
    return request.headers.get("HX-Request", "").lower() == "true"


templates = Jinja2Templates(directory="travel_scrapping/web/templates")
templates.env.filters["destination_display"] = presentation.destination_display
templates.env.filters["short_date"] = presentation.short_date
templates.env.filters["price_display"] = presentation.price_display
templates.env.filters["airlines_display"] = presentation.airlines_display
templates.env.filters["warnings_display"] = presentation.warnings_display
templates.env.filters["booking_display"] = presentation.booking_display
templates.env.filters["mode_display"] = presentation.mode_display
templates.env.filters["duration_display"] = presentation.duration_display
templates.env.filters["provider_status_display"] = presentation.provider_status_display
templates.env.filters["date_time"] = presentation.date_time
templates.env.filters["yes_no"] = presentation.yes_no
templates.env.filters["country_display"] = country_display
router = APIRouter()
TERMINAL_RUN_STATUSES = {"completed", "failed"}


def valid_display_deal(deal: Deal) -> bool:
    if not deal.outbound_date or not deal.return_date:
        return False
    outbound_date = cast(date, deal.outbound_date)
    return_date = cast(date, deal.return_date)
    nights = (return_date - outbound_date).days
    if nights != deal.nights:
        return False
    if deal.total_price_eur is None:
        return False
    if not deal.actionable or not deal.booking_url or not deal.operator_name:
        return False
    return True


def diagnostics_context(settings, session, run: SearchRun | None = None) -> dict[str, object]:
    if run is None:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
    latest_statuses = latest_provider_statuses(session, run.id if run else None)
    flixbus_status = latest_statuses.get("flixbus") or latest_statuses.get("flixbus_rapidapi")
    raw_total = sum(int(status.raw_count or 0) for status in latest_statuses.values() if status.enabled)
    normalized_total = sum(int(status.normalized_count or 0) for status in latest_statuses.values() if status.enabled)
    enabled_statuses = [status for status in latest_statuses.values() if status.enabled]
    attempted_statuses = [status for status in enabled_statuses if status.attempted]
    accepted_total = int(run.accepted_count or 0) if run else 0
    rejected_total = int(run.rejected_count or 0) if run else 0
    reasons = [status.main_rejection_reason for status in latest_statuses.values() if status.main_rejection_reason]
    main_reason = reasons[0] if reasons else "raison non disponible"
    serpapi_status = latest_statuses.get("serpapi_google_flights_deals") or latest_statuses.get("serpapi")
    if not enabled_statuses or not attempted_statuses:
        no_offer_message = "Aucun fournisseur actif pour ce run. Vérifie les modes et les clés API."
        if serpapi_status and not serpapi_status.enabled:
            no_offer_message = "SerpApi désactivé : clé absente ou non lue."
    elif serpapi_status and serpapi_status.attempted and serpapi_status.http_status and serpapi_status.http_status != 200:
        no_offer_message = f"SerpApi appelé, statut HTTP {serpapi_status.http_status}."
    elif serpapi_status and serpapi_status.attempted and int(serpapi_status.raw_count or 0) == 0:
        no_offer_message = "SerpApi appelé, HTTP 200, payload sans deal exploitable."
    elif raw_total == 0:
        no_offer_message = "Aucune offre exploitable trouvée. 0 offre reçue des fournisseurs actifs."
    elif rejected_total:
        no_offer_message = f"Aucune offre exploitable trouvée. {rejected_total} offres rejetées : {main_reason}."
    else:
        no_offer_message = (
            "Aucune offre exploitable trouvée. "
            f"{raw_total} offres reçues, {normalized_total} offres normalisées, 0 offre affichable."
        )
    return {
        "serpapi_key_present": bool(settings.serpapi_api_key),
        "serpapi_last_status": "non disponible",
        "serpapi_last_json": "data/debug/",
        "travelpayouts_active": bool(settings.travelpayouts_token and settings.travelpayouts_marker),
        "travelpayouts_marker_present": bool(settings.travelpayouts_marker),
        "ourairports_active": settings.ourairports_enabled,
        "ourairports_count": session.query(OurAirport).count(),
        "api_ninjas_active": settings.api_ninjas_enabled,
        "flixbus_active": settings.bus_enabled and settings.flixbus_enabled,
        "rapidapi_key_present": bool(settings.rapidapi_key),
        "flixbus_last_status": presentation.provider_status_display(flixbus_status),
        "flixbus_last_json": "data/debug/",
        "raw_total": raw_total,
        "normalized_total": normalized_total,
        "accepted_total": accepted_total,
        "rejected_total": rejected_total,
        "main_rejection_reason": main_reason,
        "no_offer_message": no_offer_message,
        "google_flight_deals": google_flight_deals_context(latest_statuses),
    }


def google_flight_deals_context(statuses: dict[str, ProviderStatusRow]) -> dict[str, object]:
    status = statuses.get("serpapi_google_flights_deals") or statuses.get("serpapi")
    params = {}
    examples: list[str] = []
    if status:
        try:
            params = json.loads(status.request_params_json or "{}")
        except json.JSONDecodeError:
            params = {}
        try:
            examples = [str(item) for item in json.loads(status.destination_examples_json or "[]")]
        except json.JSONDecodeError:
            examples = []
    endpoint = str(params.get("engine") or (status.name if status else "non disponible"))
    payload_diagnostic = params.get("payload_diagnostic") if isinstance(params.get("payload_diagnostic"), dict) else {}
    return {
        "endpoint": endpoint,
        "raw_count": int(status.raw_count or 0) if status else 0,
        "normalized_count": int(status.normalized_count or 0) if status else 0,
        "accepted_count": int(status.accepted_count or 0) if status else 0,
        "rejected_count": int(status.rejected_count or 0) if status else 0,
        "main_rejection_reason": status.main_rejection_reason if status else None,
        "enabled": bool(status.enabled) if status else False,
        "key_present": bool(status.key_present) if status else False,
        "attempted": bool(status.attempted) if status else False,
        "http_status": status.http_status if status else None,
        "params": params,
        "payload_diagnostic": payload_diagnostic,
        "diagnostic": params.get("diagnostic"),
        "destination_examples": examples,
        "wrong_endpoint": endpoint != "google_flights_deals",
    }


def latest_provider_statuses(session, run_id: int | None) -> dict[str, ProviderStatusRow]:
    if run_id is None:
        return {}
    rows = list(
        session.scalars(
            select(ProviderStatusRow)
            .where(ProviderStatusRow.run_id == run_id)
            .order_by(ProviderStatusRow.id.asc())
        )
    )
    statuses: dict[str, ProviderStatusRow] = {}
    for row in rows:
        statuses[row.name] = row
    return statuses


def latest_display_deals(
    settings,
    session,
    run_id: int | None = None,
    mode: str | None = None,
) -> tuple[SearchRun | None, list[Deal], dict[str, ProviderStatusRow]]:
    if run_id is None:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
    else:
        run = session.get(SearchRun, run_id)
    statuses = latest_provider_statuses(session, run.id if run else None)
    deals = [deal for deal in list(run.deals) if valid_display_deal(deal)] if run else []
    if mode in {"flight", "bus", "train"}:
        deals = [deal for deal in deals if deal.transport_mode == mode]
    deals = sorted(
        deals,
        key=lambda deal: (
            float(deal.total_price_eur),
            cast(date, deal.outbound_date),
            deal.destination_city or deal.destination_airport,
        ),
    )
    for deal in deals:
        airport = resolve_airport(deal.destination_airport, settings, session)
        deal.destination_display_name = airport.info.display_name  # type: ignore[attr-defined]
        if not deal.destination_country and airport.info.country:
            deal.destination_country = airport.info.country
        deal.provider_status = statuses.get(deal.provider or deal.source) or statuses.get(deal.source)  # type: ignore[attr-defined]
    return run, deals, statuses


def run_config_context(run: SearchRun | None, settings, statuses: dict[str, ProviderStatusRow] | None = None):
    data = run_config_data(run)
    statuses = statuses or {}
    if not data and statuses:
        data = legacy_config_from_statuses(run, statuses)
    origin = str(data.get("origin_airport") or settings.origin_airport)
    budget = numeric_config_value(data.get("budget_eur"), settings.max_roundtrip_price_eur)
    start_raw = data.get("search_start_date") or settings.search_start_date
    end_raw = data.get("search_end_date") or settings.effective_search_end_date
    min_nights = int_config_value(data.get("min_nights"), settings.min_nights)
    max_nights = int_config_value(data.get("max_nights"), settings.max_nights)
    max_stops = int_config_value(data.get("max_stops"), settings.max_stops)
    ctx = {
        "origin_airport": origin,
        "budget_eur": budget,
        "search_start_date": str(start_raw) if start_raw else "",
        "search_end_date": str(end_raw) if end_raw else "",
        "min_nights": min_nights,
        "max_nights": max_nights,
        "max_stops": max_stops,
        "top_results_limit": int_config_value(data.get("top_results_limit"), settings.top_results_limit),
        "currency": str(data.get("currency") or settings.default_currency),
        "modes": str(data.get("modes") or "flight"),
    }
    summary_settings = SimpleNamespace(
        origin_airport=ctx["origin_airport"],
        max_roundtrip_price_eur=ctx["budget_eur"],
        search_start_date=ctx["search_start_date"],
        effective_search_end_date=ctx["search_end_date"],
        min_nights=ctx["min_nights"],
        max_nights=ctx["max_nights"],
        max_stops=ctx["max_stops"],
    )
    ctx["summary"] = presentation.configuration_summary(summary_settings)
    return ctx


def int_config_value(value: object, fallback: int) -> int:
    try:
        return int(str(value)) if value not in (None, "") else fallback
    except ValueError:
        return fallback


def numeric_config_value(value: object, fallback: float) -> float:
    try:
        return float(str(value)) if value not in (None, "") else fallback
    except ValueError:
        return fallback


def legacy_config_from_statuses(run: SearchRun | None, statuses: dict[str, ProviderStatusRow]) -> dict[str, object]:
    status = statuses.get("serpapi_google_flights_deals") or statuses.get("serpapi")
    params: dict[str, object] = {}
    if status:
        try:
            loaded = json.loads(status.request_params_json or "{}")
            params = loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            params = {}
    outbound = str(params.get("outbound_date") or "")
    start, end = (outbound.split(",", 1) + [""])[:2] if "," in outbound else ("", outbound)
    trip_length = str(params.get("trip_length") or "")
    min_nights, max_nights = (trip_length.split(",", 1) + [""])[:2] if "," in trip_length else ("", "")
    google_stops = int(str(params.get("stops") or "2"))
    return {
        "origin_airport": params.get("departure_id") or first_run_origin(run),
        "budget_eur": float(str(params.get("max_price") or 0) or 0),
        "search_start_date": start or None,
        "search_end_date": end or None,
        "min_nights": int(min_nights or 1),
        "max_nights": int(max_nights or 7),
        "max_stops": max(0, google_stops - 1),
        "top_results_limit": run.accepted_count if run and run.accepted_count else 50,
        "currency": params.get("currency") or "EUR",
        "modes": "flight",
    }


def first_run_origin(run: SearchRun | None) -> str:
    if run and run.deals:
        return str(run.deals[0].origin_airport)
    return "NCE"


def provider_groups(statuses: dict[str, ProviderStatusRow]) -> dict[str, list[dict[str, object]]]:
    groups: dict[str, list[dict[str, object]]] = {"active": [], "disabled": [], "advanced": []}
    for name, status in statuses.items():
        role = provider_role(name)
        blocked = provider_blocked(status)
        item = {"name": name, "status": status, "role": role, "blocked": blocked}
        if status.enabled and not blocked and role in {"primary", "optional"}:
            groups["active"].append(item)
        elif role == "detail_probe":
            groups["advanced"].append(item)
        else:
            groups["disabled"].append(item)
    return groups


def provider_rows(groups: dict[str, list[dict[str, object]]]) -> list[dict[str, object]]:
    return groups["active"] + groups["disabled"] + groups["advanced"]


def provider_role(name: str) -> str:
    roles = {
        "serpapi_google_flights_deals": "primary",
        "serpapi": "detail_probe",
        "serpapi_google_flights": "detail_probe",
        "travelpayouts": "optional",
        "flixbus": "optional",
        "flixbus_rapidapi": "optional",
        "distribusion": "optional",
        "playwright_probe": "detail_probe",
    }
    return roles.get(name, "optional")


def provider_blocked(status: ProviderStatusRow) -> bool:
    if not status.enabled:
        return True
    if status.name in {"flixbus", "flixbus_rapidapi"} and status.http_status in {403, 429}:
        return True
    if status.name == "travelpayouts" and not status.attempted and (status.accepted_count or 0) == 0:
        return True
    if status.name == "playwright_probe":
        return True
    return False


def deal_payload(deal: Deal) -> dict[str, object]:
    status = getattr(deal, "provider_status", None)
    outbound_date = cast(date, deal.outbound_date)
    return_date = cast(date, deal.return_date)
    return {
        "id": deal.id,
        "destination": presentation.destination_display(deal),
        "outbound_date": presentation.short_date(outbound_date),
        "return_date": presentation.short_date(return_date),
        "dates": f"{presentation.short_date(outbound_date)} - {presentation.short_date(return_date)}",
        "nights": deal.nights,
        "price": presentation.price_display(deal.total_price_eur),
        "provider": deal.provider or deal.source,
        "provider_status": presentation.provider_status_display(status),
        "transport_mode": presentation.mode_display(deal.transport_mode),
        "operator": deal.operator_name or presentation.airlines_display(deal.airlines_json),
        "booking_url": deal.booking_url,
    }


def provider_diagnostics_payload(provider_statuses: dict[str, ProviderStatusRow]) -> list[dict[str, object]]:
    return [
        {
            "provider": name,
            "enabled": status.enabled,
            "key_present": status.key_present,
            "attempted": status.attempted,
            "http_status": status.http_status,
            "error": status.error,
            "raw_count": status.raw_count or 0,
            "normalized_count": status.normalized_count or 0,
            "accepted_count": status.accepted_count or 0,
            "rejected_count": status.rejected_count or 0,
            "main_rejection_reason": status.main_rejection_reason,
            "warnings": json.loads(status.warnings_json or "[]"),
            "request_params": json.loads(status.request_params_json or "{}"),
            "destination_examples": json.loads(status.destination_examples_json or "[]"),
        }
        for name, status in provider_statuses.items()
    ]


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        statuses = latest_provider_statuses(session, run.id if run else None)
        default_config = run_config_context(None, settings)
        last_run_config = run_config_context(run, settings, statuses) if run else None
        return templates.TemplateResponse(
            request,
            "home.html",
            {
                "settings": safe_settings_dict(settings),
                "default_config": default_config,
                "configuration_summary": default_config["summary"],
                "warnings": settings.warnings(),
                "run": run,
                "run_config": last_run_config,
                "provider_groups": provider_groups(statuses),
            },
        )


@router.get("/search", response_class=HTMLResponse)
def search_form():
    return RedirectResponse("/", status_code=303)


def run_search_background(search_settings, *, run_id: int, modes: str, depart_from: date | None) -> None:
    run_search_sync(search_settings, modes=modes, depart_from=depart_from, run_id=run_id)


@router.post("/run")
async def run_search_route(request: Request, background_tasks: BackgroundTasks):
    settings = get_settings()
    form = await request.form()
    origin = str(form.get("origin_airport") or form.get("depart_from") or form.get("origin") or settings.origin_airport)
    depart_from_raw = str(form.get("depart_date_min") or "")
    depart_to_raw = str(form.get("depart_date_max") or form.get("search_end_date") or settings.search_end_date)
    min_nights = int(str(form.get("min_nights") or settings.min_nights))
    max_nights = int(str(form.get("max_nights") or settings.max_nights))
    max_price = float(str(form.get("max_price") or settings.max_roundtrip_price_eur))
    max_stops = int(str(form.get("max_stops") or settings.max_stops))
    max_air_time = float(str(form.get("max_air_time") or settings.max_air_time_hours))
    max_layover = float(str(form.get("max_layover") or settings.max_layover_hours))
    modes = ",".join(str(mode) for mode in form.getlist("modes")) or "flight"
    search_settings = settings.model_copy(
        update={
            "origin_airport": origin.upper(),
            "search_start_date": date.fromisoformat(depart_from_raw) if depart_from_raw else settings.search_start_date,
            "search_end_date": date.fromisoformat(depart_to_raw),
            "min_nights": min_nights,
            "max_nights": max_nights,
            "max_roundtrip_price_eur": max_price,
            "max_stops": max_stops,
            "max_air_time_hours": max_air_time,
            "max_layover_hours": max_layover,
        }
    )
    depart_from = date.fromisoformat(depart_from_raw) if depart_from_raw else None
    run_id = create_search_run(search_settings, status="pending", modes=modes)
    background_tasks.add_task(run_search_background, search_settings, run_id=run_id, modes=modes, depart_from=depart_from)
    return RedirectResponse(f"/results?run_id={run_id}", status_code=303)


@router.get("/results", response_class=HTMLResponse)
def results(request: Request):
    settings = get_settings()
    run_id_raw = request.query_params.get("run_id")
    run_id = int(run_id_raw) if run_id_raw and run_id_raw.isdigit() else None
    mode = request.query_params.get("mode")
    factory = init_db(settings)
    with session_scope(factory) as session:
        run, deals, provider_statuses = latest_display_deals(settings, session, run_id, mode)
        all_run_deals = [deal for deal in list(run.deals) if valid_display_deal(deal)] if run else []
        cheapest = min((deal.total_price_eur for deal in all_run_deals), default=None)
        groups = provider_groups(provider_statuses)
        template_name = "_results_offers.html" if wants_results_partial(request) else "results.html"
        return templates.TemplateResponse(
            request,
            template_name,
            {
                "run": run,
                "run_terminal": bool(run and run.status in TERMINAL_RUN_STATUSES),
                "deals": deals,
                "accepted_display_count": len(deals),
                "accepted_total_count": run.accepted_count if run else 0,
                "best_price": cheapest,
                "provider_statuses": provider_statuses,
                "provider_groups": groups,
                "provider_rows": provider_rows(groups),
                "active_provider_count": len(groups["active"]),
                "processing_steps": presentation.processing_steps(run, len(deals)),
                "email_enabled": settings.email_enabled,
                "diagnostics": diagnostics_context(settings, session, run),
                "run_config": run_config_context(run, settings, provider_statuses) if run else None,
                "mode": mode or "all",
            },
        )


@router.get("/deals")
def deals_api():
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        run, deals, provider_statuses = latest_display_deals(settings, session)
        diagnostics = diagnostics_context(settings, session, run)
        return JSONResponse(
            {
                "run_id": run.id if run else None,
                "processing_steps": presentation.processing_steps(run, len(deals)),
                "deals": [deal_payload(deal) for deal in deals],
                "provider_statuses": {
                    name: presentation.provider_status_display(status)
                    for name, status in provider_statuses.items()
                },
                "provider_diagnostics": provider_diagnostics_payload(provider_statuses),
                "no_offer_message": diagnostics["no_offer_message"],
            }
        )


@router.post("/email")
def email_route():
    settings = get_settings()
    if not settings.email_enabled:
        return RedirectResponse("/results", status_code=303)
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        deals = list(run.deals) if run else []
    asyncio.run(send_deals_email(settings, deals))
    return RedirectResponse("/results", status_code=303)


@router.get("/history", response_class=HTMLResponse)
def history(request: Request):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        runs = list(session.scalars(select(SearchRun).order_by(SearchRun.id.desc()).limit(50)))
        runs_count = session.query(SearchRun).count()
        observations_count = session.query(PriceObservation).count()
        return templates.TemplateResponse(
            request,
            "history.html",
            {"runs": runs, "runs_count": runs_count, "observations_count": observations_count},
        )


@router.get("/deal/{deal_id}", response_class=HTMLResponse)
def deal_detail(request: Request, deal_id: int):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        deal = session.get(Deal, deal_id)
        history = []
        if deal:
            deal.destination_display_name = resolve_airport(  # type: ignore[attr-defined]
                deal.destination_airport, settings, session
            ).info.display_name
            route_key = f"{deal.origin_airport}-{deal.destination_airport}:{deal.outbound_date}:{deal.return_date}"
            history = list(
                session.scalars(
                    select(PriceObservation)
                    .where(PriceObservation.route_key == route_key)
                    .where(valid_price_observation_clause())
                )
            )
        return templates.TemplateResponse(
            request,
            "detail.html",
            {"deal": deal, "history": history, "json": json},
        )


@router.get("/sqlite", response_class=HTMLResponse)
def sqlite_diagnostics(request: Request):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        runs_count = session.query(SearchRun).count()
        observations_count = session.query(PriceObservation).count()
        valid_clause = valid_price_observation_clause()
        invalid_clause = invalid_price_observation_clause()
        valid_count = session.scalar(select(func.count(PriceObservation.id)).where(valid_clause)) or 0
        invalid_count = session.scalar(select(func.count(PriceObservation.id)).where(invalid_clause)) or 0
        latest = list(
            session.scalars(select(PriceObservation).where(valid_clause).order_by(PriceObservation.id.desc()).limit(20))
        )
        for row in latest:
            row.destination_display_name = resolve_airport(  # type: ignore[attr-defined]
                row.destination_iata, settings, session
            ).info.display_name
        variations = session.execute(
            select(
                PriceObservation.origin_iata,
                PriceObservation.destination_iata,
                PriceObservation.departure_date,
                PriceObservation.return_date,
                PriceObservation.nights,
                PriceObservation.source,
            )
            .where(valid_clause)
            .group_by(
                PriceObservation.origin_iata,
                PriceObservation.destination_iata,
                PriceObservation.departure_date,
                PriceObservation.return_date,
                PriceObservation.nights,
                PriceObservation.source,
            )
            .having(func.count(PriceObservation.id) > 1)
            .limit(20)
        ).all()
        variation_rows = []
        for row in variations:
            variation_rows.append(
                {
                    "origin_iata": row.origin_iata,
                    "destination_display_name": resolve_airport(
                        row.destination_iata, settings, session
                    ).info.display_name,
                    "departure_date": row.departure_date,
                    "return_date": row.return_date,
                    "nights": row.nights,
                    "source": row.source,
                }
            )
        return templates.TemplateResponse(
            request,
            "sqlite.html",
            {
                "runs_count": runs_count,
                "observations_count": observations_count,
                "valid_count": valid_count,
                "invalid_count": invalid_count,
                "latest": latest,
                "variations": variation_rows,
            },
        )
