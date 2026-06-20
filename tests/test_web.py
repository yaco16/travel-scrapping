from datetime import date, datetime

from fastapi.testclient import TestClient

from travel_scrapping.config import get_settings
from travel_scrapping.db import Deal, PriceObservation, ProviderStatusRow, SearchRun, init_db, session_scope
from travel_scrapping.main import create_app
from travel_scrapping.web import routes as web_routes


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


def test_run_search_redirects_to_results_run_id(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")

    async def fake_run_search(settings, *, modes, depart_from):
        assert settings.origin_airport == "NCE"
        assert settings.min_nights == 3
        assert settings.max_nights == 5
        assert settings.max_roundtrip_price_eur == 100
        assert modes == "flight,bus"
        assert depart_from == date(2026, 7, 1)
        return 42

    monkeypatch.setattr(web_routes, "run_search", fake_run_search)
    client = TestClient(create_app())
    response = client.post(
        "/run",
        data={
            "origin_airport": "NCE",
            "depart_date_min": "2026-07-01",
            "depart_date_max": "2026-08-30",
            "min_nights": "3",
            "max_nights": "5",
            "max_price": "100",
            "modes": ["flight", "bus"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/results?run_id=42"


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
    assert "Observations valides: 0" in response.text
    assert "Observations invalides: 1" in response.text
    assert "1 observations invalides historiques détectées" in response.text
    assert "None-None" not in response.text


def test_results_filter_by_run_id(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        old_run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=45)
        latest_run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=55)
        session.add_all([old_run, latest_run])
        session.flush()
        session.add_all(
            [
                Deal(
                    run_id=old_run.id,
                    source="old",
                    origin_airport="NCE",
                    destination_airport="VCE",
                    outbound_date=date(2026, 7, 2),
                    return_date=date(2026, 7, 6),
                    nights=4,
                    total_price=45,
                    currency="EUR",
                    total_price_eur=45,
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/old",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=latest_run.id,
                    source="latest",
                    origin_airport="NCE",
                    destination_airport="BCN",
                    outbound_date=date(2026, 7, 2),
                    return_date=date(2026, 7, 6),
                    nights=4,
                    total_price=55,
                    currency="EUR",
                    total_price_eur=55,
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/latest",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
            ]
        )
        old_run_id = old_run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={old_run_id}")

    assert response.status_code == 200
    assert "Venise" in response.text
    assert "Barcelone" not in response.text
    assert "45,00 €" in response.text


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
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/old",
                    actionable=True,
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
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/bad",
                    actionable=True,
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
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/good",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
            ]
        )
        session.add(
            PriceObservation(
                route_key="missing",
                run_id=latest_run.id,
                origin_iata=None,
                destination_iata=None,
                departure_date=None,
                return_date=None,
                nights=None,
                price=None,
                price_eur=0,
                source="legacy",
            )
        )
    client = TestClient(create_app())
    response = client.get("/results")
    assert response.status_code == 200
    assert "Venise" in response.text
    assert "Bratislava" not in response.text
    assert "Barcelone" not in response.text
    assert "legacy" not in response.text
    assert "55,00 €" in response.text


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
                airlines_json='["easyJet"]',
                operator_name="easyJet",
                booking_url="https://example.test/good",
                actionable=True,
                confidence="high",
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Venise" in response.text
    assert ">VCE<" not in response.text


def test_results_do_not_render_raw_warnings_json(tmp_path, monkeypatch):
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
                source="serpapi",
                transport_mode="flight",
                origin_airport="NCE",
                destination_airport="VCE",
                outbound_date=date(2026, 7, 2),
                return_date=date(2026, 7, 6),
                nights=4,
                total_price=55,
                currency="EUR",
                total_price_eur=55,
                airlines_json='["easyJet"]',
                operator_name="easyJet",
                booking_url="https://example.test/good",
                actionable=True,
                confidence="high",
                warnings_json='["raw warning"]',
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert '["raw warning"]' not in response.text
    assert "raw warning" not in response.text


def test_deals_api_returns_normalized_deals_and_provider_status(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "2000")
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=1234.5)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="flixbus_rapidapi",
                enabled=True,
                ok=False,
                warnings_json="[]",
                error="Too many requests",
            )
        )
        session.add(
            Deal(
                run_id=run.id,
                source="flixbus_rapidapi",
                transport_mode="bus",
                provider="flixbus_rapidapi",
                origin_airport="NCE",
                destination_airport="VCE",
                outbound_date=date(2026, 7, 30),
                return_date=date(2026, 8, 2),
                nights=3,
                total_price=1234.5,
                currency="EUR",
                total_price_eur=1234.5,
                airlines_json="[]",
                operator_name="FlixBus",
                booking_url="https://example.test/flixbus",
                actionable=True,
                confidence="high",
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/deals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == 1
    assert payload["deals"][0]["destination"] == "Venise"
    assert payload["deals"][0]["dates"] == "30/07/26 - 02/08/26"
    assert payload["deals"][0]["nights"] == 3
    assert payload["deals"][0]["price"] == "1 234,50 €"
    assert payload["deals"][0]["provider"] == "flixbus_rapidapi"
    assert payload["deals"][0]["provider_status"] == "Too many requests"
    assert "flixbus_rapidapi" in payload["provider_statuses"]


def test_results_show_flixbus_provider_error_without_secret(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=1)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="flixbus_rapidapi",
                enabled=True,
                ok=False,
                warnings_json="[]",
                error="You are not subscribed to this API.",
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "You are not subscribed to this API." in response.text
    assert "RAPIDAPI_KEY" not in response.text
