from travel_scrapping.search.normalizer import normalize_serpapi_item, scrub_payload


def test_serpapi_normalization():
    deal = normalize_serpapi_item(
        {
            "price": 42,
            "currency": "EUR",
            "destination_airport": {"id": "BCN", "city": "Barcelona"},
            "outbound_date": "2026-07-01",
            "return_date": "2026-07-04",
            "airlines": ["easyJet"],
            "stops": 0,
            "booking_url": "https://example.com",
        },
        origin="NCE",
    )
    assert deal.destination_airport == "BCN"
    assert deal.nights == 3
    assert deal.confidence == "high"


def test_scrub_payload_masks_secretish_keys():
    assert scrub_payload({"api_key": "secret"})["api_key"] == "***"
