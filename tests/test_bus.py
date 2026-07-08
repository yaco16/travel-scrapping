import zipfile
from pathlib import Path
from typing import Any, cast

import pytest

from travel_scrapping.bus.flixbus_autocomplete import (
    autocomplete_city,
    autocomplete_results,
    find_cached_mapping,
    save_city_mapping,
    select_unique_mapping,
)
from travel_scrapping.bus.flixbus_gtfs import gtfs_info, normalize_text, search_stops
from travel_scrapping.bus.comparabus import _booking_url, _parse_price_rows, _select_stop
from travel_scrapping.bus.parser import parse_trips
from travel_scrapping.bus.stations import parse_stations
from travel_scrapping.bus.flixbus_openapi import FlixBusOpenApiProvider, _parse_trips, _trip_count
from travel_scrapping.bus.flixbus_rapidapi import FlixBusRapidApiProvider, _payload_error, save_bus_debug
from travel_scrapping.config import Settings
from travel_scrapping.search.providers.playwright_probe import PlaywrightProbeProvider


def _write_gtfs_zip(path: Path, *, include_routes: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "stops.txt",
            "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n"
            "nce,Nice Aeroport,43.66,7.21,0,\n"
            "nice-ville,Nice Ville,43.70,7.26,1,\n"
            "paris,Paris Bercy,48.83,2.38,0,\n",
        )
        if include_routes:
            archive.writestr("routes.txt", "route_id,route_short_name\nr1,Nice-Paris\n")
        archive.writestr("trips.txt", "route_id,service_id,trip_id\nr1,s1,t1\n")
        archive.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\nt1,08:00:00,08:00:00,nce,1\n")
        archive.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\ns1,1,1,1,1,1,1,1,20260701,20260831\n")


def test_flixbus_gtfs_info_absent(tmp_path):
    info = gtfs_info(tmp_path / "missing.zip")

    assert info.present is False
    assert info.stops_count == 0
    assert info.files_present["stops.txt"] is False


def test_flixbus_gtfs_parses_stops_and_search_normalizes(tmp_path):
    path = tmp_path / "gtfs.zip"
    _write_gtfs_zip(path)

    info = gtfs_info(path)
    results = search_stops("nice aeroport", path)

    assert normalize_text("Niçe Aéroport") == "nice aeroport"
    assert info.stops_count == 3
    assert info.routes_count == 1
    assert info.trips_count == 1
    assert info.valid_from == "20260701"
    assert results[0]["stop_id"] == "nce"


def test_flixbus_gtfs_diagnostic_missing_files(tmp_path):
    path = tmp_path / "gtfs.zip"
    _write_gtfs_zip(path, include_routes=False)

    info = gtfs_info(path)

    assert info.present is True
    assert info.files_present["routes.txt"] is False
    assert info.routes_count == 0


def test_flixbus_autocomplete_payload_unique_ambiguous_and_cache(tmp_path):
    rows = autocomplete_results(
        {
            "data": [
                {"name": "Nice", "legacy_id": "nice-legacy", "id": "uuid", "slug": "nice", "country_code": "FR"},
                {"name": "Nice Airport", "legacy_id": "airport-legacy", "id": "airport-uuid", "country_code": "FR"},
            ]
        }
    )

    selected, ambiguous = select_unique_mapping("Nice", rows)
    assert selected and selected["id"] == "uuid"
    assert selected["legacy_id"] == "nice-legacy"
    assert ambiguous is False

    selected, ambiguous = select_unique_mapping("Ni", rows)
    assert selected is None
    assert ambiguous is True

    cache = tmp_path / "cache.json"
    saved = save_city_mapping(query="Nice", id="uuid", legacy_id="nice-legacy", name="Nice", path=cache)
    cached = find_cached_mapping("niçe", path=cache)
    assert saved["id"] == "uuid"
    assert cached and cached["id"] == "uuid"
    assert cached["legacy_id"] == "nice-legacy"


