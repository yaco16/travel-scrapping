from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Mapping, cast

import typer
from sqlalchemy import func, select

from travel_scrapping.airports import (
    collect_observation_iata_codes,
    count_cached_airports,
    count_ourairports,
    resolve_airport,
)
from travel_scrapping.airports.ourairports import import_ourairports
from travel_scrapping.bus.flixbus_autocomplete import (
    autocomplete_city,
    find_cached_mapping,
    save_city_mapping,
)
from travel_scrapping.bus.flixbus_gtfs import gtfs_info, refresh_gtfs, search_stops
from travel_scrapping.bus.flixbus_openapi import FlixBusOpenApiProvider
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider
from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import (
    AirportMetadata,
    PriceObservation,
    ProviderStatusRow,
    SearchRun,
    init_db,
    invalid_price_observation_clause,
    session_scope,
    valid_price_observation_clause,
)
from travel_scrapping.email.brevo import send_deals_email
from travel_scrapping.search.engine import latest_deals, run_search
from travel_scrapping.search.filters import validate_deal
from travel_scrapping.search.normalizer import scrub_text
from travel_scrapping.search.providers.serpapi_google_flights import (
    SerpApiGoogleFlightDealsProvider,
    serpapi_smoke,
)
from travel_scrapping.web.presentation import configuration_summary, processing_steps, short_date
from travel_scrapping.formatters import format_price_fr

app = typer.Typer()


@app.command()
def config() -> None:
    typer.echo(json.dumps(safe_settings_dict(get_settings()), indent=2))


@app.command()
def search(
    send_email: bool = False,
    origin: str | None = None,
    depart_from: str | None = None,
    depart_to: str | None = None,
    min_nights: int | None = None,
    max_nights: int | None = None,
    max_price: float | None = None,
    max_stops: int | None = None,
    modes: str = "flight",
    include_indicative: bool = False,
) -> None:
    settings = get_settings()
    overrides = {}
    if origin:
        overrides["origin_airport"] = origin
    parsed_depart_from = date.fromisoformat(depart_from) if depart_from else None
    if parsed_depart_from is not None:
        overrides["search_start_date"] = parsed_depart_from
    if depart_to:
        overrides["search_end_date"] = date.fromisoformat(depart_to)
    if min_nights is not None:
        overrides["min_nights"] = min_nights
    if max_nights is not None:
        overrides["max_nights"] = max_nights
    if max_price is not None:
        overrides["max_roundtrip_price_eur"] = max_price
    if max_stops is not None:
        overrides["max_stops"] = max_stops
    if include_indicative:
        overrides["include_indicative"] = True
    if overrides:
        settings = settings.model_copy(update=overrides)
    typer.echo("Étape 01 — Configuration chargée")
    typer.echo(configuration_summary(settings))
    typer.echo("Étape 02 — Recherche lancée")
    run_id = asyncio.run(
        run_search(settings, modes=modes, include_indicative=include_indicative, depart_from=parsed_depart_from)
    )
    typer.echo("Étape 03 — Résultats récupérés")
    typer.echo("Étape 04 — Résultats filtrés")
    typer.echo("Étape 05 — Résultats affichés")
    typer.echo(f"run_id={run_id}")
    if send_email:
        _run, deals = latest_deals(settings)
        result = asyncio.run(send_deals_email(settings, deals))
        typer.echo(json.dumps(result))


@app.command()
def top(limit: int = 50) -> None:
    run, deals = latest_deals(get_settings(), limit)
    typer.echo(f"run_id={run.id if run else 'none'}")
    for step in processing_steps(run, len(deals)):
        typer.echo(step)
    for deal in deals:
        typer.echo(
            f"{deal.destination_airport} "
            f"{short_date(cast(date | None, deal.outbound_date))}-{short_date(cast(date | None, deal.return_date))} "
            f"{format_price_fr(deal.total_price_eur, 'EUR').replace(' €', ' EUR')}"
        )


@app.command()
def smoke() -> None:
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory):
        pass
    typer.echo("db=ok providers=manual-live-only")


