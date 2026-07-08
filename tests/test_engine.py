from datetime import date, datetime, timedelta, timezone

import pytest

from travel_scrapping.config import Settings
from travel_scrapping.db import Deal, PriceObservation, ProviderStatusRow, SearchRun, init_db, session_scope
from travel_scrapping.schemas import DealCandidate, Destination, Offer
from travel_scrapping.search.engine import (
    create_search_run,
    latest_deals,
    load_destinations,
    parse_modes,
    run_search,
    run_search_sync,
)
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus


class FakeProvider(FlightProvider):
    name = "fake"

    def status(self):
        return ProviderStatus("fake", enabled=True)

    async def search(self, destinations, date_pairs, *, limit):
        outbound, ret, nights = date_pairs[0]
        return [
            DealCandidate(
                source="fake",
                origin_airport="NCE",
                destination_airport="BCN",
                outbound_date=outbound,
                return_date=ret,
                nights=nights,
                total_price=20,
                is_direct=True,
            )
        ]


class DisabledProvider(FlightProvider):
    name = "disabled"

    def status(self):
        return ProviderStatus("disabled", enabled=False, warnings=["off"])

    async def search(self, destinations, date_pairs, *, limit):
        raise AssertionError("disabled provider should not search")


class RaisingProvider(FlightProvider):
    name = "raising"

    def status(self):
        return ProviderStatus("raising", enabled=True)

    async def search(self, destinations, date_pairs, *, limit):
        raise RuntimeError("secret-token boom")


class RejectedProvider(FlightProvider):
    name = "rejected"

    def status(self):
        return ProviderStatus("rejected", enabled=True)

    async def search(self, destinations, date_pairs, *, limit):
        outbound, ret, nights = date_pairs[0]
        return [
            DealCandidate(
                source="rejected",
                origin_airport="NCE",
                destination_airport="BCN",
                outbound_date=outbound,
                return_date=ret,
                nights=nights,
                total_price=200,
                is_direct=True,
                booking_url="https://example.test",
                operator_name="U2",
            )
        ]


class ErrorPayloadProvider(FlightProvider):
    name = "serpapi_google_flights_deals"

    def __init__(self, settings):
        super().__init__(settings)
        self.last_attempted = True
        self.last_ok = False
        self.last_error = "bad *** key"
        self.last_status_code = 200
        self.last_raw_count = 0
        self.last_normalized_count = 0
        self.last_public_params = {"engine": "google_flights_deals", "error": "bad *** key"}
        self.last_destination_examples = []

    def status(self):
        return ProviderStatus("serpapi_google_flights_deals", enabled=True, key_present=True)

    async def search(self, destinations, date_pairs, *, limit):
        return []


class ActionableFlightProvider(FlightProvider):
    name = "flight_ok"

    def status(self):
        return ProviderStatus("flight_ok", enabled=True)

    async def search(self, destinations, date_pairs, *, limit):
        outbound, ret, nights = date_pairs[0]
        return [
            DealCandidate(
                source="flight_ok",
                provider="flight_ok",
                transport_mode="flight",
                origin_airport="NCE",
                destination_airport="BCN",
                outbound_date=outbound,
                return_date=ret,
                nights=nights,
                total_price=20,
                is_direct=True,
                booking_url="https://example.test/flight",
                operator_name="U2",
            )
        ]


def test_load_destinations():
    destinations = load_destinations()
    assert any(d.airport == "BCN" for d in destinations)


def test_parse_modes_all_includes_flight_bus_train():
    assert parse_modes("all") == {"flight", "bus", "train"}
    assert parse_modes("flight,bus,train") == {"flight", "bus", "train"}
    assert parse_modes("flight,bus,train,all") == {"flight", "bus", "train"}
    assert parse_modes("flight,bus") == {"flight", "bus"}


def test_parse_modes_defaults_to_flight_on_empty_or_invalid():
    assert parse_modes("") == {"flight"}
    assert parse_modes(None) == {"flight"}
    assert parse_modes("boat") == {"flight"}


