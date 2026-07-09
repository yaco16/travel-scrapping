from __future__ import annotations

from datetime import date

import pytest
import respx
from httpx import Response

from travel_scrapping.search.providers.ryanair import RYANAIR_MAX_LIMIT, RyanairProvider, _parse_fares


def _settings(**kwargs):
    from travel_scrapping.config import Settings
    base: dict = dict(  # type: ignore[assignment]
        _env_file=None,
        origin_airport="NCE",
        search_start_date=date(2026, 7, 1),
        search_end_date=date(2026, 8, 31),
        min_nights=1,
        max_nights=7,
        max_roundtrip_price_eur=150.0,
        ryanair_enabled=True,
    )
    base.update(kwargs)
    return Settings(**base)  # type: ignore[call-arg]


def _fare(dest="BCN", out="2026-07-15T06:00:00", ret="2026-07-22T18:00:00", price=101.98):
    return {
        "outbound": {
            "departureAirport": {"iataCode": "NCE", "name": "Nice"},
            "arrivalAirport": {"iataCode": dest, "name": "Barcelona", "countryName": "Spain"},
            "departureDate": out,
        },
        "inbound": {
            "departureAirport": {"iataCode": dest},
            "arrivalAirport": {"iataCode": "NCE"},
            "departureDate": ret,
        },
        "summary": {
            "price": {"value": price, "currencyCode": "EUR"},
        },
    }


def test_parse_fares_basic():
    deals = _parse_fares([_fare()], origin="NCE")
    assert len(deals) == 1
    d = deals[0]
    assert d.destination_airport == "BCN"
    assert d.total_price == 101.98
    assert d.currency == "EUR"
    assert d.source == "ryanair"
    assert d.origin_airport == "NCE"
    assert d.outbound_date == date(2026, 7, 15)
    assert d.return_date == date(2026, 7, 22)
    assert d.nights == 7
    assert d.booking_url is not None
    assert "NCE" in d.booking_url
    assert "BCN" in d.booking_url
    assert "adults=1" in d.booking_url
    assert d.confidence == "high"
    assert d.is_direct is True


def test_parse_fares_missing_dest():
    fare = _fare()
    fare["outbound"]["arrivalAirport"] = {}
    deals = _parse_fares([fare], origin="NCE")
    assert deals == []


def test_parse_fares_missing_price():
    fare = _fare()
    fare["summary"] = {}
    deals = _parse_fares([fare], origin="NCE")
    assert deals == []


def test_parse_fares_missing_date():
    fare = _fare(out="", ret="2026-07-22T18:00:00")
    deals = _parse_fares([fare], origin="NCE")
    assert deals == []


def test_parse_fares_multiple():
    fares = [_fare("BCN", price=80), _fare("MAD", price=120), _fare("LIS", price=200)]
    deals = _parse_fares(fares, origin="NCE")
    assert len(deals) == 3
    assert {d.destination_airport for d in deals} == {"BCN", "MAD", "LIS"}


def test_status_enabled():
    s = _settings(ryanair_enabled=True)
    p = RyanairProvider(s)
    assert p.status().enabled is True


def test_status_disabled():
    s = _settings(ryanair_enabled=False)
    p = RyanairProvider(s)
    assert p.status().enabled is False


@pytest.mark.asyncio
@respx.mock
async def test_search_caps_requested_limit_to_ryanair_max():
    route = respx.get("https://services-api.ryanair.com/farfnd/v4/roundTripFares").mock(
        return_value=Response(200, json={"fares": []})
    )
    s = _settings(top_results_limit=50)
    provider = RyanairProvider(s)

    await provider.search([], [], limit=50)

    assert route.calls.last.request.url.params["limit"] == str(RYANAIR_MAX_LIMIT)


@pytest.mark.asyncio
@respx.mock
async def test_search_uses_variable_filters_but_single_passenger():
    route = respx.get("https://services-api.ryanair.com/farfnd/v4/roundTripFares").mock(
        return_value=Response(200, json={"fares": []})
    )
    s = _settings(
        search_start_date=date(2026, 9, 1),
        search_end_date=date(2026, 10, 1),
        min_nights=2,
        max_nights=5,
        max_roundtrip_price_eur=123,
        default_currency="GBP",
        default_locale="en-GB",
        adults=4,
    )
    provider = RyanairProvider(s)

    await provider.search([], [], limit=7)

    params = route.calls.last.request.url.params
    assert params["departureAirportIataCode"] == "NCE"
    assert params["outboundDepartureDateFrom"] == "2026-09-01"
    assert params["outboundDepartureDateTo"] == "2026-10-01"
    assert params["durationFrom"] == "2"
    assert params["durationTo"] == "5"
    assert params["maxPrice"] == "123"
    assert params["currency"] == "GBP"
    assert params["language"] == "en"
    assert "adults" not in params
