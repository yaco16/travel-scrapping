from datetime import date

import pytest
import respx
from httpx import Response

from travel_scrapping.config import Settings
from travel_scrapping.schemas import Destination
from travel_scrapping.search.providers.serpapi_google_flights import (
    SerpApiGoogleFlightDealsProvider,
    SerpApiGoogleFlightsProvider,
    count_tokens,
    parse_google_flight_deals_payload,
    parse_serpapi_payload,
    public_params,
    serpapi_deals_params,
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


def test_serpapi_deals_params_match_google_flight_deals_request():
    params = serpapi_deals_params(
        api_key="secret",
        origin="NCE",
        outbound_start=date(2026, 7, 1),
        outbound_end=date(2026, 8, 31),
        min_nights=1,
        max_nights=7,
        max_price=150,
        max_stops=1,
    )
    assert params["engine"] == "google_flights_deals"
    assert params["departure_id"] == "NCE"
    assert params["outbound_date"] == "2026-07-01,2026-08-31"
    assert params["trip_length"] == "1,7"
    assert params["max_price"] == "150"
    assert params["stops"] == "2"
    assert params["currency"] == "EUR"
    assert params["gl"] == "fr"
    assert params["hl"] == "fr"
    assert params["adults"] == 1
    assert "return_date" not in params
    assert "arrival_id" not in params


def test_parse_google_flight_deals_fixture():
    deals = parse_google_flight_deals_payload(
        {
            "currency": "EUR",
            "destinations": [
                {
                    "destination_airport": {"id": "SVQ"},
                    "destination_city": "Séville",
                    "country": "Espagne",
                    "price": "50 €",
                    "average_price": "90 €",
                    "discount_percent": "44%",
                    "outbound_date": "2026-07-16",
                    "return_date": "2026-07-23",
                    "duration": 140,
                    "stops": 0,
                    "airline": "easyJet",
                    "google_flights_link": "https://example.test/svq",
                    "image": "https://example.test/svq.jpg",
                },
                {
                    "destination_airport": "STN",
                    "destination_city": "Londres",
                    "country": "Royaume-Uni",
                    "price": 44,
                    "outbound_date": "2026-07-21",
                    "return_date": "2026-07-28",
                    "stops": 1,
                },
                {
                    "destination_airport": "FCO",
                    "destination_city": "Rome",
                    "country": "Italie",
                    "price": 50,
                    "outbound_date": "2026-08-28",
                    "return_date": "2026-08-31",
                    "stops": 0,
                },
            ],
        },
        origin="NCE",
    )
    assert [deal.destination_airport for deal in deals] == ["SVQ", "STN", "FCO"]
    assert [deal.destination_city for deal in deals] == ["Séville", "Londres", "Rome"]
    assert deals[0].destination_country == "Espagne"
    assert deals[0].total_price == 50
    assert deals[0].average_price == 90
    assert deals[0].discount_percent == 44
    assert deals[0].image_url == "https://example.test/svq.jpg"
    assert deals[0].nights == 7
    assert deals[1].stops_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_google_flight_deals_provider_search_uses_flexible_anywhere_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    route = respx.get("https://serpapi.com/search.json").mock(
        return_value=Response(
            200,
            json={
                "destinations": [
                    {
                        "destination_airport": "SVQ",
                        "destination_city": "Séville",
                        "price": 50,
                        "outbound_date": "2026-07-16",
                        "return_date": "2026-07-23",
                    }
                ]
            },
        )
    )
    provider = SerpApiGoogleFlightDealsProvider(Settings(_env_file=None, serpapi_api_key="secret"))
    deals = await provider.search([], [], limit=10)
    sent = route.calls[0].request.url.params
    assert sent["engine"] == "google_flights_deals"
    assert sent["departure_id"] == "NCE"
    assert sent["outbound_date"] == "2026-07-01,2026-08-31"
    assert sent["trip_length"] == "1,7"
    assert sent["max_price"] == "150"
    assert sent["stops"] == "2"
    assert "return_date" not in sent
    assert "arrival_id" not in sent
    assert deals[0].destination_city == "Séville"
    assert provider.last_raw_count == 1
    assert provider.last_normalized_count == 1


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