@pytest.mark.asyncio
async def test_run_search_flight_mode_builds_flight_provider(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=1,
    )
    monkeypatch.setattr("travel_scrapping.search.engine.build_providers", lambda settings, **kwargs: [FakeProvider(settings)])

    run_id = await run_search(settings, modes="flight")

    factory = init_db(settings)
    with session_scope(factory) as session:
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))
        run = session.get(SearchRun, run_id)

    assert run is not None
    assert run.status == "completed"
    assert [row.name for row in statuses] == ["fake"]
    assert statuses[0].attempted is False
    assert statuses[0].raw_count == 1


@pytest.mark.asyncio
async def test_run_search_all_mode_keeps_flight_provider_when_ground_disabled(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=1,
        bus_enabled=False,
        distribusion_enabled=False,
    )
    monkeypatch.setattr("travel_scrapping.search.engine.build_providers", lambda settings, **kwargs: [FakeProvider(settings)])

    run_id = await run_search(settings, modes="all")

    factory = init_db(settings)
    with session_scope(factory) as session:
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))
        run = session.get(SearchRun, run_id)

    assert run is not None
    assert run.status == "completed"
    assert [row.name for row in statuses] == ["fake", "distribusion", "comparabus", "flixbus_openapi", "flixbus"]
    assert statuses[0].raw_count == 1
    assert statuses[1].enabled is False
    assert statuses[2].enabled is False
    assert statuses[3].enabled is False


@pytest.mark.asyncio
async def test_run_search_bus_train_mode_does_not_build_flight_provider(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=1,
        bus_enabled=False,
        distribusion_enabled=False,
    )

    def fail_build(settings, **kwargs):
        raise AssertionError("flight provider should not be built")

    monkeypatch.setattr("travel_scrapping.search.engine.build_providers", fail_build)

    run_id = await run_search(settings, modes="bus,train")

    factory = init_db(settings)
    with session_scope(factory) as session:
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))
        run = session.get(SearchRun, run_id)

    assert run is not None
    assert run.status == "completed"
    assert [row.name for row in statuses] == ["distribusion", "comparabus", "flixbus_openapi", "flixbus"]


@pytest.mark.asyncio
async def test_run_search_flight_bus_keeps_flight_results_when_bus_empty(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=1,
        bus_enabled=True,
        distribusion_enabled=False,
        rapidapi_key="secret",
    )

    class EmptyBusProvider:
        name = "empty_bus"

        def __init__(self, settings):
            self.last_attempted = True
            self.last_status_code = 200
            self.last_raw_count = 0
            self.last_normalized_count = 0
            self.last_public_params = {"provider": self.name}
            self.last_destination_examples = []
            self.last_error = None

        def status(self):
            return ProviderStatus(self.name, enabled=True)

        async def search_roundtrip(self, origin, destination, depart, ret):
            return []

    monkeypatch.setattr(
        "travel_scrapping.search.engine.build_providers",
        lambda settings, **kwargs: [ActionableFlightProvider(settings)],
    )
    monkeypatch.setattr("travel_scrapping.search.engine.ComparabusProvider", EmptyBusProvider)
    monkeypatch.setattr("travel_scrapping.search.engine.FlixBusOpenApiProvider", EmptyBusProvider)
    monkeypatch.setattr("travel_scrapping.search.engine.FlixBusRapidApiProvider", EmptyBusProvider)

    run_id = await run_search(settings, modes="flight,bus")

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        deals = list(session.query(Deal).order_by(Deal.id))
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))

    assert run is not None
    assert run.accepted_count == 1
    assert [deal.transport_mode for deal in deals] == ["flight"]
    assert [row.name for row in statuses] == ["flight_ok", "distribusion", "empty_bus", "empty_bus", "empty_bus"]
    assert statuses[0].accepted_count == 1
    assert statuses[2].raw_count == 0


