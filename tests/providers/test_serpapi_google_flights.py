from datetime import date

import pytest
import respx
from httpx import Response

from travel_scrapping.config import Settings
from travel_scrapping.schemas import Destination
from travel_scrapping.search.providers.serpapi_google_flights import (
    SerpApiGoogleFlightsProvider,
    parse_serpapi_payload,
)


def test_provider_missing_key_disabled():
    provider = SerpApiGoogleFlightsProvider(Settings(_env_file=None, serpapi_api_key=""))
    assert not provider.status().enabled


def test_parse_serpapi_payload():
    deals = parse_serpapi_payload(
        {"best_flights": [{"price": 30, "destination_airport": "BCN", "outbound_date": "2026-07-01", "return_date": "2026-07-04"}]},
        origin="NCE",
    )
    assert len(deals) == 1
    assert deals[0].total_price == 30


@pytest.mark.asyncio
@respx.mock
async def test_serpapi_search_mocked():
    respx.get("https://serpapi.com/search.json").mock(
        return_value=Response(
            200,
            json={
                "best_flights": [
                    {"price": 30, "destination_airport": "BCN", "outbound_date": "2026-07-01", "return_date": "2026-07-04"}
                ]
            },
        )
    )
    provider = SerpApiGoogleFlightsProvider(Settings(_env_file=None, serpapi_api_key="secret"))
    deals = await provider.search([Destination("BCN", "Barcelona", "Spain")], [(date(2026, 7, 1), date(2026, 7, 4), 3)], limit=1)
    assert deals[0].destination_airport == "BCN"
