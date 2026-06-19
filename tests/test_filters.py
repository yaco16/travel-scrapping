from datetime import date

from travel_scrapping.config import Settings
from travel_scrapping.schemas import DealCandidate
from travel_scrapping.search.filters import validate_deal


def deal(**kwargs):
    data = dict(
        source="x",
        origin_airport="NCE",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=50,
        currency="EUR",
        is_direct=True,
    )
    data.update(kwargs)
    return DealCandidate(**data)


def test_accept_under_budget_and_warn_unknowns():
    d = deal()
    ok, reasons = validate_deal(d, Settings(_env_file=None), today=date(2026, 6, 1))
    assert ok
    assert reasons == []
    assert "layover unknown" in d.warnings


def test_reject_over_budget():
    ok, reasons = validate_deal(deal(total_price=100), Settings(_env_file=None), today=date(2026, 6, 1))
    assert not ok
    assert "over budget" in reasons


def test_layover_and_overnight_rejection():
    d = deal(max_layover_hours=4, has_overnight_airport=True)
    ok, reasons = validate_deal(d, Settings(_env_file=None), today=date(2026, 6, 1))
    assert not ok
    assert "layover too long" in reasons
    assert "overnight airport stay" in reasons


def test_air_time_rejection():
    d = deal(outbound_duration_hours=6, return_duration_hours=6)
    ok, reasons = validate_deal(d, Settings(_env_file=None), today=date(2026, 6, 1))
    assert not ok
    assert "outbound air time too long" in reasons
    assert "return air time too long" in reasons
