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
