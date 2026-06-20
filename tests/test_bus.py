from travel_scrapping.bus.parser import parse_trips
from travel_scrapping.bus.stations import parse_stations
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider
from travel_scrapping.config import Settings


def test_flixbus_station_parser_fixture():
    stations = parse_stations({"data": [{"id": "nice-1", "name": "Nice Airport", "city_name": "Nice"}]})
    assert stations == [
        {"id": "nice-1", "name": "Nice Airport", "city": "Nice", "country": None, "raw": stations[0]["raw"]}
    ]


def test_flixbus_trips_parser_accepts_actionable_offer():
    offers = parse_trips(
        {
            "trips": [
                {
                    "id": "trip-1",
                    "departure_at": "2026-07-30T08:00:00+00:00",
                    "arrival_at": "2026-07-30T14:30:00+00:00",
                    "price": {"amount": 29.99},
                    "currency": "EUR",
                    "operator": {"name": "FlixBus"},
                    "booking_url": "https://example.test/flixbus",
                }
            ]
        },
        origin="Nice",
        destination="Venise",
    )
    assert offers[0].actionable is True
    assert offers[0].operator_name == "FlixBus"
    assert offers[0].duration_minutes == 390


def test_flixbus_offer_without_price_or_link_rejected():
    offers = parse_trips(
        {
            "trips": [
                {
                    "departure_at": "2026-07-30T08:00:00+00:00",
                    "arrival_at": "2026-07-30T14:30:00+00:00",
                    "operator": "FlixBus",
                }
            ]
        },
        origin="Nice",
        destination="Venise",
    )
    assert offers[0].actionable is False
    assert "price_amount" in offers[0].missing_fields
    assert "booking_url" in offers[0].missing_fields


def test_flixbus_provider_status_and_mocked_search(monkeypatch):
    provider = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="secret", flixbus_rapidapi_host="host"))
    assert provider.status().enabled
    assert provider.headers()["X-RapidAPI-Key"] == "secret"
    assert provider.headers()["X-RapidAPI-Host"] == "host"

    async def fake_get_first_ok(paths, params):
        if "query" in params:
            return 200, {"data": [{"id": "nice-1", "name": "Nice"}]}, paths[0]
        return (
            200,
            {
                "trips": [
                    {
                        "departure_at": "2026-07-30T08:00:00+00:00",
                        "arrival_at": "2026-07-30T10:00:00+00:00",
                        "price": 19,
                        "currency": "EUR",
                        "operator": "FlixBus",
                        "url": "https://example.test/book",
                    }
                ]
            },
            paths[0],
        )

    monkeypatch.setattr(provider, "_get_first_ok", fake_get_first_ok)
    import asyncio

    assert asyncio.run(provider.station_search("Nice"))[0]["id"] == "nice-1"
    offers = asyncio.run(provider.search_roundtrip("Nice", "Venise", "2026-07-30", "2026-08-02"))
    assert offers[0].actionable is True
