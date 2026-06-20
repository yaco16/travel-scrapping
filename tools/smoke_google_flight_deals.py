from __future__ import annotations

import asyncio
import json
from datetime import date
from typing import Any

from travel_scrapping.config import Settings
from travel_scrapping.formatters import format_price_fr
from travel_scrapping.search.filters import validate_deal
from travel_scrapping.search.providers.serpapi_google_flights import SerpApiGoogleFlightDealsProvider
from travel_scrapping.web.presentation import short_date


def _target_presence(deals: list[Any]) -> dict[str, str]:
    targets = {"SVQ": "absent", "STN": "absent", "FCO": "absent"}
    for deal in deals:
        code = deal.destination_airport
        if code in targets:
            targets[code] = "present"
    return targets


async def main() -> None:
    settings = Settings(
        origin_airport="NCE",
        search_start_date=date(2026, 7, 1),
        search_end_date=date(2026, 8, 31),
        min_nights=1,
        max_nights=7,
        max_roundtrip_price_eur=150,
        max_stops=1,
        default_currency="EUR",
        adults=1,
    )
    if not settings.serpapi_api_key:
        print("SERPAPI_API_KEY missing")
        return
    provider = SerpApiGoogleFlightDealsProvider(settings)
    normalized = await provider.search([], [], limit=settings.top_results_limit)
    accepted = []
    rejected = []
    for deal in normalized:
        ok, reasons = validate_deal(deal, settings, today=settings.search_start_date)
        if ok and deal.actionable:
            accepted.append(deal)
        else:
            rejected.append({"route": deal.route_key, "reasons": reasons + deal.missing_fields})
    print("endpoint=google_flights_deals")
    print(f"http_status={provider.last_status_code}")
    print(f"search_metadata_status={provider.last_public_params.get('payload_diagnostic', {}).get('search_metadata_status')}")
    print(f"params={json.dumps(provider.last_public_params, ensure_ascii=False)}")
    print(f"raw_count={provider.last_raw_count}")
    print(f"normalized_count={provider.last_normalized_count}")
    print(f"accepted_count={len(accepted)}")
    print(f"rejected_count={len(rejected)}")
    print(f"presence={json.dumps(_target_presence(normalized), ensure_ascii=False)}")
    for deal in accepted[:5]:
        print(
            "example="
            f"{deal.destination_airport} "
            f"{short_date(deal.outbound_date)}->{short_date(deal.return_date)} "
            f"{format_price_fr(deal.total_price_eur, deal.currency)} "
            f"{deal.destination_city or ''}"
        )
    print(f"debug_json={provider.last_debug_path}")


if __name__ == "__main__":
    asyncio.run(main())
