from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import Deal, PriceObservation, SearchRun, init_db, session_scope
from travel_scrapping.email.brevo import send_deals_email
from travel_scrapping.search.engine import run_search_sync

templates = Jinja2Templates(directory="travel_scrapping/web/templates")
router = APIRouter()


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
        deals = list(run.deals) if run else []
        return templates.TemplateResponse(request, "results.html", {"run": run, "deals": deals})


@router.post("/email")
def email_route():
    settings = get_settings()
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
        return templates.TemplateResponse(request, "history.html", {"runs": runs})


@router.get("/deal/{deal_id}", response_class=HTMLResponse)
def deal_detail(request: Request, deal_id: int):
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        deal = session.get(Deal, deal_id)
        history = []
        if deal:
            route_key = f"{deal.origin_airport}-{deal.destination_airport}:{deal.outbound_date}:{deal.return_date}"
            history = list(session.scalars(select(PriceObservation).where(PriceObservation.route_key == route_key)))
        return templates.TemplateResponse(
            request,
            "detail.html",
            {"deal": deal, "history": history, "json": json},
        )
