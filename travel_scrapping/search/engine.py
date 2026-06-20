from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from travel_scrapping.config import Settings
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider
from travel_scrapping.db import ProviderStatusRow, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.date_grid import generate_roundtrip_dates
from travel_scrapping.search.filters import validate_deal
from travel_scrapping.search.normalizer import scrub_text
from travel_scrapping.search.providers.base import FlightProvider
from travel_scrapping.search.providers.playwright_probe import PlaywrightProbeProvider
from travel_scrapping.search.providers.serpapi_google_flights import SerpApiGoogleFlightsProvider
from travel_scrapping.search.providers.travelpayouts import TravelpayoutsProvider
from travel_scrapping.search.scoring import sort_deals


TERMINAL_RUN_STATUSES = {"completed", "failed"}


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


def build_providers(settings: Settings, *, include_indicative: bool = False) -> list[FlightProvider]:
    providers: list[FlightProvider] = [SerpApiGoogleFlightsProvider(settings)]
    if settings.travelpayouts_marker or include_indicative or settings.include_indicative:
        providers.append(TravelpayoutsProvider(settings))
    providers.append(PlaywrightProbeProvider(settings))
    return providers


def create_search_run(settings: Settings, *, status: str = "pending") -> int:
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = SearchRun(status=status)
        session.add(run)
        session.flush()
        return run.id


async def run_search(
    settings: Settings,
    *,
    providers: list[FlightProvider] | None = None,
    modes: str = "flight",
    include_indicative: bool = False,
    depart_from: date | None = None,
    run_id: int | None = None,
) -> int:
    factory = init_db(settings)
    try:
        destinations = load_destinations()
        date_pairs = generate_roundtrip_dates(
            today=depart_from or date.today(),
            date_to=settings.effective_search_end_date,
            min_nights=settings.min_nights,
            max_nights=settings.max_nights,
        )
        mode_set = {"flight", "bus"} if modes == "all" else {part.strip() for part in modes.split(",")}
        providers = providers or (
            build_providers(settings, include_indicative=include_indicative) if "flight" in mode_set else []
        )
        with session_scope(factory) as session:
            if run_id is None:
                run = SearchRun(status="running")
                session.add(run)
                session.flush()
            else:
                run = session.get(SearchRun, run_id)
                if run is None:
                    raise ValueError(f"SearchRun {run_id} not found")
                run.status = "running"
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
                        warnings_json=json.dumps(status.warnings),
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
                            error=scrub_text(str(exc))[:500],
                        )
                    )
                    continue
                for deal in candidates:
                    ok, _reasons = validate_deal(deal, settings)
                    if ok and deal.actionable:
                        all_deals.append(deal)
                    else:
                        rejected += 1
            if "bus" in mode_set:
                bus_provider = FlixBusRapidApiProvider(settings)
                status = bus_provider.status()
                session.add(
                    ProviderStatusRow(
                        run_id=run.id,
                        name=status.name,
                        enabled=status.enabled,
                        ok=status.ok,
                        warnings_json=json.dumps(status.warnings),
                        error=status.error,
                    )
                )
                if status.enabled and date_pairs:
                    outbound, ret, _nights = date_pairs[0]
                    for destination in destinations[: max(1, min(len(destinations), settings.top_results_limit))]:
                        try:
                            offers = await bus_provider.search_roundtrip(
                                "Nice", destination.city, outbound.isoformat(), ret.isoformat()
                            )
                        except Exception as exc:
                            rejected += 1
                            session.add(
                                ProviderStatusRow(
                                    run_id=run.id,
                                    name=bus_provider.name,
                                    enabled=True,
                                    ok=False,
                                    warnings_json="[]",
                                    error=scrub_text(str(exc))[:500],
                                )
                            )
                            continue
                        for offer in offers:
                            deal = offer.to_deal_candidate()
                            ok, _reasons = validate_deal(deal, settings)
                            if ok and deal.actionable:
                                all_deals.append(deal)
                            else:
                                rejected += 1
                    if bus_provider.last_error:
                        session.add(
                            ProviderStatusRow(
                                run_id=run.id,
                                name=bus_provider.name,
                                enabled=True,
                                ok=False,
                                warnings_json="[]",
                                error=scrub_text(bus_provider.last_error),
                            )
                        )
            sorted_deals = sort_deals(all_deals)[: settings.top_results_limit]
            inserted = save_deals(session, run, sorted_deals)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.accepted_count = inserted
            run.rejected_count = rejected + (len(sorted_deals) - inserted)
            run.cheapest_price_eur = sorted_deals[0].total_price_eur if sorted_deals else None
            return run.id
    except Exception as exc:
        if run_id is None:
            raise
        with session_scope(factory) as session:
            run = session.get(SearchRun, run_id)
            if run is not None:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                run.warnings_json = json.dumps([scrub_text(str(exc))[:500]])
        return run_id


def latest_deals(settings: Settings, limit: int | None = None):
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.scalars(select(SearchRun).order_by(SearchRun.id.desc())).first()
        if not run:
            return None, []
        deals = list(run.deals)[: limit or settings.top_results_limit]
        return run, deals


def run_search_sync(
    settings: Settings,
    *,
    modes: str = "flight",
    depart_from: date | None = None,
    run_id: int | None = None,
) -> int:
    return asyncio.run(run_search(settings, modes=modes, depart_from=depart_from, run_id=run_id))
