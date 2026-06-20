from datetime import date, datetime

from fastapi.testclient import TestClient

from travel_scrapping.config import get_settings
from travel_scrapping.db import Deal, PriceObservation, SearchRun, init_db, session_scope
from travel_scrapping.main import create_app


def test_dashboard_routes_return_200(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    client = TestClient(create_app())
    for path in ["/", "/search", "/results", "/history", "/sqlite"]:
        response = client.get(path)
        assert response.status_code == 200


def test_email_button_hidden_by_default(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    monkeypatch.setenv("EMAIL_ENABLED", "false")
    client = TestClient(create_app())
    response = client.get("/results")
    assert response.status_code == 200
    assert "Envoyer email" not in response.text


def test_main_menu_hides_sqlite(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert '<a href="/sqlite">SQLite</a>' not in response.text
    assert '<a href="/history">Historique</a>' in response.text


def test_sqlite_diagnostic_handles_null_dates(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        session.add(
            PriceObservation(
                route_key="missing",
                departure_date=None,
                return_date=None,
                nights=None,
                price=None,
                price_eur=0,
                source="test",
            )
        )
    client = TestClient(create_app())
    response = client.get("/sqlite")
    assert response.status_code == 200
    assert "Dates non disponibles" in response.text
    assert "Non disponible" in response.text


def test_results_show_only_valid_deals_from_latest_run(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MIN_NIGHTS", "3")
    monkeypatch.setenv("MAX_NIGHTS", "5")
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        old_run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=40)
        latest_run = SearchRun(status="completed", accepted_count=2, rejected_count=0, cheapest_price_eur=55)
        session.add_all([old_run, latest_run])
        session.flush()
        session.add_all(
            [
                Deal(
                    run_id=old_run.id,
                    source="old",
                    origin_airport="NCE",
                    destination_airport="BCN",
                    outbound_date=date(2026, 7, 1),
                    return_date=date(2026, 7, 4),
                    nights=3,
                    total_price=40,
                    currency="EUR",
                    total_price_eur=40,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=latest_run.id,
                    source="bad",
                    origin_airport="NCE",
                    destination_airport="BTS",
                    outbound_date=date(2026, 7, 2),
                    return_date=date(2026, 8, 26),
                    nights=3,
                    total_price=55,
                    currency="EUR",
                    total_price_eur=55,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=latest_run.id,
                    source="good",
                    origin_airport="NCE",
                    destination_airport="VCE",
                    outbound_date=date(2026, 7, 2),
                    return_date=date(2026, 7, 6),
                    nights=4,
                    total_price=55,
                    currency="EUR",
                    total_price_eur=55,
                    confidence="high",
                    fetched_at=now,
                ),
            ]
        )
    client = TestClient(create_app())
    response = client.get("/results")
    assert response.status_code == 200
    assert "Venise" in response.text
    assert "Bratislava" not in response.text
    assert "Barcelone" not in response.text
    assert ">55<" in response.text


def test_results_display_api_ninjas_cached_city_not_iata(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=55)
        session.add(run)
        session.flush()
        session.add(
            Deal(
                run_id=run.id,
                source="good",
                origin_airport="NCE",
                destination_airport="VCE",
                outbound_date=date(2026, 7, 2),
                return_date=date(2026, 7, 6),
                nights=4,
                total_price=55,
                currency="EUR",
                total_price_eur=55,
                confidence="high",
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Venise" in response.text
    assert ">VCE<" not in response.text
