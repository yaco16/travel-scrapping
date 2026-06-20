from __future__ import annotations

import asyncio
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from travel_scrapping.config import Settings
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider
from travel_scrapping.db import ProviderStatusRow, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.db import set_run_config_snapshot
from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.date_grid import generate_roundtrip_dates
from travel_scrapping.search.filters import validate_deal
from travel_scrapping.search.normalizer import scrub_text
from travel_scrapping.search.providers.base import FlightProvider
from travel_scrapping.search.providers.distribusion import DistribusionGroundTransportProvider
from travel_scrapping.search.providers.playwright_probe import PlaywrightProbeProvider
from travel_scrapping.search.providers.serpapi_google_flights import SerpApiGoogleFlightDealsProvider
from travel_scrapping.search.providers.travelpayouts import TravelpayoutsProvider
from travel_scrapping.search.scoring import sort_deals


TERMINAL_RUN_STATUSES = {"completed", "failed"}
ALL_TRANSPORT_MODES = {"flight", "bus", "train"}


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
    providers: list[FlightProvider] = [SerpApiGoogleFlightDealsProvider(settings)]
    providers.append(TravelpayoutsProvider(settings))
    providers.append(PlaywrightProbeProvider(settings))
    return providers


def parse_modes(modes: str | None) -> set[str]:
    if not modes:
        return {"flight"}
    if modes == "all":
        return set(ALL_TRANSPORT_MODES)
    parsed = {part.strip() for part in modes.split(",") if part.strip()}
    mode_set = parsed & ALL_TRANSPORT_MODES
    return mode_set or {"flight"}


def rejection_reasons(deal: DealCandidate, reasons: list[str]) -> list[str]:
    values = list(reasons)
    values.extend(f"missing {field}" for field in deal.missing_fields)
    if not values and not deal.actionable:
        values.append("not actionable")
    return values


