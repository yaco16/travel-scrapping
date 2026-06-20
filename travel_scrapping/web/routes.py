from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import cast

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import (
    Deal,
    PriceObservation,
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
    return True


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
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        deals = [deal for deal in list(run.deals) if valid_display_deal(deal, settings)] if run else []
        for deal in deals:
            deal.destination_display_name = resolve_airport(  # type: ignore[attr-defined]
                deal.destination_airport, settings, session
            ).info.display_name
        return templates.TemplateResponse(
            request,
            "results.html",
            {"run": run, "deals": deals, "email_enabled": settings.email_enabled},
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
