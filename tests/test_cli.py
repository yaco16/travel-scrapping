from datetime import date, datetime, timezone
from types import SimpleNamespace

from typer.testing import CliRunner

from travel_scrapping.airports import AirportInfo, AirportResolveResult
from travel_scrapping.cli import app
from travel_scrapping.config import get_settings
from travel_scrapping.db import PriceObservation, SearchRun, init_db, save_deals, session_scope
from travel_scrapping.schemas import DealCandidate, Offer
from travel_scrapping.search.providers.base import ProviderStatus
from travel_scrapping.search.providers.serpapi_google_flights import SerpApiSmokeResult


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


def test_cli_search_applies_overrides_and_sends_email(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("MAX_ROUNDTRIP_PRICE_EUR", "150")
    calls = {}

    async def fake_run_search(settings, modes, include_indicative, depart_from):
        calls["settings"] = settings
        calls["modes"] = modes
        calls["include_indicative"] = include_indicative
        calls["depart_from"] = depart_from
        return 42

    def fake_latest_deals(settings, limit=None):
        return SimpleNamespace(id=42), ["deal"]

    async def fake_send_email(settings, deals):
        calls["email_deals"] = deals
        return {"sent": True}

    monkeypatch.setattr("travel_scrapping.cli.run_search", fake_run_search)
    monkeypatch.setattr("travel_scrapping.cli.latest_deals", fake_latest_deals)
    monkeypatch.setattr("travel_scrapping.cli.send_deals_email", fake_send_email)

    result = runner.invoke(
        app,
        [
            "search",
            "--send-email",
            "--origin",
            "cdg",
            "--depart-from",
            "2026-07-01",
            "--depart-to",
            "2026-07-31",
            "--min-nights",
            "4",
            "--max-nights",
            "5",
            "--modes",
            "all",
            "--include-indicative",
        ],
    )

    assert result.exit_code == 0
    assert "run_id=42" in result.output
    assert "Étape 01 — Configuration chargée" in result.output
    assert "Origine cdg · Budget max 150 EUR · 4-5 nuits · départ du 01/07/26 au 31/07/26" in result.output
    assert "Étape 05 — Résultats affichés" in result.output
    assert '"sent": true' in result.output
    assert calls["settings"].origin_airport == "cdg"
    assert calls["settings"].search_end_date == date(2026, 7, 31)
    assert calls["settings"].min_nights == 4
    assert calls["settings"].max_nights == 5
    assert calls["settings"].include_indicative is True
    assert calls["modes"] == "all"
    assert calls["include_indicative"] is True
    assert calls["depart_from"] == date(2026, 7, 1)
    assert calls["email_deals"] == ["deal"]


def test_cli_top_prints_latest_deals(monkeypatch):
    deal = DealCandidate(
        source="test",
        origin_airport="NCE",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=49,
        operator_name="U2",
        booking_url="https://example.test",
    )
    monkeypatch.setattr("travel_scrapping.cli.latest_deals", lambda settings, limit: (SimpleNamespace(id=7), [deal]))

    result = runner.invoke(app, ["top", "--limit", "1"])

    assert result.exit_code == 0
    assert "run_id=7" in result.output
    assert "Étape 01 — Configuration chargée" in result.output
    assert "BCN 01/07/26-04/07/26 49,00 EUR" in result.output


def test_cli_airports_refresh_counts_sources(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/cli.db")
    sources = ["ourairports", "api_ninjas", "fallback", "unknown"]

    def fake_collect(session, origin):
        return ["VCE", "SVQ", "BCN", "XXX"]

    def fake_resolve(code, settings, session, force=False):
        source = sources.pop(0)
        return AirportResolveResult(
            AirportInfo(
                iata=code,
                airport_name=None,
                city=code,
                country=None,
                timezone=None,
                latitude=None,
                longitude=None,
                source=source,
            ),
            cache_hit=(code == "VCE"),
        )

    monkeypatch.setattr("travel_scrapping.cli.collect_observation_iata_codes", fake_collect)
    monkeypatch.setattr("travel_scrapping.cli.resolve_airport", fake_resolve)

    result = runner.invoke(app, ["airports-refresh", "--force"])

    assert result.exit_code == 0
    assert "total codes=4" in result.output
    assert "trouvés via cache=1" in result.output
    assert "trouvés via API=1" in result.output
    assert "fallback=1" in result.output
    assert "inconnus=1" in result.output


def test_cli_serpapi_smoke_with_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("SERPAPI_API_KEY", "secret")

    async def fake_smoke(api_key, origin, destination, depart, ret):
        return SerpApiSmokeResult(
            params={"api_key": "masked", "origin": origin, "destination": destination},
            status_code=200,
            metadata_status="Success",
            error=None,
            best_flights=1,
            other_flights=2,
            departure_tokens=3,
            booking_tokens=4,
            booking_options=5,
            debug_path="debug.json",
        )

    monkeypatch.setattr("travel_scrapping.cli.serpapi_smoke", fake_smoke)

    result = runner.invoke(
        app,
        ["serpapi-smoke", "--origin", "NCE", "--destination", "VCE", "--depart", "2026-07-30", "--return", "2026-08-02"],
    )

    assert result.exit_code == 0
    assert "statut_http=200" in result.output
    assert "best_flights=1" in result.output
    assert "json_debug=debug.json" in result.output


def test_cli_bus_commands_enabled(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("RAPIDAPI_KEY", "secret")

    class FakeFlixBusProvider:
        def __init__(self, settings):
            self.last_status_code = 200
            self.last_path = "/search"
            self.last_error = "quota"

        def status(self):
            return ProviderStatus("flixbus", enabled=True)

        async def station_search(self, query):
            return [{"id": f"{query}-1", "name": f"{query} Station", "city": query}]

        async def search_roundtrip(self, origin, destination, depart, ret):
            return [
                Offer(
                    id="offer-1",
                    transport_mode="bus",
                    provider="flixbus",
                    source="flixbus",
                    origin_code=origin,
                    origin_name="Nice",
                    destination_code=destination,
                    destination_name="Venise",
                    departure_at=datetime(2026, 7, 30, 8, tzinfo=timezone.utc),
                    return_at=datetime(2026, 8, 2, 8, tzinfo=timezone.utc),
                    nights=3,
                    price_amount=29,
                    price_currency="EUR",
                    operator_name="FlixBus",
                    duration_minutes=360,
                    booking_url="https://example.test",
                )
            ]

    monkeypatch.setattr("travel_scrapping.cli.FlixBusRapidApiProvider", FakeFlixBusProvider)

    stations = runner.invoke(app, ["bus-stations-search", "--query", "Nice"])
    smoke = runner.invoke(
        app,
        ["flixbus-smoke", "--origin", "Nice", "--destination", "Venise", "--depart", "2026-07-30", "--return", "2026-08-02"],
    )

    assert stations.exit_code == 0
    assert "Nice-1 | Nice Station | Nice" in stations.output
    assert "error=quota" in stations.output
    assert smoke.exit_code == 0
    assert "stations_origin=1" in smoke.output
    assert "offres=1" in smoke.output
    assert "link=oui" in smoke.output


def test_cli_smoke_flixbus_openapi_no_live_does_not_call_network(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("FLIXBUS_OPENAPI_ENABLED", "true")

    class FakeFlixBusOpenApiProvider:
        name = "flixbus_openapi"

        def __init__(self, settings):
            self.last_attempted = False
            self.last_status_code = None
            self.last_lookup_status_code = None
            self.last_search_status_code = None
            self.last_raw_count = 0
            self.last_normalized_count = 0
            self.last_error = None
            self.last_path = None
            self.last_public_params = {}
            self.last_city_lookups = []
            self.last_lookup_source = "none"
            self.last_lookup_ambiguous = False
            self.last_from_city_id = None
            self.last_to_city_id = None
            self.last_from_legacy_id = None
            self.last_to_legacy_id = None
            self.last_id_kind = "uuid"

        def status(self):
            return ProviderStatus("flixbus_openapi", enabled=True)

        async def search_roundtrip(self, origin, destination, depart, ret):
            self.last_attempted = True
            self.last_error = "legacy_id absent"
            return []

    monkeypatch.setattr("travel_scrapping.cli.FlixBusOpenApiProvider", FakeFlixBusOpenApiProvider)
    monkeypatch.setattr(
        "travel_scrapping.cli.gtfs_info",
        lambda: SimpleNamespace(present=False),
    )

    result = runner.invoke(app, ["smoke-flixbus-openapi"])

    assert result.exit_code == 0
    assert "provider=flixbus_openapi" in result.output
    assert "enabled=true" in result.output
    assert "attempted=true" in result.output
    assert "raw_count=0" in result.output
    assert "normalized_count=0" in result.output
    assert "params={}" in result.output


def test_cli_smoke_flixbus_openapi_live_reports_city_resolution_without_fake_offer(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("FLIXBUS_OPENAPI_ENABLED", "true")

    class FakeFlixBusOpenApiProvider:
        name = "flixbus_openapi"

        def __init__(self, settings):
            self.last_attempted = False
            self.last_status_code = 400
            self.last_lookup_status_code = 200
            self.last_search_status_code = None
            self.last_raw_count = 0
            self.last_normalized_count = 0
            self.last_error = "legacy_id absent: 'Nice' or 'Paris'"
            self.last_path = "https://global.api.flixbus.com/mobile/v1/network/autocomplete"
            self.last_public_params = {"origin": "Nice", "destination": "Paris", "lookup_source": "autocomplete"}
            self.last_lookup_source = "autocomplete"
            self.last_lookup_ambiguous = False
            self.last_from_city_id = None
            self.last_to_city_id = None
            self.last_from_legacy_id = None
            self.last_to_legacy_id = None
            self.last_id_kind = "uuid"
            self.last_city_lookups = [
                SimpleNamespace(
                    params={"q": "Nice", "lang": "fr"},
                    raw_summary="autocomplete count=0",
                    city_id=None,
                    legacy_id=None,
                    source="autocomplete",
                    ambiguous=False,
                ),
                SimpleNamespace(
                    params={"q": "Paris", "lang": "fr"},
                    raw_summary="autocomplete count=0",
                    city_id=None,
                    legacy_id=None,
                    source="autocomplete",
                    ambiguous=False,
                ),
            ]

        def status(self):
            return ProviderStatus("flixbus_openapi", enabled=True)

        async def search_roundtrip(self, origin, destination, depart, ret):
            self.last_attempted = True
            return []

    monkeypatch.setattr("travel_scrapping.cli.FlixBusOpenApiProvider", FakeFlixBusOpenApiProvider)
    monkeypatch.setattr("travel_scrapping.cli.gtfs_info", lambda: SimpleNamespace(present=False))

    result = runner.invoke(
        app,
        [
            "smoke-flixbus-openapi",
            "--from",
            "Nice",
            "--to",
            "Paris",
            "--depart",
            "2026-07-30",
            "--return",
            "2026-08-02",
        ],
    )

    assert result.exit_code == 0
    assert 'requête_ville_départ={"lang": "fr", "q": "Nice"}' in result.output
    assert "id_départ=absent" in result.output
    assert "legacy_id_départ=absent" in result.output
    assert 'requête_ville_arrivée={"lang": "fr", "q": "Paris"}' in result.output
    assert "id_arrivée=absent" in result.output
    assert "legacy_id_arrivée=absent" in result.output
    assert "id_kind=uuid" in result.output
    assert "http_status=400" in result.output
    assert "raw_count=0" in result.output
    assert "normalized_count=0" in result.output
    assert "offres=0" in result.output


def test_cli_smoke_flixbus_openapi_disabled(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("FLIXBUS_OPENAPI_ENABLED", "false")

    result = runner.invoke(app, ["smoke-flixbus-openapi"])

    assert result.exit_code == 0
    assert "provider=flixbus_openapi" in result.output
    assert "enabled=false" in result.output
    assert "attempted=false" in result.output


def test_cli_flixbus_gtfs_info_and_search(monkeypatch):
    info = SimpleNamespace(
        present=True,
        path="data/gtfs/flixbus/gtfs_generic_eu.zip",
        downloaded_at=datetime(2026, 6, 20, tzinfo=timezone.utc),
        size_bytes=123,
        files_present={"stops.txt": True, "routes.txt": False},
        stops_count=1,
        routes_count=0,
        trips_count=0,
        valid_from="20260701",
        valid_until="20260831",
        nice_examples=[{"stop_id": "nce", "stop_name": "Nice", "stop_lat": "1", "stop_lon": "2"}],
        paris_examples=[],
        error=None,
    )
    monkeypatch.setattr("travel_scrapping.cli.gtfs_info", lambda: info)
    monkeypatch.setattr("travel_scrapping.cli.search_stops", lambda query: info.nice_examples)

    diagnostic = runner.invoke(app, ["flixbus-gtfs-info"])
    search = runner.invoke(app, ["flixbus-gtfs-stop-search", "--query", "Nice"])

    assert diagnostic.exit_code == 0
    assert "stops.txt=present" in diagnostic.output
    assert "note=stop_id GTFS != legacy_id reservation" in diagnostic.output
    assert search.exit_code == 0
    assert "stop_id=nce" in search.output


def test_cli_flixbus_autocomplete_and_cache_set(monkeypatch, tmp_path):
    async def fake_autocomplete(query, lang="fr"):
        return SimpleNamespace(
            endpoint="https://global.api.flixbus.com/mobile/v1/network/autocomplete",
            params={"q": query, "limit": 50, "lang": lang},
            status_code=200,
            raw_count=1,
            ambiguous=False,
            selected={"id": "uuid", "legacy_id": "nice-legacy"},
            error=None,
            results=[
                {
                    "name": "Nice",
                    "legacy_id": "nice-legacy",
                    "id": "uuid",
                    "slug": "nice",
                    "country_code": "FR",
                }
            ],
        )

    stored = {}

    def fake_save(**kwargs):
        stored.update(kwargs)
        return {"query": kwargs["query"], "id": kwargs["id"], "legacy_id": kwargs["legacy_id"], "name": kwargs["name"]}

    monkeypatch.setattr("travel_scrapping.cli.autocomplete_city", fake_autocomplete)
    monkeypatch.setattr("travel_scrapping.cli.save_city_mapping", fake_save)

    autocomplete = runner.invoke(app, ["flixbus-autocomplete", "--query", "Nice"])
    cache = runner.invoke(
        app,
        ["flixbus-city-cache-set", "--query", "Nice", "--id", "uuid", "--legacy-id", "nice-legacy", "--name", "Nice"],
    )

    assert autocomplete.exit_code == 0
    assert "selected_id=uuid" in autocomplete.output
    assert "legacy_id=nice-legacy" in autocomplete.output
    assert cache.exit_code == 0
    assert stored["id"] == "uuid"
    assert stored["legacy_id"] == "nice-legacy"
