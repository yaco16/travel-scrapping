from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import cast

from fastapi import APIRouter, Request
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
    session_scope,
    valid_price_observation_clause,
)
from travel_scrapping.email.brevo import send_deals_email
from travel_scrapping.search.engine import run_search_sync
from travel_scrapping.airports import resolve_airport
from travel_scrapping.web import presentation

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
router = APIRouter()


def valid_display_deal(deal: Deal, settings) -> bool:
    if not deal.outbound_date or not deal.return_date:
        return False
    outbound_date = cast(date, deal.outbound_date)
    return_date = cast(date, deal.return_date)
    nights = (return_date - outbound_date).days
    if nights != deal.nights:
        deal.nights = nights
    if not settings.min_nights <= nights <= settings.max_nights:
        return False
    if return_date > settings.effective_search_end_date:
        return False
    if deal.total_price_eur is None or deal.total_price_eur >= settings.max_roundtrip_price_eur:
        return False
    if not deal.actionable or not deal.booking_url or not deal.operator_name:
        return False
    return True


def diagnostics_context(settings, session, run: SearchRun | None = None) -> dict[str, object]:
    if run is None:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
    latest_statuses = latest_provider_statuses(session, run.id if run else None)
    flixbus_status = latest_statuses.get("flixbus_rapidapi")
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


def latest_display_deals(settings, session) -> tuple[SearchRun | None, list[Deal], dict[str, ProviderStatusRow]]:
    run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
    statuses = latest_provider_statuses(session, run.id if run else None)
    deals = [deal for deal in list(run.deals) if valid_display_deal(deal, settings)] if run else []
    deals = sorted(deals, key=lambda deal: deal.total_price_eur)[: settings.top_results_limit]
    for deal in deals:
        deal.destination_display_name = resolve_airport(  # type: ignore[attr-defined]
            deal.destination_airport, settings, session
        ).info.display_name
        deal.provider_status = statuses.get(deal.provider or deal.source) or statuses.get(deal.source)  # type: ignore[attr-defined]
    return run, deals, statuses


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


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        return templates.TemplateResponse(
            request,
            "home.html",
            {"settings": safe_settings_dict(settings), "warnings": settings.warnings(), "run": run},
        )


@router.get("/search", response_class=HTMLResponse)
def search_form(request: Request):
    settings = get_settings()
    return templates.TemplateResponse(request, "search.html", {"settings": safe_settings_dict(settings)})


@router.post("/run")
def run_search_route():
    settings = get_settings()
    run_search_sync(settings)
    return RedirectResponse("/results", status_code=303)


@router.get("/results", response_class=HTMLResponse)
def results(request: Request):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        run, deals, provider_statuses = latest_display_deals(settings, session)
        return templates.TemplateResponse(
            request,
            "results.html",
            {
                "run": run,
                "deals": deals,
                "provider_statuses": provider_statuses,
                "email_enabled": settings.email_enabled,
                "diagnostics": diagnostics_context(settings, session, run),
            },
        )


@router.get("/deals")
def deals_api():
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        run, deals, provider_statuses = latest_display_deals(settings, session)
        return JSONResponse(
            {
                "run_id": run.id if run else None,
                "deals": [deal_payload(deal) for deal in deals],
                "provider_statuses": {
                    name: presentation.provider_status_display(status)
                    for name, status in provider_statuses.items()
                },
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
