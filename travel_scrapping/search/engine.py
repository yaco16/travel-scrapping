from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from travel_scrapping.config import Settings
from travel_scrapping.db import ProviderStatusRow, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.date_grid import generate_roundtrip_dates
from travel_scrapping.search.filters import validate_deal
from travel_scrapping.search.providers.base import FlightProvider
from travel_scrapping.search.providers.playwright_probe import PlaywrightProbeProvider
from travel_scrapping.search.providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from travel_scrapping.search.providers.travelpayouts import TravelpayoutsProvider
from travel_scrapping.search.scoring import sort_deals


def load_destinations(path: str = "config/destinations.yaml") -> list[Destination]:
    data = yaml.safe_load(Path(path).read_text()) if Path(path).exists() else []
    seen: set[str] = set()
    destinations: list[Destination] = []
    for row in data or []:
        airport = str(row["airport"]).upper()
        if airport not in seen:
            seen.add(airport)
            destinations.append(Destination(airport, row.get("city", airport), row.get("country", "")))
    return destinations


def build_providers(settings: Settings) -> list[FlightProvider]:
    return [
        SerpApiGoogleFlightsProvider(settings),
        TravelpayoutsProvider(settings),
        PlaywrightProbeProvider(settings),
    ]


async def run_search(settings: Settings, *, providers: list[FlightProvider] | None = None) -> int:
    factory = init_db(settings)
    destinations = load_destinations()
    date_pairs = generate_roundtrip_dates(
        today=date.today(),
        date_to=settings.effective_search_end_date,
        min_nights=settings.min_nights,
        max_nights=settings.max_nights,
    )
    providers = providers or build_providers(settings)
    with session_scope(factory) as session:
        run = SearchRun(status="running")
        session.add(run)
        session.flush()
        all_deals: list[DealCandidate] = []
        rejected = 0
        for provider in providers:
            status = provider.status()
            session.add(
                ProviderStatusRow(
                    run_id=run.id,
                    name=status.name,
                    enabled=status.enabled,
                    ok=status.ok,
                    warnings_json="[]",
                    error=status.error,
                )
            )
            if not status.enabled:
                continue
            try:
                candidates = await provider.search(destinations, date_pairs, limit=settings.top_results_limit)
            except Exception as exc:  # provider isolation
                rejected += 1
                session.add(
                    ProviderStatusRow(
                        run_id=run.id,
                        name=provider.name,
                        enabled=True,
                        ok=False,
                        warnings_json="[]",
                        error=str(exc)[:500],
                    )
                )
                continue
            for deal in candidates:
                ok, _reasons = validate_deal(deal, settings)
                if ok:
                    all_deals.append(deal)
                else:
                    rejected += 1
        sorted_deals = sort_deals(all_deals)[: settings.top_results_limit]
        inserted = save_deals(session, run, sorted_deals)
        run.status = "completed"
        run.completed_at = datetime.now(timezone.utc)
        run.accepted_count = inserted
        run.rejected_count = rejected + (len(sorted_deals) - inserted)
        run.cheapest_price_eur = sorted_deals[0].total_price_eur if sorted_deals else None
        return run.id


def latest_deals(settings: Settings, limit: int | None = None):
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        if not run:
            return None, []
        deals = list(run.deals)[: limit or settings.top_results_limit]
        return run, deals


def run_search_sync(settings: Settings) -> int:
    return asyncio.run(run_search(settings))
