import pytest
import respx
from httpx import Response

from travel_scrapping.config import Settings
from travel_scrapping.search.providers.travelpayouts import TravelpayoutsProvider, parse_travelpayouts_payload


def test_travelpayouts_missing_marker_warns():
    status = TravelpayoutsProvider(Settings(_env_file=None, travelpayouts_token="tok", travelpayouts_marker="")).status()
    assert status.enabled
    assert "TRAVELPAYOUTS_MARKER missing; deeplinks disabled" in status.warnings


def test_travelpayouts_missing_token_disabled():
    assert not TravelpayoutsProvider(Settings(_env_file=None, travelpayouts_token="")).status().enabled


def test_parse_travelpayouts_payload():
    deals = parse_travelpayouts_payload(
        {
            "data": [
                {
                    "destination": "BCN",
                    "depart_date": "2026-07-01",
                    "return_date": "2026-07-04",
                    "value": 45,
                    "airline": "U2",
                    "deep_link": "https://example.test/book",
                }
            ]
        },
        origin="NCE",
    )
    assert deals[0].confidence == "low"
    assert deals[0].airlines == ["U2"]
    assert deals[0].booking_url == "https://example.test/book"


def test_parse_travelpayouts_payload_missing_marker_adds_warning():
    deals = parse_travelpayouts_payload(
        {"data": [{"destination": "BTS", "depart_date": "2026-07-02", "return_date": "2026-07-06", "value": 55}]},
        origin="NCE",
        marker="",
    )
    assert deals[0].airlines == []
    assert "airline missing from source" in deals[0].warnings
    assert "travelpayouts marker missing" in deals[0].warnings
    assert deals[0].booking_url is None


@pytest.mark.asyncio
@respx.mock
async def test_travelpayouts_search_mocked():
    respx.get("https://api.travelpayouts.com/v2/prices/latest").mock(
        return_value=Response(200, json={"data": []})
    )
    deals = await TravelpayoutsProvider(Settings(_env_file=None, travelpayouts_token="tok")).search([], [], limit=1)
    assert deals == []