@pytest.mark.asyncio
async def test_flixbus_autocomplete_http_and_payload_errors():
    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = "rate limited"

        def json(self):
            if isinstance(self._payload, Exception):
                raise self._payload
            return self._payload

    class FakeClient:
        def __init__(self, response):
            self.response = response

        async def get(self, url, params, headers):
            return self.response

    throttled = await autocomplete_city("Nice", client=cast(Any, FakeClient(FakeResponse(429, {"message": "quota"}))))
    unexpected = await autocomplete_city("Nice", client=cast(Any, FakeClient(FakeResponse(200, {"data": {"bad": True}}))))

    assert throttled.error == "quota"
    assert throttled.results == []
    assert unexpected.error == "zero results"
    assert unexpected.results == []


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


def test_flixbus_openapi_nested_result_requires_booking_link():
    payload = {
        "trips": [
            {
                "results": {
                    "trip-1": {
                        "uid": "trip-1",
                        "provider": "flixbus",
                        "departure": {"date": "2026-07-30T03:30:00+02:00"},
                        "arrival": {"date": "2026-07-30T19:25:00+02:00"},
                        "price": {"total": 59.48},
                    },
                    "trip-2": {
                        "uid": "trip-2",
                        "provider": "flixbus",
                        "departure": {"date": "2026-07-30T08:00:00+02:00"},
                        "arrival": {"date": "2026-07-30T20:00:00+02:00"},
                        "price": {"total": 49.99},
                        "booking_url": "https://shop.flixbus.test/book",
                    },
                }
            }
        ]
    }

    offers = _parse_trips(
        payload,
        origin="Nice",
        destination="Paris",
        from_id="nice-uuid",
        to_id="paris-uuid",
        ret="2026-08-02",
    )

    assert _trip_count(payload) == 2
    assert len(offers) == 1
    assert offers[0].id == "trip-2"
    assert offers[0].price_amount == 49.99
    assert offers[0].operator_name == "flixbus"
    assert offers[0].booking_url == "https://shop.flixbus.test/book"


def test_comparabus_select_stop_requires_unique_or_exact():
    rows = [{"id": 336, "name": "Nice"}, {"id": 15982, "name": "Aéroport Nice Côte d'Azur NCE"}]

    assert _select_stop("Nice", rows)["id"] == 336
    assert _select_stop("Ni", rows) is None
    assert _select_stop("Lille", [{"id": 6, "name": "Lille"}])["id"] == 6


def test_comparabus_price_parser_requires_redirect_link():
    payload = {
        "outbound": [
            {
                "id": 1,
                "companyId": 13,
                "companyName": "FlixBus",
                "type": "bus",
                "stopExtDep": "2015",
                "stopExtArr": "2215",
                "cents": 998,
                "currency": "EUR",
                "duration": 185,
                "depDatetime": "2026-07-30 03:25:00",
                "arrDatetime": "2026-07-30 06:30:00",
                "link": "uid=direct%3A1&hash=x",
                "full": False,
                "carrierName": "FlixBus",
                "connection": 0,
                "stopIdDep": 10,
                "stopIdArr": 6,
            },
            {
                "id": 2,
                "companyId": 1,
                "type": "bus",
                "cents": 849,
                "depDatetime": "2026-07-30 09:00:00",
                "arrDatetime": "2026-07-30 12:15:00",
                "carrierName": "BlaBlaCar Bus",
            },
        ]
    }

    offers = _parse_price_rows(
        payload,
        origin={"id": 10, "name": "Paris"},
        destination={"id": 6, "name": "Lille"},
        depart="2026-07-30",
        ret="2026-08-02",
        base_url="https://www.comparabus.com",
    )

    assert len(offers) == 1
    assert offers[0].provider == "comparabus"
    assert offers[0].operator_name == "FlixBus"
    assert offers[0].price_amount == 9.98
    assert offers[0].booking_url.startswith("https://www.comparabus.com/fr/redirect?")
    assert "link=uid%3Ddirect%253A1%26hash%3Dx" in offers[0].booking_url


def test_comparabus_booking_url_missing_link_is_not_actionable():
    row = {
        "companyId": 13,
        "stopExtDep": "2015",
        "stopExtArr": "2215",
        "stopIdDep": 10,
        "stopIdArr": 6,
        "cents": 998,
        "depDatetime": "2026-07-30 03:25:00",
        "type": "bus",
    }

    assert _booking_url(row, depart="2026-07-30", ret="2026-08-02", base_url="https://www.comparabus.com") is None


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