@pytest.mark.asyncio
async def test_run_search_train_mode_saves_distribusion_candidates(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=1,
        distribusion_enabled=True,
        distribusion_api_key="secret",
        distribusion_base_url="https://example.test",
        bus_enabled=False,
    )
    monkeypatch.setattr(
        "travel_scrapping.search.engine.load_destinations",
        lambda: [Destination("PAR", "Paris", "FR")],
    )

    class FakeDistribusionProvider:
        name = "distribusion"

        def __init__(self, settings):
            self.last_attempted = True
            self.last_ok = True
            self.last_status_code = 200
            self.last_raw_count = 1
            self.last_normalized_count = 1
            self.last_public_params = {"provider": "distribusion"}
            self.last_destination_examples = ["Paris"]

        def status(self):
            return ProviderStatus("distribusion", enabled=True, key_present=True)

        async def search(self, destinations, date_pairs, *, limit):
            outbound, ret, nights = date_pairs[0]
            return [
                DealCandidate(
                    source="distribusion",
                    provider="distribusion",
                    transport_mode="train",
                    origin_airport="NCE",
                    destination_airport="PAR",
                    destination_city="Paris",
                    outbound_date=outbound,
                    return_date=ret,
                    nights=nights,
                    total_price=29,
                    booking_url="https://example.test/train",
                    operator_name="SNCF",
                    duration_minutes=360,
                    stops_count=0,
                    confidence="high",
                )
            ]

    monkeypatch.setattr("travel_scrapping.search.engine.DistribusionGroundTransportProvider", FakeDistribusionProvider)

    run_id = await run_search(settings, providers=[], modes="train")

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        deal = session.query(Deal).one()
        status = session.query(ProviderStatusRow).one()

    assert run is not None
    assert run.accepted_count == 1
    assert deal.transport_mode == "train"
    assert deal.operator_name == "SNCF"
    assert deal.provider == "distribusion"
    assert status.name == "distribusion"
    assert status.accepted_count == 1
    assert status.raw_count == 1


def test_create_search_run_and_latest_empty(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")

    assert latest_deals(settings) == (None, [])
    run_id = create_search_run(settings)

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        assert run is not None
        assert run.status == "pending"


@pytest.mark.asyncio
async def test_run_search_persists(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=5,
    )
    run_id = await run_search(settings, providers=[FakeProvider(settings)])
    assert run_id == 1
    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        assert run is not None
        assert run.accepted_count == session.query(PriceObservation).count()


@pytest.mark.asyncio
async def test_run_search_records_disabled_errors_and_rejections(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=5,
    )

    run_id = await run_search(settings, providers=[DisabledProvider(settings), RaisingProvider(settings), RejectedProvider(settings)])

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))

    assert run is not None
    assert run.status == "completed"
    assert run.accepted_count == 0
    assert run.rejected_count == 2
    assert session.query(PriceObservation).count() == 0
    assert [(row.name, row.enabled, row.ok, row.attempted, row.accepted_count, row.rejected_count) for row in statuses] == [
        ("disabled", False, True, False, 0, 0),
        ("raising", True, False, True, 0, 1),
        ("rejected", True, True, False, 0, 1),
    ]
    assert statuses[1].error == "secret-token boom"
    assert statuses[2].raw_count == 1
    assert statuses[2].normalized_count == 1
    assert statuses[2].main_rejection_reason == "over budget (1)"


@pytest.mark.asyncio
async def test_run_search_persists_provider_payload_error_status(tmp_path):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        date_to=date.today().replace(year=date.today().year + 1),
        top_results_limit=5,
    )

    run_id = await run_search(settings, providers=[ErrorPayloadProvider(settings)])

    factory = init_db(settings)
    with session_scope(factory) as session:
        status = session.query(ProviderStatusRow).filter_by(run_id=run_id, name="serpapi_google_flights_deals").one()

    assert status.ok is False
    assert status.error == "bad *** key"
    assert status.http_status == 200
    assert "api_key" not in status.request_params_json


@pytest.mark.asyncio
async def test_run_search_marks_existing_run_failed_when_missing_provider_file(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    run_id = create_search_run(settings)
    monkeypatch.setattr("travel_scrapping.search.engine.load_destinations", lambda: (_ for _ in ()).throw(RuntimeError("bad file")))

    assert await run_search(settings, run_id=run_id) == run_id

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)

    assert run is not None
    assert run.status == "failed"
    assert "bad file" in run.warnings_json


