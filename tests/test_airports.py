from __future__ import annotations

import httpx
from sqlalchemy import select

from travel_scrapping.airports import resolve_airport
from travel_scrapping.config import Settings
from travel_scrapping.db import AirportMetadata, init_db, session_scope
from travel_scrapping.providers.api_ninjas_airports import fetch_airport_by_iata


class FakeResponse:
    def __init__(self, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_fetch_airport_by_iata_filters_exact_match(monkeypatch):
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append((url, params, headers, timeout))
        return FakeResponse(
            200,
            [
                {"iata": "VCE1", "name": "Partial", "city": "Wrong"},
                {
                    "iata": "VCE",
                    "name": "Venice Marco Polo Airport",
                    "city": "Venice",
                    "country": "Italy",
                    "timezone": "Europe/Rome",
                    "latitude": "45.5053",
                    "longitude": "12.3519",
                },
            ],
        )

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.httpx.get", fake_get)
    settings = Settings(_env_file=None, api_ninjas_api_key="secret")

    info = fetch_airport_by_iata("VCE", settings=settings)

    assert info is not None
    assert info.iata == "VCE"
    assert info.city == "Venice"
    assert info.city_fr == "Venise"
    assert info.source == "api_ninjas"
    assert calls[0][1] == {"iata": "VCE"}
    assert calls[0][2] == {"X-Api-Key": "secret"}
    assert calls[0][3] == 5.0


def test_fetch_airport_by_iata_without_key_returns_none():
    settings = Settings(_env_file=None, api_ninjas_api_key="")
    assert fetch_airport_by_iata("VCE", settings=settings) is None


def test_fetch_airport_by_iata_timeout_returns_none(monkeypatch):
    def fake_get(url, params, headers, timeout):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.httpx.get", fake_get)
    settings = Settings(_env_file=None, api_ninjas_api_key="secret")

    assert fetch_airport_by_iata("VCE", settings=settings) is None


def test_resolver_french_display_names_without_api_key(tmp_path):
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    factory = init_db(settings)
    with session_scope(factory) as session:
        assert resolve_airport("VCE", settings, session).info.display_name == "Venise"
        assert resolve_airport("SVQ", settings, session).info.display_name == "Séville"
        assert resolve_airport("BCN", settings, session).info.display_name == "Barcelone"
        assert resolve_airport("BTS", settings, session).info.display_name == "Bratislava"
        assert resolve_airport("XXX", settings, session).info.display_name == "XXX inconnu"


def test_resolver_caches_api_result_and_reuses_cache(tmp_path, monkeypatch):
    calls = 0

    def fake_fetch(iata_code, settings=None):
        nonlocal calls
        calls += 1
        from travel_scrapping.airports import AirportInfo

        return AirportInfo(
            iata="VCE",
            airport_name="Venice Marco Polo Airport",
            city="Venice",
            city_fr="Venise",
            country="Italy",
            timezone="Europe/Rome",
            latitude=45.5053,
            longitude=12.3519,
            source="api_ninjas",
            raw_payload={"iata": "VCE", "city": "Venice"},
        )

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.fetch_airport_by_iata", fake_fetch)
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{tmp_path}/x.db",
        api_ninjas_api_key="secret",
    )
    factory = init_db(settings)

    with session_scope(factory) as session:
        first = resolve_airport("VCE", settings, session)
        second = resolve_airport("VCE", settings, session)
        rows = list(session.scalars(select(AirportMetadata)))

    assert first.info.source == "api_ninjas"
    assert second.cache_hit is True
    assert second.info.display_name == "Venise"
    assert calls == 1
    assert len(rows) == 1
    assert rows[0].iata == "VCE"
    assert rows[0].city == "Venice"
