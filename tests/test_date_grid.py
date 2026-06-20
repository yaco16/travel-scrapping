from datetime import date

import pytest

from travel_scrapping.search.date_grid import generate_roundtrip_dates


def test_3_to_5_night_combinations_no_past():
    pairs = generate_roundtrip_dates(
        today=date(2026, 7, 1), date_to=date(2026, 7, 7), min_nights=3, max_nights=5
    )
    assert pairs[0] == (date(2026, 7, 1), date(2026, 7, 4), 3)
    assert all(3 <= nights <= 5 for _, _, nights in pairs)
    assert all(ret <= date(2026, 7, 7) for _, ret, _ in pairs)


def test_invalid_nights():
    with pytest.raises(ValueError):
        generate_roundtrip_dates(today=date.today(), date_to=date.today(), min_nights=5, max_nights=3)


def test_search_end_date_limits_last_departure():
    pairs = generate_roundtrip_dates(
        today=date(2026, 8, 24),
        date_to=date(2026, 8, 30),
        min_nights=3,
        max_nights=5,
    )
    assert (date(2026, 8, 25), date(2026, 8, 30), 5) in pairs
    assert all(ret <= date(2026, 8, 30) for _, ret, _ in pairs)
    assert all(outbound <= date(2026, 8, 25) for outbound, _, nights in pairs if nights == 5)
    assert (date(2026, 8, 26), date(2026, 8, 31), 5) not in pairs
