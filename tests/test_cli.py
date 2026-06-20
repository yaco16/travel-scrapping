from datetime import date

from typer.testing import CliRunner

from travel_scrapping.cli import app
from travel_scrapping.config import get_settings
from travel_scrapping.db import PriceObservation, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.schemas import DealCandidate


runner = CliRunner()


def _seed_observations() -> None:
    factory = init_db(get_settings())
    for price in [40, 42]:
        with session_scope(factory) as session:
            run = SearchRun(status="completed")
            session.add(run)
            session.flush()
            inserted = save_deals(
                session,
                run,
                [
                    DealCandidate(
                        source="test",
                        origin_airport="NCE",
                        destination_airport="BCN",
                        destination_city="Barcelone",
                        outbound_date=date(2026, 7, 1),
                        return_date=date(2026, 7, 4),
                        nights=3,
                        total_price=price,
                        airlines=["U2"],
                        booking_url="https://example.test/book",
                        raw_payload={"price": price},
                    )
                ],
            )
            run.accepted_count = inserted
    with session_scope(factory) as session:
        session.add(
            PriceObservation(
                route_key="missing",
                run_id=None,
                departure_date=None,
                return_date=None,
                nights=None,
                price=None,
                price_eur=0,
                source="test",
            )
        )


def test_sqlite_diagnostics_ignores_invalid_variations(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/cli.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    _seed_observations()

    result = runner.invoke(app, ["sqlite-diagnostics"])

    assert result.exit_code == 0
    assert "observations_valides=2" in result.output
    assert "observations_invalides=1" in result.output
    assert "1 observations invalides historiques détectées" in result.output
    assert "NCE-BCN 2026-07-01->2026-07-04 nights=3 source=test count=2 min=40.0 max=42.0" in result.output
    assert "None-None" not in result.output


def test_sqlite_clean_invalid_dry_run_does_not_delete(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/cli.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    _seed_observations()

    result = runner.invoke(app, ["sqlite-clean-invalid", "--dry-run"])

    assert result.exit_code == 0
    assert "1 observations invalides seraient supprimées" in result.output
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        assert session.query(PriceObservation).count() == 3
        assert session.query(SearchRun).count() == 2


def test_sqlite_clean_invalid_execute_deletes_only_invalid_observations(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/cli.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    _seed_observations()

    result = runner.invoke(app, ["sqlite-clean-invalid", "--execute"])

    assert result.exit_code == 0
    assert "1 observations invalides supprimées" in result.output
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        assert session.query(PriceObservation).count() == 2
        assert session.query(SearchRun).count() == 2


def test_cli_config_smoke_and_missing_key_commands(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/cli.db")
    monkeypatch.setenv("SERPAPI_API_KEY", "")
    monkeypatch.setenv("RAPIDAPI_KEY", "")

    assert runner.invoke(app, ["config"]).exit_code == 0
    assert runner.invoke(app, ["smoke"]).output.strip() == "db=ok providers=manual-live-only"
    assert "SERPAPI_API_KEY manquant" in runner.invoke(
        app,
        ["serpapi-smoke", "--origin", "NCE", "--destination", "VCE", "--depart", "2026-07-30", "--return", "2026-08-02"],
    ).output
    assert "RAPIDAPI_KEY missing" in runner.invoke(app, ["bus-stations-search", "--query", "Nice"]).output
    assert "RAPIDAPI_KEY missing" in runner.invoke(
        app,
        ["flixbus-smoke", "--origin", "Nice", "--destination", "Venise", "--depart", "2026-07-30", "--return", "2026-08-02"],
    ).output


def test_cli_airports_import_and_diagnostics(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/cli.db")

    def fake_import(session, force_refresh=False):
        from pathlib import Path
        from travel_scrapping.airports.ourairports import ImportResult

        return ImportResult(Path("data/sources/ourairports/airports.csv"), 2)

    monkeypatch.setattr("travel_scrapping.cli.import_ourairports", fake_import)

    result = runner.invoke(app, ["airports-import-ourairports", "--force-refresh"])
    assert result.exit_code == 0
    assert "importés=2" in result.output
    diagnostics = runner.invoke(app, ["airports-diagnostics"])
    assert diagnostics.exit_code == 0
    assert "aéroports en cache=0" in diagnostics.output