@app.command()
def sqlite_diagnostics() -> None:
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        valid_clause = valid_price_observation_clause()
        invalid_clause = invalid_price_observation_clause()
        valid_count = session.scalar(select(func.count(PriceObservation.id)).where(valid_clause)) or 0
        invalid_count = session.scalar(select(func.count(PriceObservation.id)).where(invalid_clause)) or 0
        typer.echo(f"campaigns={session.query(SearchRun).count()}")
        typer.echo(f"observations={session.query(PriceObservation).count()}")
        typer.echo(f"observations_valides={valid_count}")
        typer.echo(f"observations_invalides={invalid_count}")
        if invalid_count:
            typer.echo(f"{invalid_count} observations invalides historiques détectées")
        typer.echo("latest_valid_observations:")
        latest = session.scalars(
            select(PriceObservation).where(valid_clause).order_by(PriceObservation.id.desc()).limit(20)
        )
        for row in latest:
            typer.echo(
                f"{row.id} run={row.run_id} {row.origin_iata}-{row.destination_iata} "
                f"{row.departure_date}->{row.return_date} nights={row.nights} "
                f"price={row.price} {row.currency} source={row.source} airline={row.airline or 'Non communiqué'}"
            )
        typer.echo("price_variations:")
        variations = session.execute(
            select(
                PriceObservation.origin_iata,
                PriceObservation.destination_iata,
                PriceObservation.departure_date,
                PriceObservation.return_date,
                PriceObservation.nights,
                PriceObservation.source,
                func.count(PriceObservation.id).label("count"),
                func.min(PriceObservation.price).label("min_price"),
                func.max(PriceObservation.price).label("max_price"),
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
        )
        for row in variations:
            typer.echo(
                f"{row.origin_iata}-{row.destination_iata} {row.departure_date}->{row.return_date} "
                f"nights={row.nights} source={row.source} count={row.count} "
                f"min={row.min_price} max={row.max_price}"
            )
        typer.echo("latest_provider_statuses:")
        statuses = session.scalars(select(ProviderStatusRow).order_by(ProviderStatusRow.id.desc()).limit(10))
        for row in statuses:
            warnings = ", ".join(json.loads(row.warnings_json or "[]"))
            typer.echo(
                f"{row.id} run={row.run_id} provider={row.name} enabled={row.enabled} ok={row.ok} "
                f"error={scrub_text(row.error or '')} warnings={warnings}"
            )


@app.command("sqlite-clean-invalid")
def sqlite_clean_invalid(dry_run: bool = False, execute: bool = False) -> None:
    if dry_run == execute:
        raise typer.BadParameter("Choisir exactement --dry-run ou --execute.")
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        invalid_clause = invalid_price_observation_clause()
        count = session.scalar(select(func.count(PriceObservation.id)).where(invalid_clause)) or 0
        if dry_run:
            typer.echo(f"{count} observations invalides seraient supprimées")
            typer.echo("campaigns conservées")
            return
        deleted = session.query(PriceObservation).filter(invalid_clause).delete(synchronize_session=False)
        typer.echo(f"{deleted} observations invalides supprimées")
        typer.echo("campaigns conservées")


@app.command("airports-refresh")
def airports_refresh(iata: str | None = None, force: bool = False) -> None:
    settings = get_settings()
    factory = init_db(settings)
    counts = {"cache": 0, "ourairports": 0, "api": 0, "fallback": 0, "unknown": 0}
    with session_scope(factory) as session:
        codes = [iata.upper()] if iata else collect_observation_iata_codes(session, settings.origin_airport)
        for code in codes:
            result = resolve_airport(code, settings, session, force=force)
            if result.cache_hit:
                counts["cache"] += 1
            elif result.info.source == "ourairports":
                counts["ourairports"] += 1
            elif result.info.source == "api_ninjas":
                counts["api"] += 1
            elif result.info.source == "fallback":
                counts["fallback"] += 1
            else:
                counts["unknown"] += 1
            typer.echo(f"{result.info.iata}: {result.info.display_name} ({result.info.source})")
    typer.echo(f"total codes={len(codes)}")
    typer.echo(f"trouvés via cache={counts['cache']}")
    typer.echo(f"trouvés via OurAirports={counts['ourairports']}")
    typer.echo(f"trouvés via API={counts['api']}")
    typer.echo(f"fallback={counts['fallback']}")
    typer.echo(f"inconnus={counts['unknown']}")


@app.command("airports-import-ourairports")
def airports_import_ourairports(force_refresh: bool = False) -> None:
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        result = import_ourairports(session, force_refresh=force_refresh)
        typer.echo(f"csv={result.csv_path}")
        typer.echo(f"importés={result.imported}")


@app.command("airports-diagnostics")
def airports_diagnostics() -> None:
    settings = get_settings()
    factory = init_db(settings)
    with session_scope(factory) as session:
        rows = session.execute(select(AirportMetadata.source, func.count(AirportMetadata.iata)).group_by(AirportMetadata.source))
        typer.echo(f"aéroports en cache={count_cached_airports(session)}")
        typer.echo(f"aéroports importés OurAirports={count_ourairports(session)}")
        typer.echo(f"API Ninjas activé={'oui' if settings.api_ninjas_enabled and bool(settings.api_ninjas_api_key) else 'non'}")
        typer.echo("résolutions par source:")
        for source, count in rows:
            typer.echo(f"- {source}: {count}")


@app.command("serpapi-smoke")
def serpapi_smoke_cmd(
    origin: str = typer.Option(..., "--origin"),
    destination: str = typer.Option(..., "--destination"),
    depart: str = typer.Option(..., "--depart"),
    return_: str = typer.Option(..., "--return"),
    debug: bool = False,
) -> None:
    settings = get_settings()
    if not settings.serpapi_api_key:
        typer.echo("SERPAPI_API_KEY manquant")
        return
    result = asyncio.run(
        serpapi_smoke(
            api_key=settings.serpapi_api_key,
            origin=origin,
            destination=destination,
            depart=date.fromisoformat(depart),
            ret=date.fromisoformat(return_),
        )
    )
    typer.echo(f"params={json.dumps(result.params, ensure_ascii=False)}")
    typer.echo(f"statut_http={result.status_code}")
    typer.echo(f"search_metadata.status={result.metadata_status}")
    typer.echo(f"error={result.error or ''}")
    typer.echo(f"best_flights={result.best_flights}")
    typer.echo(f"other_flights={result.other_flights}")
    typer.echo(f"departure_token={result.departure_tokens}")
    typer.echo(f"booking_token={result.booking_tokens}")
    typer.echo(f"booking_options={result.booking_options}")
    typer.echo(f"json_debug={result.debug_path}")


@app.command("google-flight-deals-smoke")
def google_flight_deals_smoke_cmd(
    origin: str = typer.Option("NCE", "--origin"),
    depart_from: str = typer.Option("2026-07-01", "--depart-from"),
    depart_to: str = typer.Option("2026-08-31", "--depart-to"),
    min_nights: int = typer.Option(1, "--min-nights"),
    max_nights: int = typer.Option(7, "--max-nights"),
    max_price: float = typer.Option(150, "--max-price"),
    max_stops: int = typer.Option(1, "--max-stops"),
) -> None:
    settings = get_settings().model_copy(
        update={
            "origin_airport": origin,
            "search_start_date": date.fromisoformat(depart_from),
            "search_end_date": date.fromisoformat(depart_to),
            "min_nights": min_nights,
            "max_nights": max_nights,
            "max_roundtrip_price_eur": max_price,
            "max_stops": max_stops,
        }
    )
    if not settings.serpapi_api_key:
        typer.echo("SERPAPI_API_KEY manquant")
        return
    provider = SerpApiGoogleFlightDealsProvider(settings)
    deals = asyncio.run(provider.search([], [], limit=settings.top_results_limit))
    accepted = []
    rejected: list[tuple[str, list[str]]] = []
    for deal in deals:
        ok, reasons = validate_deal(deal, settings, today=settings.search_start_date)
        if ok and deal.actionable:
            accepted.append(deal)
        else:
            rejected.append((deal.route_key, reasons + [f"missing {field}" for field in deal.missing_fields]))
    top = sorted(accepted, key=lambda deal: deal.total_price_eur or deal.total_price)[:10]
    targets = {"NCE-SVQ": "absent", "NCE-STN": "absent", "NCE-FCO": "absent"}
    for deal in deals:
        route = f"{deal.origin_airport}-{deal.destination_airport}"
        if route in targets:
            ok, reasons = validate_deal(deal, settings, today=settings.search_start_date)
            targets[route] = "présent accepté" if ok and deal.actionable else f"présent rejeté: {', '.join(reasons)}"
    typer.echo("endpoint=google_flights_deals")
    typer.echo(f"params={json.dumps(provider.last_public_params, ensure_ascii=False)}")
    typer.echo(f"offres_brutes={provider.last_raw_count}")
    typer.echo(f"offres_normalisées={provider.last_normalized_count}")
    typer.echo(f"offres_acceptées={len(accepted)}")
    typer.echo(f"offres_rejetées={len(rejected)}")
    typer.echo("top_10_prix=" + ", ".join(f"{deal.destination_airport}:{deal.total_price_eur or deal.total_price}" for deal in top))
    for route, status in targets.items():
        typer.echo(f"{route}={status}")
    if rejected:
        reason_counts: dict[str, int] = {}
        for _route, reasons in rejected:
            for reason in reasons:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        typer.echo(f"raisons_rejet={json.dumps(reason_counts, ensure_ascii=False)}")
    typer.echo(f"json_debug={provider.last_debug_path}")


@app.command("google-flight-deals-probes")
def google_flight_deals_probes_cmd() -> None:
    settings = get_settings()
    if not settings.serpapi_api_key:
        typer.echo("SERPAPI_API_KEY manquant")
        return
    probes = [
        ("SVQ", date(2026, 7, 16), date(2026, 7, 23)),
        ("STN", date(2026, 7, 21), date(2026, 7, 28)),
        ("FCO", date(2026, 8, 28), date(2026, 8, 31)),
    ]
    for destination, depart, ret in probes:
        result = asyncio.run(
            serpapi_smoke(
                api_key=settings.serpapi_api_key,
                origin="NCE",
                destination=destination,
                depart=depart,
                ret=ret,
            )
        )
        payload_path = result.debug_path or ""
        typer.echo(
            f"NCE-{destination} {depart.isoformat()}->{ret.isoformat()} "
            f"endpoint={result.endpoint} http={result.status_code} "
            f"best={result.best_flights} other={result.other_flights} debug={payload_path}"
        )


@app.command("bus-stations-search")
def bus_stations_search(query: str = typer.Option(..., "--query")) -> None:
    provider = FlixBusRapidApiProvider(get_settings())
    status = provider.status()
    if not status.enabled:
        typer.echo("; ".join(status.warnings))
        return
    stations = asyncio.run(provider.station_search(query))
    typer.echo(f"statut_http={provider.last_status_code or 'non disponible'}")
    typer.echo(f"endpoint={provider.last_path or 'non disponible'}")
    if provider.last_error:
        typer.echo(f"error={scrub_text(provider.last_error)}")
    for station in stations[:20]:
        typer.echo(f"{station['id']} | {station['name']} | {station.get('city') or ''}")


@app.command("flixbus-smoke")
def flixbus_smoke(
    origin: str = typer.Option(..., "--origin"),
    destination: str = typer.Option(..., "--destination"),
    depart: str = typer.Option(..., "--depart"),
    return_: str = typer.Option(..., "--return"),
    debug: bool = False,
) -> None:
    settings = get_settings()
    provider = FlixBusRapidApiProvider(settings)
    status = provider.status()
    if not status.enabled:
        typer.echo("; ".join(status.warnings))
        return
    origin_stations = asyncio.run(provider.station_search(origin))
    destination_stations = asyncio.run(provider.station_search(destination))
    typer.echo(f"stations_origin={len(origin_stations)}")
    typer.echo(f"stations_destination={len(destination_stations)}")
    if provider.last_status_code is not None:
        typer.echo(f"stations_statut_http={provider.last_status_code}")
        typer.echo(f"stations_endpoint={provider.last_path or 'non disponible'}")
    if provider.last_error:
        typer.echo(f"stations_error={scrub_text(provider.last_error)}")
    origin_id = origin_stations[0]["id"] if origin_stations else origin
    destination_id = destination_stations[0]["id"] if destination_stations else destination
    offers = asyncio.run(provider.search_roundtrip(origin_id, destination_id, depart, return_))
    if provider.last_status_code is not None:
        typer.echo(f"search_statut_http={provider.last_status_code}")
        typer.echo(f"search_endpoint={provider.last_path or 'non disponible'}")
    if provider.last_error:
        typer.echo(f"search_error={scrub_text(provider.last_error)}")
    typer.echo(f"offres={len(offers)}")
    for offer in offers[:10]:
        typer.echo(
            f"{offer.departure_at.isoformat()} {offer.origin_name}->{offer.destination_name} "
            f"{offer.price_amount} {offer.price_currency} {offer.operator_name} "
            f"duration={offer.duration_minutes} link={'oui' if offer.booking_url else 'non'}"
        )
        if offer.raw_debug_path:
            typer.echo(f"json_debug={offer.raw_debug_path}")


@app.command("flixbus-openapi-city-search")
def flixbus_openapi_city_search(query: list[str] = typer.Option(..., "--query")) -> None:
    settings = get_settings()
    provider = FlixBusOpenApiProvider(settings)
    status = provider.status()
    if not status.enabled:
        typer.echo("; ".join(status.warnings))
        return

    async def run() -> None:
        import httpx

        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            for value in query:
                lookup = await provider.city_search(client, value)
                typer.echo(f"requête_ville={json.dumps(lookup.params, ensure_ascii=False, sort_keys=True)}")
                typer.echo(f"endpoint={lookup.endpoint}")
                typer.echo(f"statut_http={lookup.status_code if lookup.status_code is not None else 'non disponible'}")
                typer.echo(f"réponse_brute={lookup.raw_summary}")
                typer.echo(f"city_id={lookup.city_id or 'absent'}")
                typer.echo(f"legacy_id={lookup.legacy_id or 'absent'}")
                typer.echo(f"id_kind={lookup.id_kind}")
                typer.echo(f"error={scrub_text(lookup.error) if lookup.error else 'non disponible'}")
                for row in lookup.results[:10]:
                    typer.echo(
                        f"- id={row.get('id') or 'absent'} legacy_id={row.get('legacy_id') or 'absent'} "
                        f"name={row.get('name') or row.get('city_name') or row.get('display_name') or 'non disponible'}"
                    )

    asyncio.run(run())


@app.command("flixbus-gtfs-refresh")
def flixbus_gtfs_refresh() -> None:
    path = refresh_gtfs()
    typer.echo(f"gtfs_zip={path}")
    typer.echo("status=downloaded")


@app.command("flixbus-gtfs-info")
def flixbus_gtfs_info() -> None:
    info = gtfs_info()
    typer.echo(f"fichier={'present' if info.present else 'absent'}")
    typer.echo(f"path={info.path}")
    typer.echo(f"cache_downloaded_at={info.downloaded_at.isoformat() if info.downloaded_at else 'non disponible'}")
    typer.echo(f"zip_size_bytes={info.size_bytes if info.size_bytes is not None else 'non disponible'}")
    for name, present in info.files_present.items():
        typer.echo(f"{name}={'present' if present else 'absent'}")
    typer.echo(f"stops={info.stops_count}")
    typer.echo(f"routes={info.routes_count}")
    typer.echo(f"trips={info.trips_count}")
    typer.echo(f"valid_from={info.valid_from or 'non disponible'}")
    typer.echo(f"valid_until={info.valid_until or 'non disponible'}")
    typer.echo("note=stop_id GTFS != legacy_id reservation")
    if info.error:
        typer.echo(f"error={scrub_text(info.error)}")
    typer.echo("exemples_nice:")
    for row in info.nice_examples:
        typer.echo(_format_gtfs_stop(row))
    typer.echo("exemples_paris:")
    for row in info.paris_examples:
        typer.echo(_format_gtfs_stop(row))


@app.command("flixbus-gtfs-stop-search")
def flixbus_gtfs_stop_search(query: str = typer.Option(..., "--query")) -> None:
    info = gtfs_info()
    if not info.present:
        typer.echo("gtfs_zip=absent")
        typer.echo("note=stop_id GTFS != legacy_id reservation")
        return
    stops = search_stops(query)
    typer.echo(f"query={query}")
    typer.echo(f"results={len(stops)}")
    typer.echo("note=stop_id GTFS != legacy_id reservation")
    for row in stops:
        typer.echo(_format_gtfs_stop(row))


@app.command("flixbus-autocomplete")
def flixbus_autocomplete(query: str = typer.Option(..., "--query"), lang: str = typer.Option("fr", "--lang")) -> None:
    diagnostic = asyncio.run(autocomplete_city(query, lang=lang))
    typer.echo(f"endpoint={diagnostic.endpoint}")
    typer.echo(f"params={json.dumps(diagnostic.params, ensure_ascii=False, sort_keys=True)}")
    typer.echo(f"http_status={diagnostic.status_code if diagnostic.status_code is not None else 'non disponible'}")
    typer.echo(f"raw_count={diagnostic.raw_count}")
    typer.echo(f"ambiguous={str(diagnostic.ambiguous).lower()}")
    typer.echo(f"selected_id={(diagnostic.selected or {}).get('id') or 'absent'}")
    typer.echo(f"selected_legacy_id={(diagnostic.selected or {}).get('legacy_id') or 'absent'}")
    typer.echo(f"error={scrub_text(diagnostic.error) if diagnostic.error else 'non disponible'}")
    for row in diagnostic.results:
        typer.echo(
            " | ".join(
                [
                    f"name={row.get('name') or 'non disponible'}",
                    f"legacy_id={row.get('legacy_id') or 'absent'}",
                    f"id={row.get('id') or 'absent'}",
                    f"slug={row.get('slug') or 'absent'}",
                    f"country_code={row.get('country_code') or 'absent'}",
                ]
            )
        )


@app.command("flixbus-city-cache-set")
def flixbus_city_cache_set(
    query: str = typer.Option(..., "--query"),
    id: str = typer.Option(..., "--id"),
    legacy_id: str = typer.Option(..., "--legacy-id"),
    name: str = typer.Option(..., "--name"),
    slug: str = typer.Option("", "--slug"),
    country_code: str = typer.Option("", "--country-code"),
) -> None:
    mapping = save_city_mapping(query=query, id=id, legacy_id=legacy_id, name=name, slug=slug, country_code=country_code)
    typer.echo(
        f"stored=true query={mapping['query']} id={mapping['id']} "
        f"legacy_id={mapping['legacy_id']} name={mapping['name']}"
    )


@app.command("smoke-flixbus-openapi")
def smoke_flixbus_openapi(
    from_: str = typer.Option("Nice", "--from", "--origin"),
    to: str = typer.Option("Paris", "--to", "--destination"),
    depart: str = typer.Option("2026-07-30", "--depart"),
    return_: str = typer.Option("2026-08-02", "--return"),
    try_legacy_id: bool = typer.Option(False, "--try-legacy-id"),
) -> None:
    settings = get_settings()
    provider = FlixBusOpenApiProvider(settings)
    status = provider.status()
    typer.echo("etape_gtfs=stop_search")
    info = gtfs_info()
    if info.present:
        typer.echo(f"gtfs_from_matches={len(search_stops(from_))}")
        typer.echo(f"gtfs_to_matches={len(search_stops(to))}")
    else:
        typer.echo("gtfs_zip=absent")
    typer.echo("note=stop_id GTFS != legacy_id reservation")
    if status.enabled and try_legacy_id:
        offers = asyncio.run(provider.search_roundtrip(from_, to, depart, return_, use_legacy_id=True))
    else:
        offers = asyncio.run(provider.search_roundtrip(from_, to, depart, return_)) if status.enabled else []
    typer.echo(f"provider={provider.name}")
    typer.echo(f"enabled={str(status.enabled).lower()}")
    typer.echo(f"attempted={str(provider.last_attempted).lower()}")
    typer.echo("etape_autocomplete=id_lookup")
    if provider.last_city_lookups:
        origin_lookup = provider.last_city_lookups[0]
        typer.echo(f"lookup_source_départ={origin_lookup.source}")
        typer.echo(f"requête_ville_départ={json.dumps(origin_lookup.params, ensure_ascii=False, sort_keys=True)}")
        typer.echo(f"réponse_ville_départ={origin_lookup.raw_summary}")
        typer.echo(f"id_départ={origin_lookup.city_id or 'absent'}")
        typer.echo(f"legacy_id_départ={origin_lookup.legacy_id or 'absent'}")
        typer.echo(f"ambiguous_départ={str(origin_lookup.ambiguous).lower()}")
        if len(provider.last_city_lookups) > 1:
            destination_lookup = provider.last_city_lookups[1]
            typer.echo(f"lookup_source_arrivée={destination_lookup.source}")
            typer.echo(f"requête_ville_arrivée={json.dumps(destination_lookup.params, ensure_ascii=False, sort_keys=True)}")
            typer.echo(f"réponse_ville_arrivée={destination_lookup.raw_summary}")
            typer.echo(f"id_arrivée={destination_lookup.city_id or 'absent'}")
            typer.echo(f"legacy_id_arrivée={destination_lookup.legacy_id or 'absent'}")
            typer.echo(f"ambiguous_arrivée={str(destination_lookup.ambiguous).lower()}")
    else:
        typer.echo(f"cache_from={'present' if find_cached_mapping(from_) else 'absent'}")
        typer.echo(f"cache_to={'present' if find_cached_mapping(to) else 'absent'}")
    typer.echo("etape_search=search_if_ids_present")
    typer.echo(f"lookup_source={provider.last_public_params.get('lookup_source', provider.last_lookup_source)}")
    typer.echo(f"id_kind={provider.last_public_params.get('id_kind', provider.last_id_kind)}")
    typer.echo(f"from_city_id={provider.last_from_city_id or 'absent'}")
    typer.echo(f"from_legacy_id={provider.last_from_legacy_id or 'absent'}")
    typer.echo(f"to_city_id={provider.last_to_city_id or 'absent'}")
    typer.echo(f"to_legacy_id={provider.last_to_legacy_id or 'absent'}")
    typer.echo(f"lookup_ambiguous={str(provider.last_lookup_ambiguous).lower()}")
    typer.echo(f"lookup_http_status={provider.last_lookup_status_code if provider.last_lookup_status_code is not None else 'non disponible'}")
    typer.echo(f"search_http_status={provider.last_search_status_code if provider.last_search_status_code is not None else 'non appelé'}")
    typer.echo(f"endpoint={provider.last_path or 'non disponible'}")
    typer.echo(f"http_status={provider.last_status_code if provider.last_status_code is not None else 'non disponible'}")
    typer.echo(f"raw_count={provider.last_raw_count}")
    typer.echo(f"normalized_count={provider.last_normalized_count}")
    typer.echo(f"error={scrub_text(provider.last_error) if provider.last_error else 'non disponible'}")
    typer.echo(f"params={json.dumps(provider.last_public_params, ensure_ascii=True, sort_keys=True)}")
    typer.echo(f"offres={len(offers)}")


def _format_gtfs_stop(row: Mapping[str, object]) -> str:
    return (
        f"stop_id={row.get('stop_id') or 'absent'} | "
        f"stop_name={row.get('stop_name') or 'non disponible'} | "
        f"stop_lat={row.get('stop_lat') or ''} | "
        f"stop_lon={row.get('stop_lon') or ''} | "
        f"location_type={row.get('location_type') or ''} | "
        f"parent_station={row.get('parent_station') or ''}"
    )


if __name__ == "__main__":
    app()
