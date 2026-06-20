import json
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
    for path in ["/", "/results", "/history", "/sqlite"]:
        response = client.get(path)
        assert response.status_code == 200


def test_search_redirects_to_home_with_303(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    client = TestClient(create_app())

    response = client.get("/search", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


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
    assert '<a href="/search">Recherche</a>' not in response.text
    assert '<a href="/history">Historique</a>' in response.text


def test_home_keeps_search_form_and_hides_travelpayouts_marker_warning(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "token")
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert '<form action="/run" method="post" class="form-grid" data-run-form>' in response.text
    assert "Travelpayouts désactivé : TRAVELPAYOUTS_MARKER manquant" not in response.text


def test_dashboard_configuration_uses_end_date_and_french_formats(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "150")
    monkeypatch.setenv("MIN_NIGHTS", "1")
    monkeypatch.setenv("MAX_NIGHTS", "7")
    monkeypatch.setenv("SEARCH_END_DATE", "2026-08-31")
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert (
        "Origine NCE · Budget max 150,00 EUR · 1-7 nuits · "
        "départ du 01/07/26 au 31/08/26 · 1 correspondance max"
    ) in response.text
    assert "jusqu&#39;au None" not in response.text


def test_run_search_redirects_to_results_run_id(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    captured = {}

    def fake_create_search_run(settings, *, status, modes):
        assert settings.origin_airport == "NCE"
        assert settings.search_start_date == date(2026, 7, 1)
        assert settings.search_end_date == date(2026, 8, 31)
        assert settings.min_nights == 3
        assert settings.max_nights == 5
        assert settings.max_roundtrip_price_eur == 100
        assert settings.max_stops == 1
        assert status == "pending"
        assert modes == "flight,bus"
        return 42

    def fake_run_search_background(settings, *, run_id, modes, depart_from):
        captured["origin"] = settings.origin_airport
        captured["run_id"] = run_id
        captured["modes"] = modes
        captured["depart_from"] = depart_from

    monkeypatch.setattr(web_routes, "create_search_run", fake_create_search_run)
    monkeypatch.setattr(web_routes, "run_search_background", fake_run_search_background)
    client = TestClient(create_app())
    response = client.post(
        "/run",
        data={
            "origin_airport": "NCE",
            "depart_date_min": "2026-07-01",
            "depart_date_max": "2026-08-31",
            "min_nights": "3",
            "max_nights": "5",
            "max_price": "100",
            "max_stops": "1",
            "modes": ["flight", "bus"],
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/results?run_id=42"
    assert captured == {
        "origin": "NCE",
        "run_id": 42,
        "modes": "flight,bus",
        "depart_from": date(2026, 7, 1),
    }


def test_home_search_form_prevents_double_submit(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "data-run-form" in response.text
    assert "data-run-submit" in response.text
    assert "button.disabled = true" in response.text


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


def test_results_show_pending_status_and_auto_refresh(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="pending")
        session.add(run)
        session.flush()
        run_id = run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={run_id}")

    assert response.status_code == 200
    assert f"Run #{run_id}" in response.text
    assert '<strong class="status-badge pending-blink">pending</strong>' in response.text
    assert "Étape 01 — Configuration chargée" in response.text
    assert "Étape 02 — Recherche lancée" in response.text
    assert "step-spinner" not in response.text
    assert '<span class="step-state pending-blink">pending</span>' in response.text
    assert '<meta http-equiv="refresh" content="5">' in response.text


def test_results_tabs_use_htmx_and_anchor_fallback(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=0)
        session.add(run)
        session.flush()
        run_id = run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={run_id}")

    assert response.status_code == 200
    assert 'id="results-offers-panel"' in response.text
    assert 'hx-target="#results-offers-panel"' in response.text
    assert 'hx-swap="outerHTML"' in response.text
    assert f'href="/results?run_id={run_id}&mode=flight#results-offers-panel"' in response.text
    assert f'hx-push-url="/results?run_id={run_id}&mode=flight"' in response.text
    assert f'href="/results?run_id={run_id}&mode=train#results-offers-panel"' in response.text
    assert f'hx-push-url="/results?run_id={run_id}&mode=train"' in response.text
    assert ">Train</a>" in response.text


def test_results_filter_by_train_mode(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=3, rejected_count=0, cheapest_price_eur=30)
        session.add(run)
        session.flush()
        session.add_all(
            [
                Deal(
                    run_id=run.id,
                    source="serpapi_google_flights_deals",
                    transport_mode="flight",
                    provider="serpapi_google_flights_deals",
                    origin_airport="NCE",
                    destination_airport="BCN",
                    destination_city="Barcelone",
                    outbound_date=date(2026, 7, 2),
                    return_date=date(2026, 7, 6),
                    nights=4,
                    total_price=40,
                    currency="EUR",
                    total_price_eur=40,
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/flight",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=run.id,
                    source="flixbus_rapidapi",
                    transport_mode="bus",
                    provider="flixbus_rapidapi",
                    origin_airport="NCE",
                    destination_airport="VCE",
                    destination_city="Venise",
                    outbound_date=date(2026, 7, 3),
                    return_date=date(2026, 7, 7),
                    nights=4,
                    total_price=35,
                    currency="EUR",
                    total_price_eur=35,
                    airlines_json="[]",
                    operator_name="FlixBus",
                    booking_url="https://example.test/bus",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=run.id,
                    source="distribusion",
                    transport_mode="train",
                    provider="distribusion",
                    origin_airport="NCE",
                    destination_airport="PAR",
                    destination_city="Paris",
                    outbound_date=date(2026, 7, 4),
                    return_date=date(2026, 7, 8),
                    nights=4,
                    total_price=30,
                    currency="EUR",
                    total_price_eur=30,
                    airlines_json="[]",
                    operator_name="SNCF",
                    booking_url="https://example.test/train",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
            ]
        )
        run_id = run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={run_id}&mode=train")

    assert response.status_code == 200
    assert "Train" in response.text
    assert "SNCF" in response.text
    assert "easyJet" not in response.text
    assert "FlixBus" not in response.text
    assert "1 offres affichées sur 3 acceptées" in response.text


def test_results_htmx_request_returns_offers_panel_only(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=0)
        session.add(run)
        session.flush()
        run_id = run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={run_id}&mode=bus", headers={"HX-Request": "true"})

    assert response.status_code == 200
    assert response.text.lstrip().startswith('<div id="results-offers-panel">')
    assert "results-hero" not in response.text


def test_history_shows_run_start_date_between_id_and_status(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        session.add(
            SearchRun(
                started_at=datetime(2026, 6, 20, 9, 56),
                status="completed",
                accepted_count=2,
                rejected_count=3,
                cheapest_price_eur=88.9,
            )
        )

    client = TestClient(create_app())
    response = client.get("/history")

    assert response.status_code == 200
    header = "<th>ID</th><th>Date</th><th>Statut</th><th>Acceptés</th><th>Rejetés</th><th>Meilleur prix</th>"
    row = (
        "<td>1</td><td>20/06/26 09:56</td><td>completed</td>"
        "<td>2</td><td>3</td><td>88,90 €</td>"
    )
    assert header in response.text
    assert row in response.text
    assert "None" not in response.text


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


def test_results_display_country_next_to_city(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=44)
        session.add(run)
        session.flush()
        session.add(
            Deal(
                run_id=run.id,
                source="serpapi_google_flights_deals",
                transport_mode="flight",
                origin_airport="NCE",
                destination_airport="STN",
                destination_city="Londres",
                destination_country="GB",
                outbound_date=date(2026, 7, 21),
                return_date=date(2026, 7, 28),
                nights=7,
                total_price=44,
                currency="EUR",
                total_price_eur=44,
                airlines_json='["Ryanair"]',
                operator_name="Ryanair",
                booking_url="https://example.test/stn",
                actionable=True,
                confidence="high",
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Londres" in response.text
    assert "Royaume-Uni" in response.text
    assert "44,00 €" in response.text


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
    assert payload["processing_steps"] == [
        "Étape 01 — Configuration chargée",
        "Étape 02 — Recherche lancée",
        "Étape 03 — Résultats récupérés",
        "Étape 04 — Résultats filtrés",
        "Étape 05 — Résultats affichés",
    ]
    assert payload["deals"][0]["destination"] == "Venise"
    assert payload["deals"][0]["dates"] == "30/07/26 - 02/08/26"
    assert payload["deals"][0]["nights"] == 3
    assert payload["deals"][0]["price"] == "1 234,50 €"
    assert payload["deals"][0]["provider"] == "flixbus_rapidapi"
    assert payload["deals"][0]["provider_status"] == "Too many requests"
    assert "flixbus_rapidapi" in payload["provider_statuses"]
    assert payload["provider_diagnostics"][0]["provider"] == "flixbus_rapidapi"
    assert payload["no_offer_message"] == "Aucune offre exploitable trouvée. 0 offre reçue des fournisseurs actifs."


def test_deals_api_serializes_train_deal(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "2000")
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 12, 0, 0)
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=1, rejected_count=0, cheapest_price_eur=89.9)
        session.add(run)
        session.flush()
        session.add(
            Deal(
                run_id=run.id,
                source="distribusion",
                transport_mode="train",
                provider="distribusion",
                origin_airport="NCE",
                destination_airport="PAR",
                destination_city="Paris",
                outbound_date=date(2026, 7, 30),
                return_date=date(2026, 8, 2),
                nights=3,
                total_price=89.9,
                currency="EUR",
                total_price_eur=89.9,
                airlines_json="[]",
                operator_name="SNCF",
                booking_url="https://example.test/train",
                actionable=True,
                confidence="high",
                fetched_at=now,
            )
        )

    client = TestClient(create_app())
    response = client.get("/deals")

    assert response.status_code == 200
    deal = response.json()["deals"][0]
    assert deal["transport_mode"] == "Train"
    assert deal["dates"] == "30/07/26 - 02/08/26"
    assert deal["price"] == "89,90 €"
    assert deal["provider"] == "distribusion"
    assert deal["operator"] == "SNCF"
    assert deal["booking_url"] == "https://example.test/train"


def test_results_distribusion_disabled_without_secret_leak(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DISTRIBUSION_API_KEY", "placeholder-value")
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=0)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="distribusion",
                enabled=False,
                ok=True,
                warnings_json='["DISTRIBUSION credentials missing"]',
                key_present=True,
                attempted=False,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")
    payload = client.get("/deals").json()

    assert response.status_code == 200
    assert "distribusion" in response.text
    assert "DISTRIBUSION credentials missing" in response.text
    assert "placeholder-value" not in response.text
    assert "placeholder-value" not in str(payload)
    assert payload["provider_diagnostics"][0]["provider"] == "distribusion"
    assert payload["provider_diagnostics"][0]["enabled"] is False
    assert payload["provider_diagnostics"][0]["attempted"] is False
    assert payload["provider_diagnostics"][0]["warnings"] == ["DISTRIBUSION credentials missing"]


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


def test_results_show_zero_offer_diagnostic(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=0)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="serpapi",
                enabled=True,
                ok=True,
                key_present=True,
                attempted=True,
                http_status=200,
                raw_count=0,
                normalized_count=0,
                accepted_count=0,
                rejected_count=0,
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Aucune offre exploitable trouvée. 0 offre reçue des fournisseurs actifs." in response.text
    assert "<td>serpapi</td>" in response.text
    assert "<td>200</td>" in response.text
    assert "La recherche ne peut pas reproduire Google Flight Deals : endpoint différent." in response.text


def test_results_show_all_rejected_diagnostic_and_marker_warning(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "token")
    monkeypatch.delenv("TRAVELPAYOUTS_MARKER", raising=False)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=0, rejected_count=47)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="serpapi",
                enabled=True,
                ok=True,
                key_present=True,
                attempted=True,
                http_status=200,
                raw_count=47,
                normalized_count=47,
                accepted_count=0,
                rejected_count=47,
                main_rejection_reason="over budget (47)",
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Aucune offre exploitable trouvée. 47 offres rejetées : over budget (47)." in response.text
    assert "Travelpayouts : endpoints nécessitant un marker désactivés" in response.text


def test_results_show_google_flight_deals_comparison_and_destinations(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    factory = init_db(get_settings())
    with session_scope(factory) as session:
        run = SearchRun(status="completed", accepted_count=3, rejected_count=1)
        session.add(run)
        session.flush()
        session.add(
            ProviderStatusRow(
                run_id=run.id,
                name="serpapi_google_flights_deals",
                enabled=True,
                ok=True,
                key_present=True,
                attempted=True,
                http_status=200,
                raw_count=4,
                normalized_count=3,
                accepted_count=3,
                rejected_count=1,
                main_rejection_reason="too many stops (1)",
                request_params_json=(
                    '{"engine": "google_flights_deals", "departure_id": "NCE", '
                    '"outbound_date": "2026-07-01,2026-08-31", "trip_length": "1,7", '
                    '"max_price": "150", "stops": "2", "currency": "EUR", "gl": "fr", "hl": "fr"}'
                ),
                destination_examples_json='["Séville", "Londres", "Rome"]',
            )
        )

    client = TestClient(create_app())
    response = client.get("/results")

    assert response.status_code == 200
    assert "Comparaison Google Flight Deals" in response.text
    assert "Endpoint utilisé : google_flights_deals" in response.text
    assert "Offres brutes : 4 · normalisées : 3 · acceptées : 3 · rejetées : 1" in response.text
    assert "Séville, Londres, Rome" in response.text
    assert "2026-07-01,2026-08-31" in response.text


def test_results_use_run_snapshot_and_show_cheapest_first(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "100")
    monkeypatch.setenv("MIN_NIGHTS", "3")
    monkeypatch.setenv("MAX_NIGHTS", "5")
    factory = init_db(get_settings())
    now = datetime(2026, 6, 20, 13, 33, 0)
    config = {
        "origin_airport": "NCE",
        "budget_eur": 150,
        "search_start_date": "2026-07-01",
        "search_end_date": "2026-08-31",
        "min_nights": 1,
        "max_nights": 7,
        "max_stops": 1,
        "top_results_limit": 50,
        "currency": "EUR",
        "modes": "flight",
    }
    with session_scope(factory) as session:
        run = SearchRun(
            status="completed",
            accepted_count=2,
            rejected_count=1,
            cheapest_price_eur=44,
            config_json=json.dumps(config),
        )
        session.add(run)
        session.flush()
        session.add_all(
            [
                Deal(
                    run_id=run.id,
                    source="serpapi_google_flights_deals",
                    provider="serpapi_google_flights_deals",
                    origin_airport="NCE",
                    destination_airport="IBZ",
                    destination_city="Ibiza",
                    outbound_date=date(2026, 8, 31),
                    return_date=date(2026, 9, 4),
                    nights=4,
                    total_price=71,
                    currency="EUR",
                    total_price_eur=71,
                    airlines_json='["easyJet"]',
                    operator_name="easyJet",
                    booking_url="https://example.test/ibz",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
                Deal(
                    run_id=run.id,
                    source="serpapi_google_flights_deals",
                    provider="serpapi_google_flights_deals",
                    origin_airport="NCE",
                    destination_airport="STN",
                    destination_city="Londres",
                    outbound_date=date(2026, 7, 21),
                    return_date=date(2026, 7, 28),
                    nights=7,
                    total_price=44,
                    currency="EUR",
                    total_price_eur=44,
                    airlines_json='["Ryanair"]',
                    operator_name="Ryanair",
                    booking_url="https://example.test/stn",
                    actionable=True,
                    confidence="high",
                    fetched_at=now,
                ),
            ]
        )
        run_id = run.id

    client = TestClient(create_app())
    response = client.get(f"/results?run_id={run_id}")

    assert response.status_code == 200
    assert "44,00 €" in response.text
    assert "2 offres affichées sur 2 acceptées" in response.text
    assert "Meilleur prix" in response.text
    assert 'class="deal-card best"' in response.text
    assert 'class="badge best-badge">Meilleur prix</span>' in response.text
    assert "Budget max 150,00 EUR · 1-7 nuits" in response.text
    assert "Budget max 100,00 EUR · 3-5 nuits" not in response.text
    assert response.text.index("44,00 €") < response.text.index("71,00 €")


def test_country_display_known_codes():
    assert web_routes.country_display("GB") == "Royaume-Uni"
    assert web_routes.country_display("IT") == "Italie"
    assert web_routes.country_display("ES") == "Espagne"


def test_home_distinguishes_default_config_and_latest_run_snapshot(tmp_path, monkeypatch):
    get_settings.cache_clear()
    db_url = f"sqlite:///{tmp_path}/web.db"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "100")
    monkeypatch.setenv("MIN_NIGHTS", "3")
    monkeypatch.setenv("MAX_NIGHTS", "5")
    factory = init_db(get_settings())
    config = {
        "origin_airport": "NCE",
        "budget_eur": 150,
        "search_start_date": "2026-07-01",
        "search_end_date": "2026-08-31",
        "min_nights": 1,
        "max_nights": 7,
        "max_stops": 1,
        "top_results_limit": 50,
        "currency": "EUR",
        "modes": "flight",
    }
    with session_scope(factory) as session:
        run = SearchRun(
            started_at=datetime(2026, 6, 20, 13, 33),
            status="completed",
            accepted_count=28,
            rejected_count=2,
            cheapest_price_eur=44,
            config_json=json.dumps(config),
        )
        session.add(run)
        session.flush()
        run_id = run.id

    client = TestClient(create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert "Configuration par défaut" in response.text
    assert "Budget max 100,00 EUR · 3-5 nuits" in response.text
    assert "Dernier run" in response.text
    assert "Budget max 150,00 EUR · 1-7 nuits" in response.text
    assert f'href="/results?run_id={run_id}"' in response.text
    assert "Relancer avec cette configuration" in response.text
