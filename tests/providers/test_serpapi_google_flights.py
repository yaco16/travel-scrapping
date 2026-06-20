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


class FakeSerpApiResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeAsyncClient:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params):
        self.calls.append({"url": url, "params": dict(params)})
        return FakeSerpApiResponse(self.payloads.pop(0))


def deal_payload(code="SVQ", city="Séville", price=50):
    return {
        "deals": [
            {
                "arrival_airport_code": code,
                "destination_city": city,
                "price": price,
                "outbound_date": "2026-07-16",
                "return_date": "2026-07-23",
                "airline": "easyJet",
                "google_flights_link": f"https://example.test/{code.lower()}",
            }
        ],
        "search_metadata": {"status": "Success"},
    }


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
    assert "api_key" not in public_params({"api_key": "secret", "engine": "google_flights"})


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
            "deals": [
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
async def test_google_flight_deals_provider_search_uses_strict_deals_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    route = respx.get("https://serpapi.com/search.json").mock(
        return_value=Response(
            200,
            json={
                "deals": [
                    {
                        "destination_airport": "SVQ",
                        "destination_city": "Séville",
                        "price": 50,
                        "outbound_date": "2026-07-16",
                        "return_date": "2026-07-23",
                        "airline": "easyJet",
                        "google_flights_link": "https://example.test/svq",
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
async def test_google_flight_deals_provider_single_request_no_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeAsyncClient([deal_payload()])
    monkeypatch.setattr(
        "travel_scrapping.search.providers.serpapi_google_flights.httpx.AsyncClient",
        lambda timeout: client,
    )
    provider = SerpApiGoogleFlightDealsProvider(Settings(_env_file=None, serpapi_api_key="secret"))

    deals = await provider.search([], [], limit=10)

    assert len(client.calls) == 1
    assert deals[0].destination_airport == "SVQ"
    assert "api_key" not in provider.last_public_params
    assert "fallback_attempts" not in provider.last_public_params
    assert "return_date" not in provider.last_public_params
    assert provider.last_public_params["trip_length"] == "1,7"


@pytest.mark.asyncio
async def test_google_flight_deals_provider_does_not_fallback_when_deals_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeAsyncClient([{"search_metadata": {"status": "Success"}, "departure_informations": []}])
    monkeypatch.setattr(
        "travel_scrapping.search.providers.serpapi_google_flights.httpx.AsyncClient",
        lambda timeout: client,
    )
    provider = SerpApiGoogleFlightDealsProvider(Settings(_env_file=None, serpapi_api_key="secret"))

    deals = await provider.search([], [], limit=10)

    assert len(client.calls) == 1
    assert deals == []
    assert provider.last_raw_count == 0
    assert provider.last_public_params["diagnostic"] == "SerpApi appelé, HTTP 200, payload sans clé deals exploitable."


@pytest.mark.asyncio
async def test_google_flight_deals_provider_empty_payload_diagnostic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeAsyncClient([{"search_metadata": {"status": "Success"}}])
    monkeypatch.setattr(
        "travel_scrapping.search.providers.serpapi_google_flights.httpx.AsyncClient",
        lambda timeout: client,
    )
    provider = SerpApiGoogleFlightDealsProvider(Settings(_env_file=None, serpapi_api_key="secret"))

    deals = await provider.search([], [], limit=10)

    assert deals == []
    assert len(client.calls) == 1
    assert provider.last_raw_count == 0
    assert provider.last_public_params["diagnostic"] == "SerpApi appelé, HTTP 200, payload sans clé deals exploitable."
    assert provider.last_public_params["payload_diagnostic"]["top_level_keys"] == ["search_metadata"]


@pytest.mark.asyncio
async def test_google_flight_deals_provider_http_200_error_sets_error_and_scrubs_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = FakeAsyncClient([
        {"search_metadata": {"status": "Success"}, "error": "bad api_key secret value"},
    ])
    monkeypatch.setattr(
        "travel_scrapping.search.providers.serpapi_google_flights.httpx.AsyncClient",
        lambda timeout: client,
    )
    provider = SerpApiGoogleFlightDealsProvider(Settings(_env_file=None, serpapi_api_key="secret"))

    deals = await provider.search([], [], limit=10)

    assert deals == []
    assert provider.last_ok is False
    assert provider.last_error == "bad *** secret value"
    dumped = str(provider.last_public_params)
    assert "api_key" not in dumped
    assert provider.last_public_params["payload_diagnostic"]["error"] == "bad *** secret value"


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
