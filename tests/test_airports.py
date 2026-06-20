from __future__ import annotations

import httpx
from sqlalchemy import select

from travel_scrapping.airports import resolve_airport
from travel_scrapping.airports.ourairports import ensure_airports_csv, import_csv, lookup_airport
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

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("bad status", request=None, response=None)


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


def test_fetch_airport_by_iata_rejects_bad_responses(monkeypatch):
    settings = Settings(_env_file=None, api_ninjas_api_key="secret")
    responses = [
        FakeResponse(500, []),
        FakeResponse(200, ValueError("bad json")),
        FakeResponse(200, {"iata": "VCE"}),
        FakeResponse(200, [{"iata": "XXX", "name": "Wrong"}]),
    ]

    def fake_get(url, params, headers, timeout):
        return responses.pop(0)

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.httpx.get", fake_get)

    assert fetch_airport_by_iata("VCE", settings=settings) is None
    assert fetch_airport_by_iata("VCE", settings=settings) is None
    assert fetch_airport_by_iata("VCE", settings=settings) is None
    assert fetch_airport_by_iata("VCE", settings=settings) is None


def test_ensure_airports_csv_uses_cache_and_force_refresh(tmp_path, monkeypatch):
    path = tmp_path / "airports.csv"
    path.write_text("cached", encoding="utf-8")
    calls = 0

    def fake_get(url, timeout):
        nonlocal calls
        calls += 1
        return FakeResponse(200, [])

    monkeypatch.setattr("travel_scrapping.airports.ourairports.httpx.get", fake_get)

    assert ensure_airports_csv(path) == path
    assert path.read_text(encoding="utf-8") == "cached"
    assert calls == 0

    response = FakeResponse(200, [])
    response.content = b"fresh"

    def fake_refresh(url, timeout):
        nonlocal calls
        calls += 1
        return response

    monkeypatch.setattr("travel_scrapping.airports.ourairports.httpx.get", fake_refresh)
    assert ensure_airports_csv(path, force_refresh=True) == path
    assert path.read_text(encoding="utf-8") == "fresh"
    assert calls == 1


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


def test_ourairports_import_and_resolve(tmp_path):
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,iata_code\n"
        "LIPZ,large_airport,Venice Marco Polo Airport,45.5053,12.3519,7,IT,IT-34,Venice,yes,VCE\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db", api_ninjas_api_key="")
    factory = init_db(settings)
    with session_scope(factory) as session:
        assert import_csv(session, csv_path) == 1
        result = resolve_airport("VCE", settings, session)

    assert result.info.source == "ourairports"
    assert result.info.display_name == "Venise"


def test_ourairports_import_updates_existing_and_lookup_handles_invalid(tmp_path):
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,iata_code\n"
        "OLD,small_airport,Old Name,bad,bad,bad,IT,IT-34,Old City,no,VCE\n",
        encoding="utf-8",
    )
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db")
    factory = init_db(settings)
    with session_scope(factory) as session:
        assert lookup_airport(session, "") is None
        assert lookup_airport(session, "VCE") is None
        assert import_csv(session, csv_path) == 1
        first = lookup_airport(session, "VCE")
        assert first is not None
        assert first.latitude is None
        assert first.raw_payload["elevation_ft"] is None
        csv_path.write_text(
            "ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,iata_code\n"
            "NEW,large_airport,New Name,45.5,12.3,7,IT,IT-34,Venice,yes,VCE\n",
            encoding="utf-8",
        )
        assert import_csv(session, csv_path) == 1
        updated = lookup_airport(session, "VCE")

    assert updated is not None
    assert updated.airport_name == "New Name"
    assert updated.latitude == 45.5


def test_api_ninjas_not_called_when_ourairports_has_code(tmp_path, monkeypatch):
    csv_path = tmp_path / "airports.csv"
    csv_path.write_text(
        "ident,type,name,latitude_deg,longitude_deg,elevation_ft,iso_country,iso_region,municipality,scheduled_service,iata_code\n"
        "LIPZ,large_airport,Venice Marco Polo Airport,45.5053,12.3519,7,IT,IT-34,Venice,yes,VCE\n",
        encoding="utf-8",
    )
    calls = 0

    def fake_fetch(iata_code, settings=None):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.fetch_airport_by_iata", fake_fetch)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db", api_ninjas_api_key="secret")
    factory = init_db(settings)
    with session_scope(factory) as session:
        import_csv(session, csv_path)
        result = resolve_airport("VCE", settings, session)

    assert result.info.source == "ourairports"
    assert calls == 0


def test_api_ninjas_fallback_when_ourairports_missing_code(tmp_path, monkeypatch):
    from travel_scrapping.airports import AirportInfo

    def fake_fetch(iata_code, settings=None):
        return AirportInfo(
            iata=iata_code,
            airport_name="Seville Airport",
            city="Seville",
            city_fr="Séville",
            country="Spain",
            timezone=None,
            latitude=None,
            longitude=None,
            source="api_ninjas",
        )

    monkeypatch.setattr("travel_scrapping.providers.api_ninjas_airports.fetch_airport_by_iata", fake_fetch)
    settings = Settings(_env_file=None, database_url=f"sqlite:///{tmp_path}/x.db", api_ninjas_api_key="secret")
    factory = init_db(settings)
    with session_scope(factory) as session:
        result = resolve_airport("SVQ", settings, session)

    assert result.info.source == "api_ninjas"
