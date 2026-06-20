from travel_scrapping.formatters import format_date_fr, format_datetime_fr, format_duration, format_price_fr
from travel_scrapping.web.presentation import mode_display


def test_format_date_and_datetime_fr():
    assert format_date_fr("2026-07-30") == "30/07/26"
    assert format_date_fr("2026-08-31") == "31/08/26"
    assert format_datetime_fr("2026-07-30T08:15:00+00:00") == "30/07/26 08:15"


def test_format_price_and_duration_fr():
    assert format_price_fr(1234.5, "EUR") == "1 234,50 €"
    assert format_duration(185) == "3h05"
    assert format_price_fr(None) == ""
    assert format_price_fr(None, diagnostic=True) == "Non disponible"


def test_mode_display_train():
    assert mode_display("flight") == "Avion"
    assert mode_display("bus") == "Bus"
    assert mode_display("train") == "Train"
