from __future__ import annotations

import asyncio
import json

import typer

from travel_scrapping.config import get_settings, safe_settings_dict
from travel_scrapping.db import init_db, session_scope
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


if __name__ == "__main__":
    app()
