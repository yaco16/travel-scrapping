from datetime import date, datetime, timezone
from types import SimpleNamespace

from travel_scrapping.web.presentation import (
    airlines_display,
    booking_display,
    date_time,
    destination_display,
    operator_display,
    price_display,
    short_date,
    warnings_display,
)


def test_destination_display_uses_french_city_mapping():
    assert destination_display(SimpleNamespace(destination_airport="BTS", destination_city=None)) == "Bratislava"
    assert destination_display(SimpleNamespace(destination_airport="VCE", destination_city=None)) == "Venise"
    assert destination_display(SimpleNamespace(destination_airport="SVQ", destination_city=None)) == "Séville"
    assert destination_display(SimpleNamespace(destination_airport="BCN", destination_city=None)) == "Barcelone"


def test_destination_display_unknown_code_has_clear_fallback():
    deal = SimpleNamespace(destination_airport="XXX", destination_city=None)
    assert destination_display(deal) == "XXX inconnu"


def test_short_date_format():
    assert short_date(date(2026, 7, 2)) == "02/07/26"
    assert short_date("2026-07-02") == "02/07/26"
    assert short_date(None) == "Non disponible"
    assert short_date("") == "Non disponible"
    assert short_date("invalid") == "Non disponible"


def test_date_time_format_handles_missing_datetime_and_iso_values():
    assert date_time(None) == "Non disponible"
    assert date_time(datetime(2026, 6, 20, 9, 56)) == "20/06/26 09:56"
    assert date_time(datetime(2026, 6, 20, 9, 56, tzinfo=timezone.utc)) == "20/06/26 09:56"
    assert date_time("2026-06-20T09:56:00+00:00") == "20/06/26 09:56"
    assert date_time("2026-06-20T09:56:00Z") == "20/06/26 09:56"
    assert date_time("invalid") == "Non disponible"


def test_price_display_without_currency_or_decimals():
    assert price_display(55.00) == "55,00 €"
    assert price_display(1234.5) == "1 234,50 €"


def test_empty_airlines_displayed_as_unknown():
    assert airlines_display("[]") == ""


def test_operator_display_priority():
    assert operator_display(SimpleNamespace(operator_name="SNCF", airlines_json='["easyJet"]', provider="p", source="s")) == "SNCF"
    assert operator_display(SimpleNamespace(operator_name=None, airlines_json='["easyJet"]', provider="p", source="s")) == "easyJet"
    assert operator_display(SimpleNamespace(operator_name=None, airlines_json="[]", provider="flixbus", source="s")) == "flixbus"
    assert operator_display(SimpleNamespace(operator_name=None, airlines_json="[]", provider=None, source="distribusion")) == "distribusion"


def test_warnings_translated_to_french():
    assert warnings_display('["cached or indicative fare; verify before booking","layover unknown"]') == [
        "Prix indicatif : à vérifier avant réservation",
        "Durée d’escale inconnue",
    ]


def test_missing_travelpayouts_marker_link_explained():
    deal = SimpleNamespace(booking_url=None, warnings_json='["travelpayouts marker missing"]')
    assert booking_display(deal) == "Lien indisponible : TRAVELPAYOUTS_MARKER manquant"
