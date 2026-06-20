import pytest

from travel_scrapping.bus.parser import parse_trips
from travel_scrapping.bus.stations import parse_stations
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider, _payload_error, save_bus_debug
from travel_scrapping.config import Settings
from travel_scrapping.search.providers.playwright_probe import PlaywrightProbeProvider


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
    provider = FlixBusRapidApiProvider(
        Settings(_env_file=None, rapidapi_key="secret", flixbus_rapidapi_host="host", flixbus_debug_save=False)
    )
    assert provider.status().enabled
    assert provider.headers()["X-RapidAPI-Key"] == "secret"
    assert provider.headers()["X-RapidAPI-Host"] == "host"
    default_host_provider = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="secret"))
    assert default_host_provider.headers()["X-RapidAPI-Host"] == "flixbus2.p.rapidapi.com"

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


def test_flixbus_status_disabled_states():
    assert not FlixBusRapidApiProvider(Settings(_env_file=None, bus_enabled=False, rapidapi_key="x")).status().enabled
    missing = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="")).status()
    assert missing.enabled is False
    assert missing.warnings == ["RAPIDAPI_KEY missing"]


def test_payload_error_and_debug_scrubs_secret(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert _payload_error([]) is None
    assert _payload_error({"message": "x" * 600}) == "x" * 500
    assert _payload_error({"error": "bad"}) == "bad"
    assert _payload_error({}) is None

    path = save_bus_debug({"token": "secret", "nested": {"api_key": "hidden"}}, prefix="flixbus-test")
    content = (tmp_path / path).read_text(encoding="utf-8")
    assert "secret" not in content
    assert "hidden" not in content


@pytest.mark.asyncio
async def test_get_first_ok_skips_500_and_records_payload_error(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = "plain error"

        def json(self):
            if isinstance(self._payload, Exception):
                raise self._payload
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            if url.endswith("/bad"):
                return FakeResponse(503, {"message": "retry"})
            return FakeResponse(403, ValueError("not json"))

    monkeypatch.setattr("travel_scrapping.bus.flixbus_rapidapi.httpx.AsyncClient", lambda timeout: FakeClient())
    provider = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="secret"))

    status, payload, path = await provider._get_first_ok(("/bad", "/forbidden"), {"q": "Nice"})

    assert status == 403
    assert payload == {"error": "plain error"}
    assert path == "/forbidden"
    assert provider.last_status_code == 403
    assert provider.last_path == "/forbidden"
    assert provider.last_error == "plain error"


@pytest.mark.asyncio
async def test_get_first_ok_all_server_errors_returns_last_payload(monkeypatch):
    class FakeResponse:
        status_code = 503
        text = "server"

        def json(self):
            return {"message": "server down"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            return FakeResponse()

    monkeypatch.setattr("travel_scrapping.bus.flixbus_rapidapi.httpx.AsyncClient", lambda timeout: FakeClient())
    provider = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="secret"))

    status, payload, path = await provider._get_first_ok(("/one", "/two"), {})

    assert status == 503
    assert payload == {"error": "no endpoint returned usable response"}
    assert path == "/two"
    assert provider.last_error == "no endpoint returned usable response"


@pytest.mark.asyncio
async def test_flixbus_search_returns_empty_on_http_error_and_saves_debug(monkeypatch):
    calls = []
    provider = FlixBusRapidApiProvider(Settings(_env_file=None, rapidapi_key="secret", flixbus_debug_save=True))

    async def fake_get_first_ok(paths, params):
        return 429, {"message": "Too many requests"}, paths[0]

    def fake_save(payload, *, prefix):
        calls.append((payload, prefix))
        return "debug.json"

    monkeypatch.setattr(provider, "_get_first_ok", fake_get_first_ok)
    monkeypatch.setattr("travel_scrapping.bus.flixbus_rapidapi.save_bus_debug", fake_save)

    assert await provider.station_search("Nice") == []
    assert await provider.search_roundtrip("Nice", "Venise", "2026-07-30", "2026-08-02") == []
    assert calls == [
        ({"message": "Too many requests"}, "flixbus-stations"),
        ({"message": "Too many requests"}, "flixbus-search"),
    ]


@pytest.mark.asyncio
async def test_playwright_probe_status_and_empty_search():
    disabled = PlaywrightProbeProvider(Settings(_env_file=None, playwright_enabled=False, scraping_enabled=True))
    assert disabled.status().warnings == ["Playwright scraping disabled"]
    enabled = PlaywrightProbeProvider(Settings(_env_file=None, playwright_enabled=True, scraping_enabled=True))
    status = enabled.status()
    assert status.enabled is False
    assert "Safe probe skeleton" in status.warnings[0]
    assert await enabled.search([], [], limit=1) == []