def test_flixbus_openapi_status_disabled():
    provider = FlixBusOpenApiProvider(Settings(_env_file=None, bus_enabled=False, flixbus_openapi_enabled=True))

    status = provider.status()

    assert status.name == "flixbus_openapi"
    assert status.enabled is False
    assert provider.last_attempted is False


@pytest.mark.asyncio
async def test_flixbus_openapi_city_resolution_fixture(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"data": [{"legacy_id": "nice-legacy", "id": "uuid", "name": "Nice", "slug": "nice"}]}

    class FakeClient:
        async def get(self, url, params, headers):
            return FakeResponse()

    provider = FlixBusOpenApiProvider(Settings(_env_file=None, flixbus_openapi_enabled=True))

    lookup = await provider.city_search(cast(Any, FakeClient()), "Nice")

    assert lookup.city_id == "uuid"
    assert lookup.legacy_id == "nice-legacy"
    assert lookup.id_kind == "uuid"
    assert lookup.results[0]["name"] == "Nice"
    assert lookup.raw_summary == "autocomplete count=1"
    assert provider.last_raw_count == 1
    assert find_cached_mapping("Nice")["id"] == "uuid"
    assert find_cached_mapping("Nice")["legacy_id"] == "nice-legacy"


@pytest.mark.asyncio
async def test_flixbus_openapi_city_not_found_is_clean(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            return FakeResponse()

    monkeypatch.setattr("travel_scrapping.bus.flixbus_openapi.httpx.AsyncClient", lambda timeout, follow_redirects: FakeClient())
    provider = FlixBusOpenApiProvider(Settings(_env_file=None, flixbus_openapi_enabled=True))

    offers = await provider.search_roundtrip("Nice", "Paris", "2026-07-30", "2026-08-02")

    assert offers == []
    assert provider.last_ok is False
    assert provider.last_raw_count == 0
    assert provider.last_normalized_count == 0
    assert "id UUID absent: 'Nice' or 'Paris'" in (provider.last_error or "")
    assert provider.last_public_params["from_city_id"] is None
    assert provider.last_public_params["to_city_id"] is None
    assert provider.last_public_params["id_kind"] == "uuid"
    assert provider.last_search_status_code is None


@pytest.mark.asyncio
async def test_flixbus_openapi_http_error_returns_empty_with_diagnostics(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload
            self.text = "server error"

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            if "autocomplete" in url:
                return FakeResponse(
                    200,
                    {
                        "data": [
                            {
                                "id": f"{params['q']}-uuid",
                                "legacy_id": f"{params['q']}-legacy",
                                "name": params["q"],
                            }
                        ]
                    },
                )
            return FakeResponse(400, {"message": "Signature is invalid"})

    monkeypatch.setattr("travel_scrapping.bus.flixbus_openapi.httpx.AsyncClient", lambda timeout, follow_redirects: FakeClient())
    provider = FlixBusOpenApiProvider(Settings(_env_file=None, flixbus_openapi_enabled=True, flixbus_debug_save=False))

    offers = await provider.search_roundtrip("Nice", "Venise", "2026-07-30", "2026-08-02")

    assert offers == []
    assert provider.last_attempted is True
    assert provider.last_ok is False
    assert provider.last_status_code == 400
    assert provider.last_raw_count == 0
    assert provider.last_normalized_count == 0
    assert provider.last_error == "Signature is invalid"
    assert provider.last_public_params["from_city_id"] == "Nice-uuid"
    assert provider.last_public_params["from_legacy_id"] == "Nice-legacy"
    assert provider.last_public_params["to_city_id"] == "Venise-uuid"
    assert provider.last_public_params["to_legacy_id"] == "Venise-legacy"
    assert provider.last_public_params["id_kind"] == "uuid"


@pytest.mark.asyncio
async def test_flixbus_openapi_autocomplete_ambiguous_skips_search(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "data": [
                    {"id": "uuid-1", "legacy_id": "nice-1", "name": "Nice Airport"},
                    {"id": "uuid-2", "legacy_id": "nice-2", "name": "Nice Ville"},
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr("travel_scrapping.bus.flixbus_openapi.httpx.AsyncClient", lambda timeout, follow_redirects: FakeClient())
    provider = FlixBusOpenApiProvider(Settings(_env_file=None, flixbus_openapi_enabled=True))

    offers = await provider.search_roundtrip("Nice", "Paris", "2026-07-30", "2026-08-02")

    assert offers == []
    assert provider.last_lookup_ambiguous is True
    assert provider.last_search_status_code is None
    assert all("search/service/v4/search" not in call for call in calls)


@pytest.mark.asyncio
async def test_flixbus_openapi_uses_cache_before_autocomplete(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_city_mapping(query="Nice", id="nice-uuid", legacy_id="nice-cache", name="Nice")
    save_city_mapping(query="Paris", id="paris-uuid", legacy_id="paris-cache", name="Paris")

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {
                "trips": [
                    {
                        "id": "trip-1",
                        "departure_at": "2026-07-30T08:00:00+00:00",
                        "arrival_at": "2026-07-30T14:00:00+00:00",
                        "price": {"amount": 19},
                        "operator": "FlixBus",
                        "booking_url": "https://example.test/book",
                    }
                ]
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            assert params["from_city_id"] == "nice-uuid"
            assert params["to_city_id"] == "paris-uuid"
            assert params["departure_date"] == "30.07.2026"
            assert params["products"] == '{"adult":1}'
            return FakeResponse()

    monkeypatch.setattr("travel_scrapping.bus.flixbus_openapi.httpx.AsyncClient", lambda timeout, follow_redirects: FakeClient())
    provider = FlixBusOpenApiProvider(
        Settings(_env_file=None, flixbus_openapi_enabled=True, flixbus_debug_save=False)
    )

    offers = await provider.search_roundtrip("Nice", "Paris", "2026-07-30", "2026-08-02")

    assert provider.last_lookup_source == "cache"
    assert provider.last_search_status_code == 200
    assert provider.last_public_params["from_city_id"] == "nice-uuid"
    assert provider.last_public_params["from_legacy_id"] == "nice-cache"
    assert provider.last_public_params["id_kind"] == "uuid"
    assert offers[0].booking_url


@pytest.mark.asyncio
async def test_flixbus_openapi_legacy_id_only_when_explicit(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    class FakeResponse:
        def __init__(self, payload):
            self.status_code = 200
            self._payload = payload
            self.text = ""

        def json(self):
            return self._payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, params, headers):
            if "autocomplete" in url:
                return FakeResponse(
                    {"data": [{"id": f"{params['q']}-uuid", "legacy_id": f"{params['q']}-legacy", "name": params["q"]}]}
                )
            assert params["from_city_id"] == "Nice-legacy"
            assert params["to_city_id"] == "Paris-legacy"
            return FakeResponse({"trips": []})

    monkeypatch.setattr("travel_scrapping.bus.flixbus_openapi.httpx.AsyncClient", lambda timeout, follow_redirects: FakeClient())
    provider = FlixBusOpenApiProvider(Settings(_env_file=None, flixbus_openapi_enabled=True, flixbus_debug_save=False))

    offers = await provider.search_roundtrip("Nice", "Paris", "2026-07-30", "2026-08-02", use_legacy_id=True)

    assert offers == []
    assert provider.last_public_params["from_city_id"] == "Nice-legacy"
    assert provider.last_public_params["from_legacy_id"] == "Nice-legacy"
    assert provider.last_public_params["id_kind"] == "legacy"


@pytest.mark.asyncio
async def test_playwright_probe_status_and_empty_search():
    disabled = PlaywrightProbeProvider(Settings(_env_file=None, playwright_enabled=False, scraping_enabled=True))
    assert disabled.status().warnings == ["Playwright scraping disabled"]
    enabled = PlaywrightProbeProvider(Settings(_env_file=None, playwright_enabled=True, scraping_enabled=True))
    status = enabled.status()
    assert status.enabled is False
    assert "Safe probe skeleton" in status.warnings[0]
    assert await enabled.search([], [], limit=1) == []