def main_reason(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    reason, count = counter.most_common(1)[0]
    return f"{reason} ({count})"


def provider_status_row(run_id: int, status) -> ProviderStatusRow:
    return ProviderStatusRow(
        run_id=run_id,
        name=status.name,
        enabled=status.enabled,
        ok=status.ok,
        warnings_json=json.dumps(status.warnings),
        error=status.error,
        key_present=status.key_present,
        attempted=status.attempted,
        http_status=status.http_status,
        raw_count=status.raw_count,
        normalized_count=status.normalized_count,
        accepted_count=status.accepted_count,
        rejected_count=status.rejected_count,
        main_rejection_reason=status.main_rejection_reason,
        request_params_json=json.dumps(status.request_params),
        destination_examples_json=json.dumps(status.destination_examples),
    )


def enrich_status(row: ProviderStatusRow, provider, *, accepted: int, rejected: int, reasons: Counter[str]) -> None:
    row.attempted = bool(getattr(provider, "last_attempted", row.attempted))
    row.http_status = getattr(provider, "last_status_code", row.http_status)
    row.raw_count = int(getattr(provider, "last_raw_count", row.raw_count or 0) or 0)
    row.normalized_count = int(getattr(provider, "last_normalized_count", row.normalized_count or 0) or 0)
    row.accepted_count = accepted
    row.rejected_count = rejected
    row.main_rejection_reason = main_reason(reasons)
    row.request_params_json = json.dumps(getattr(provider, "last_public_params", {}) or {})
    row.destination_examples_json = json.dumps(getattr(provider, "last_destination_examples", []) or [])


def create_search_run(settings: Settings, *, status: str = "pending", modes: str = "flight") -> int:
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = SearchRun(status=status)
        set_run_config_snapshot(run, settings, modes=modes)
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
            today=depart_from or settings.search_start_date or date.today(),
            date_to=settings.effective_search_end_date,
            min_nights=settings.min_nights,
            max_nights=settings.max_nights,
        )
        mode_set = parse_modes(modes)
        if providers is None:
            providers = build_providers(settings, include_indicative=include_indicative) if "flight" in mode_set else []
        with session_scope(factory) as session:
            if run_id is None:
                run = SearchRun(status="running")
                set_run_config_snapshot(run, settings, modes=modes)
                session.add(run)
                session.flush()
            else:
                run = session.get(SearchRun, run_id)
                if run is None:
                    raise ValueError(f"SearchRun {run_id} not found")
                run.status = "running"
                if not run.config_json or run.config_json == "{}":
                    set_run_config_snapshot(run, settings, modes=modes)
            all_deals: list[DealCandidate] = []
            rejected = 0
            provider_records: list[dict[str, object]] = []
            for provider in providers:
                status = provider.status()
                row = provider_status_row(run.id, status)
                session.add(row)
                provider_records.append({"name": status.name, "enabled": status.enabled, "role": provider_role(status.name)})
                if not status.enabled:
                    continue
                provider_accepted = 0
                provider_rejected = 0
                provider_reasons: Counter[str] = Counter()
                try:
                    candidates = await provider.search(destinations, date_pairs, limit=settings.top_results_limit)
                except Exception as exc:  # provider isolation
                    rejected += 1
                    row.ok = False
                    row.error = scrub_text(str(exc))[:500]
                    row.attempted = bool(getattr(provider, "last_attempted", True))
                    row.http_status = getattr(provider, "last_status_code", None)
                    row.rejected_count = 1
                    row.main_rejection_reason = "provider error (1)"
                    continue
                for deal in candidates:
                    ok, reasons = validate_deal(deal, settings)
                    if ok and deal.actionable:
                        all_deals.append(deal)
                        provider_accepted += 1
                    else:
                        rejected += 1
                        provider_rejected += 1
                        provider_reasons.update(rejection_reasons(deal, reasons))
                if row.raw_count == 0:
                    row.raw_count = len(candidates)
                if row.normalized_count == 0:
                    row.normalized_count = len(candidates)
                enrich_status(row, provider, accepted=provider_accepted, rejected=provider_rejected, reasons=provider_reasons)
            if mode_set & {"bus", "train"}:
                distribusion_provider = DistribusionGroundTransportProvider(settings)
                status = distribusion_provider.status()
                row = provider_status_row(run.id, status)
                session.add(row)
                provider_records.append(
                    {"name": status.name, "enabled": status.enabled, "role": provider_role(status.name)}
                )
                if status.enabled:
                    candidates = await distribusion_provider.search(
                        destinations,
                        date_pairs,
                        limit=settings.top_results_limit,
                    )
                    row.raw_count = len(candidates)
                    row.normalized_count = len(candidates)
            if "bus" in mode_set:
                bus_provider = FlixBusRapidApiProvider(settings)
                status = bus_provider.status()
                row = provider_status_row(run.id, status)
                session.add(row)
                provider_records.append({"name": status.name, "enabled": status.enabled, "role": provider_role(status.name)})
                if status.enabled and date_pairs:
                    outbound, ret, _nights = date_pairs[0]
                    bus_accepted = 0
                    bus_rejected = 0
                    bus_raw = 0
                    bus_reasons: Counter[str] = Counter()
                    for destination in destinations[: max(1, min(len(destinations), settings.top_results_limit))]:
                        try:
                            offers = await bus_provider.search_roundtrip(
                                "Nice", destination.city, outbound.isoformat(), ret.isoformat()
                            )
                        except Exception as exc:
                            rejected += 1
                            bus_rejected += 1
                            bus_reasons.update(["provider error"])
                            row.ok = False
                            row.error = scrub_text(str(exc))[:500]
                            continue
                        bus_raw += len(offers)
                        for offer in offers:
                            deal = offer.to_deal_candidate()
                            ok, reasons = validate_deal(deal, settings)
                            if ok and deal.actionable:
                                all_deals.append(deal)
                                bus_accepted += 1
                            else:
                                rejected += 1
                                bus_rejected += 1
                                bus_reasons.update(rejection_reasons(deal, reasons))
                    if bus_provider.last_error:
                        row.ok = False
                        row.error = scrub_text(bus_provider.last_error)
                    row.attempted = bool(getattr(bus_provider, "last_path", None))
                    row.http_status = bus_provider.last_status_code
                    row.raw_count = bus_raw
                    row.normalized_count = bus_raw
                    row.accepted_count = bus_accepted
                    row.rejected_count = bus_rejected
                    row.main_rejection_reason = main_reason(bus_reasons)
            sorted_deals = sort_deals(all_deals)[: settings.top_results_limit]
            inserted = save_deals(session, run, sorted_deals)
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.accepted_count = inserted
            run.rejected_count = rejected + (len(sorted_deals) - inserted)
            run.cheapest_price_eur = sorted_deals[0].total_price_eur if sorted_deals else None
            run.providers_json = json.dumps(provider_records, ensure_ascii=True)
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
