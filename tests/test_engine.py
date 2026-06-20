from datetime import date, datetime, timezone

import pytest

from travel_scrapping.config import Settings
from travel_scrapping.db import PriceObservation, ProviderStatusRow, SearchRun, init_db, session_scope
from travel_scrapping.schemas import DealCandidate, Destination, Offer
from travel_scrapping.search.engine import create_search_run, latest_deals, load_destinations, run_search, run_search_sync
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


def test_load_destinations():
    destinations = load_destinations()
    assert any(d.airport == "BCN" for d in destinations)


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
    assert [(row.name, row.enabled, row.ok) for row in statuses] == [
        ("disabled", False, True),
        ("raising", True, True),
        ("raising", True, False),
        ("rejected", True, True),
    ]
    assert statuses[2].error == "secret-token boom"


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

        def status(self):
            return ProviderStatus("flixbus", enabled=True)

        async def search_roundtrip(self, origin, destination, depart, ret):
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
                    departure_at=datetime(2026, 7, 1, 8, tzinfo=timezone.utc),
                    return_at=datetime(2026, 7, 4, 8, tzinfo=timezone.utc),
                    nights=3,
                    price_amount=None,
                    price_currency="EUR",
                    operator_name="FlixBus",
                    booking_url=None,
                )
            ]

    monkeypatch.setattr("travel_scrapping.search.engine.FlixBusRapidApiProvider", FakeBusProvider)

    run_id = await run_search(settings, providers=[], modes="bus")

    factory = init_db(settings)
    with session_scope(factory) as session:
        run = session.get(SearchRun, run_id)
        statuses = list(session.query(ProviderStatusRow).order_by(ProviderStatusRow.id))

    assert run is not None
    assert run.accepted_count == 0
    assert run.rejected_count == 1
    assert len(statuses) == 2
    assert statuses[-1].ok is False
    assert statuses[-1].error == "quota secret-token exceeded"


def test_run_search_sync_returns_run_id(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        date_to=date.today().replace(year=date.today().year + 1),
    )
    monkeypatch.setattr("travel_scrapping.search.engine.load_destinations", lambda: [Destination("BCN", "Barcelone", "ES")])

    run_id = run_search_sync(settings, depart_from=date.today(), modes="flight")

    assert run_id == 1
