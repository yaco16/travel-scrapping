from datetime import date
from types import SimpleNamespace

from travel_scrapping.web.presentation import (
    airlines_display,
    booking_display,
    destination_display,
    price_display,
    short_date,
    warnings_display,
)


def test_destination_display_uses_french_city_mapping():
    deal = SimpleNamespace(destination_airport="BTS", destination_city=None)
    assert destination_display(deal) == "Bratislava"


def test_short_date_format():
    assert short_date(date(2026, 7, 2)) == "02/07/26"


def test_price_display_without_currency_or_decimals():
    assert price_display(55.00) == "55"


def test_empty_airlines_displayed_as_unknown():
    assert airlines_display("[]") == "Non communiqué"


def test_warnings_translated_to_french():
    assert warnings_display('["cached or indicative fare; verify before booking","layover unknown"]') == [
        "Prix indicatif : à vérifier avant réservation",
        "Durée d’escale inconnue",
    ]


def test_missing_travelpayouts_marker_link_explained():
    deal = SimpleNamespace(booking_url=None, warnings_json='["travelpayouts marker missing"]')
    assert booking_display(deal) == "Lien indisponible : TRAVELPAYOUTS_MARKER manquant"
