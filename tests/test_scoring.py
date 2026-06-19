from datetime import date

from travel_scrapping.schemas import DealCandidate
from travel_scrapping.search.scoring import sort_deals


def make(price, confidence="low", direct=False):
    return DealCandidate(
        source="x",
        origin_airport="NCE",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=price,
        confidence=confidence,
        is_direct=direct,
    )


def test_sort_by_price_then_confidence_then_direct():
    deals = [make(70, "high"), make(50, "low"), make(50, "high", True)]
    sorted_deals = sort_deals(deals)
    assert sorted_deals[0].confidence == "high"
    assert sorted_deals[0].total_price == 50
