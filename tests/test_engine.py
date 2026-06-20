from datetime import date

import pytest

from travel_scrapping.config import Settings
from travel_scrapping.db import PriceObservation, SearchRun, init_db, session_scope
from travel_scrapping.schemas import DealCandidate
from travel_scrapping.search.engine import load_destinations, run_search
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


def test_load_destinations():
    destinations = load_destinations()
    assert any(d.airport == "BCN" for d in destinations)


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
