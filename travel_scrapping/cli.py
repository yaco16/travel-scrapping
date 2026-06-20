from __future__ import annotations

import asyncio
import json

import typer
from sqlalchemy import func, select

from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import PriceObservation, SearchRun, init_db, session_scope
from travel_scrapping.email.brevo import send_deals_email
from travel_scrapping.search.engine import latest_deals, run_search

app = typer.Typer()


@app.command()
def config() -> None:
    typer.echo(json.dumps(safe_settings_dict(get_settings()), indent=2))


@app.command()
def search(send_email: bool = False) -> None:
    settings = get_settings()
    run_id = asyncio.run(run_search(settings))
    typer.echo(f"run_id={run_id}")
    if send_email:
        _run, deals = latest_deals(settings)
        result = asyncio.run(send_deals_email(settings, deals))
        typer.echo(json.dumps(result))


@app.command()
def top(limit: int = 50) -> None:
    run, deals = latest_deals(get_settings(), limit)
    typer.echo(f"run_id={run.id if run else 'none'}")
    for deal in deals:
        typer.echo(f"{deal.destination_airport} {deal.outbound_date}-{deal.return_date} {deal.total_price_eur:.2f} EUR")


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
        typer.echo(f"campaigns={session.query(SearchRun).count()}")
        typer.echo(f"observations={session.query(PriceObservation).count()}")
        typer.echo("latest_observations:")
        latest = session.scalars(select(PriceObservation).order_by(PriceObservation.id.desc()).limit(20))
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


if __name__ == "__main__":
    app()
