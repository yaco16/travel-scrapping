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


def test_reject_55_nights_after_normalization():
    d = deal(
        destination_airport="BTS",
        outbound_date=date(2026, 7, 2),
        return_date=date(2026, 8, 26),
        nights=3,
        total_price=55,
    )
    ok, reasons = validate_deal(d, Settings(_env_file=None, min_nights=3, max_nights=5), today=date(2026, 6, 1))
    assert not ok
    assert d.nights == 55
    assert "night range mismatch" in reasons


def test_reject_return_after_search_end_date():
    d = deal(outbound_date=date(2026, 8, 26), return_date=date(2026, 8, 31), nights=5)
    ok, reasons = validate_deal(
        d,
        Settings(_env_file=None, search_end_date=date(2026, 8, 30), min_nights=3, max_nights=5),
        today=date(2026, 6, 1),
    )
    assert not ok
    assert "return after search end date" in reasons
