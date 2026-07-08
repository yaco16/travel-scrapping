import json
import zlib
from datetime import date, datetime, timezone
from types import SimpleNamespace

from travel_scrapping.web.presentation import (
    airlines_display,
    booking_display,
    bus_route_details,
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


def test_bus_route_details_extracts_stations_segments_and_stopover():
    payload = {
        "legs": [
            {
                "departure_station_name": "Nice Aéroport",
                "arrival_station_name": "Milan Lampugnano",
                "departure_at": "2026-07-02T08:00:00",
                "arrival_at": "2026-07-02T13:30:00",
            },
            {
                "departure_station_name": "Milan Lampugnano",
                "arrival_station_name": "Venise Tronchetto",
                "departure_at": "2026-07-02T14:15:00",
                "arrival_at": "2026-07-02T17:45:00",
            },
        ]
    }
    deal = SimpleNamespace(
        transport_mode="bus",
        raw_payload_z=zlib.compress(json.dumps(payload).encode()),
        origin_airport="NCE",
        destination_airport="VCE",
        destination_city="Venise",
    )

    details = bus_route_details(deal)

    assert details["origin_station"] == "Nice Aéroport"
    assert details["destination_station"] == "Venise Tronchetto"
    assert details["segments"][0]["duration_minutes"] == 330
    assert details["segments"][1]["duration_minutes"] == 210
    assert details["stopovers"] == [
        {
            "index": 1,
            "station": "Milan Lampugnano",
            "arrival_at": datetime(2026, 7, 2, 13, 30),
            "departure_at": datetime(2026, 7, 2, 14, 15),
            "duration_minutes": 45,
            "inbound_duration_minutes": 330,
            "outbound_duration_minutes": 210,
        }
    ]


def test_bus_route_details_uses_station_names_and_marks_unknown_stopover_details():
    payload = {
        "departure_station_name": "Nice Vauban",
        "arrival_station_name": "Venise Tronchetto",
        "stopover_details_available": False,
    }
    deal = SimpleNamespace(
        transport_mode="bus",
        raw_payload_z=zlib.compress(json.dumps(payload).encode()),
        destination_airport="VCE",
        destination_city="Venise",
        outbound_departure_at=datetime(2026, 7, 2, 8, 0),
        outbound_arrival_at=datetime(2026, 7, 2, 17, 45),
        duration_minutes=585,
        stops_count=1,
    )

    details = bus_route_details(deal)

    assert details["origin_station"] == "Nice Vauban"
    assert details["destination_station"] == "Venise Tronchetto"
    assert details["segments"][0]["departure_station"] == "Nice Vauban"
    assert details["segments"][0]["arrival_station"] == "Venise Tronchetto"
    assert details["unavailable_stopovers"] == 1
