from datetime import date

import pytest
import respx
from httpx import Response

from travel_scrapping.config import Settings
from travel_scrapping.schemas import Destination
from travel_scrapping.search.providers.serpapi_google_flights import (
    SerpApiGoogleFlightsProvider,
    count_tokens,
    parse_serpapi_payload,
    public_params,
    serpapi_smoke,
)


def test_provider_missing_key_disabled():
    provider = SerpApiGoogleFlightsProvider(Settings(_env_file=None, serpapi_api_key=""))
    assert not provider.status().enabled


def test_parse_serpapi_payload():
    deals = parse_serpapi_payload(
        {
            "best_flights": [
                {
                    "price": 30,
                    "destination_airport": "BCN",
                    "outbound_date": "2026-07-01",
                    "return_date": "2026-07-04",
                    "airline": "easyJet",
                    "booking_options": [{"link": "https://example.test/book"}],
                }
            ]
        },
        origin="NCE",
    )
    assert len(deals) == 1
    assert deals[0].total_price == 30
    assert deals[0].actionable is True


def test_parse_serpapi_rejects_missing_airline_or_link_from_main_results():
    deals = parse_serpapi_payload(
        {
            "best_flights": [
                {"price": 30, "destination_airport": "BCN", "outbound_date": "2026-07-01", "return_date": "2026-07-04"},
                {
                    "price": 30,
                    "destination_airport": "BCN",
                    "outbound_date": "2026-07-01",
                    "return_date": "2026-07-04",
                    "airline": "easyJet",
                },
            ]
        },
        origin="NCE",
    )
    assert [deal.actionable for deal in deals] == [False, False]


def test_count_tokens_and_public_params():
    payload = {
        "best_flights": [
            {
                "departure_token": "dep",
                "booking_token": "book",
                "booking_options": [{"link": "https://example.test"}],
            }
        ]
    }
    assert count_tokens(payload) == (1, 1, 1)
    assert public_params({"api_key": "secret", "engine": "google_flights"})["api_key"] == "***"


@pytest.mark.asyncio
@respx.mock
async def test_serpapi_search_mocked():
    respx.get("https://serpapi.com/search.json").mock(
        return_value=Response(
            200,
            json={
                "best_flights": [
                    {
                        "price": 30,
                        "destination_airport": "BCN",
                        "outbound_date": "2026-07-01",
                        "return_date": "2026-07-04",
                        "airline": "easyJet",
                        "booking_options": [{"link": "https://example.test/book"}],
                    }
                ]
            },
        )
    )
    provider = SerpApiGoogleFlightsProvider(Settings(_env_file=None, serpapi_api_key="secret"))
    deals = await provider.search([Destination("BCN", "Barcelona", "Spain")], [(date(2026, 7, 1), date(2026, 7, 4), 3)], limit=1)
    assert deals[0].destination_airport == "BCN"


@pytest.mark.asyncio
@respx.mock
async def test_serpapi_smoke_mocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    respx.get("https://serpapi.com/search.json").mock(
        side_effect=[
            Response(
                200,
                json={
                    "search_metadata": {"status": "Success"},
                    "best_flights": [],
                    "other_flights": [{"departure_token": "dep"}],
                },
            ),
            Response(200, json={"other_flights": [{"booking_token": "book"}]}),
            Response(200, json={"booking_options": [{"link": "https://example.test/book"}]}),
        ]
    )
    result = await serpapi_smoke(api_key="secret", origin="NCE", destination="VCE", depart=date(2026, 7, 30), ret=date(2026, 8, 2))
    assert result.status_code == 200
    assert result.metadata_status == "Success"
    assert result.departure_tokens == 1
    assert result.booking_tokens == 1
    assert result.booking_options == 1
    assert result.debug_path is not None