@pytest.mark.asyncio
async def test_run_search_bus_records_last_error_and_rejected_offer(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        search_start_date=date.today() + timedelta(days=1),
        date_to=date.today().replace(year=date.today().year + 1),
        rapidapi_key="secret",
        top_results_limit=1,
    )
    monkeypatch.setattr(
        "travel_scrapping.search.engine.load_destinations",
        lambda: [Destination("VCE", "Venise", "IT")],
    )

    class FakeBusProvider:
        name = "flixbus"

        def __init__(self, settings):
            self.last_error = "quota secret-token exceeded"
            self.last_status_code = 429
            self.last_path = "/search"

        def status(self):
            return ProviderStatus("flixbus", enabled=True)

        async def search_roundtrip(self, origin, destination, depart, ret):
            departure_at = datetime.combine(date.today() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            return_at = departure_at + timedelta(days=3)
            return [
                Offer(
                    id="bus-1",
                    transport_mode="bus",
                    provider="flixbus",
                    source="flixbus",
                    origin_code=origin,
                    origin_name=origin,
                    destination_code=destination,
                    destination_name=destination,
                    departure_at=departure_at,
                    return_at=return_at,
                    nights=3,
                    price_amount=None,
                    price_currency="EUR",
                    operator_name="FlixBus",
                    booking_url=None,
                )
            ]

    class DisabledBusProvider:
        name = "flixbus_openapi"

        def __init__(self, settings):
            self.last_error = None
            self.last_status_code = None
            self.last_path = None

        def status(self):
            return ProviderStatus("flixbus_openapi", enabled=False, warnings=["disabled for test"])

        async def search_roundtrip(self, origin, destination, depart, ret):
            return []

    monkeypatch.setattr("travel_scrapping.search.engine.FlixBusOpenApiProvider", DisabledBusProvider)
    monkeypatch.setattr("travel_scrapping.search.engine.ComparabusProvider", DisabledBusProvider)
    monkeypatch.setattr("travel_scrapping.search.engine.FlixBusRapidApiProvider", FakeBusProvider)

    run_id = await run_search(settings, providers=[], modes="bus")

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))

    assert run is not None
    assert run.accepted_count == 0
    assert run.rejected_count == 1
    assert [(row.name, row.enabled, row.attempted) for row in statuses[:1]] == [
        ("distribusion", False, False)
    ]
    assert len(statuses) == 4
    assert statuses[-1].ok is False
    assert statuses[-1].error == "quota secret-token exceeded"
    assert statuses[-1].attempted is True
    assert statuses[-1].http_status == 429
    assert statuses[-1].raw_count == 1
    assert statuses[-1].normalized_count == 1
    assert statuses[-1].rejected_count == 1
    assert statuses[-1].main_rejection_reason == "invalid price (1)"


@pytest.mark.asyncio
async def test_run_search_train_records_disabled_distribusion_without_network(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        date_to=date.today().replace(year=date.today().year + 1),
    )
    monkeypatch.setattr(
        "travel_scrapping.search.engine.load_destinations",
        lambda: [Destination("PAR", "Paris", "FR")],
    )

    run_id = await run_search(settings, providers=[], modes="train")

    factory = init_db(settings)
    with session_scope(factory) as session:
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))
        run = session.get(SearchRun, run_id)

    assert run is not None
    assert run.status == "completed"
    assert run.accepted_count == 0
    assert [(row.name, row.enabled, row.key_present, row.attempted) for row in statuses] == [
        ("distribusion", False, False, False)
    ]
    assert "DISTRIBUSION credentials missing" in statuses[0].warnings_json


def test_run_search_sync_returns_run_id(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        date_to=date.today().replace(year=date.today().year + 1),
    )
    monkeypatch.setattr("travel_scrapping.search.engine.load_destinations", lambda: [Destination("BCN", "Barcelone", "ES")])

    run_id = run_search_sync(settings, depart_from=date.today(), modes="flight")

    assert run_id == 1
