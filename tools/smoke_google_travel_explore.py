from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.config import Settings
from travel_scrapping.search.normalizer import scrub_payload


SERPAPI_URL = "https://serpapi.com/search.json"
VARIANTS = [
    ("A", "2026-07-16", "2026-07-23"),
    ("B", "2026-07-21", "2026-07-28"),
    ("C", "2026-08-28", "2026-08-31"),
    ("D", "2026-07-01", "2026-07-08"),
]
LIST_KEYS = ("destinations", "flights", "flight_deals", "deals", "best_flights", "other_flights")


def _public_params(params: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in params.items() if key != "api_key"}


def _price(item: dict[str, Any]) -> Any:
    for key in ("flight_price", "price", "extracted_price", "total_price"):
        if item.get(key) is not None:
            return item[key]
    return None


def _destination(item: dict[str, Any]) -> str | None:
    destination = item.get("destination")
    airport = item.get("destination_airport") or item.get("airport") or {}
    values = [
        item.get("name"),
        item.get("city"),
        destination.get("name") if isinstance(destination, dict) else None,
        airport.get("code") if isinstance(airport, dict) else None,
        airport.get("id") if isinstance(airport, dict) else None,
    ]
    return next((str(value) for value in values if value), None)


def _contains_code(item: dict[str, Any], code: str) -> bool:
    return code in json.dumps(item, ensure_ascii=False).upper()


def _summary_items(payload: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    lists = {key: payload.get(key) for key in LIST_KEYS if isinstance(payload.get(key), list)}
    items: list[dict[str, Any]] = []
    for value in lists.values():
        items.extend(item for item in value if isinstance(item, dict))
    return {key: len(value) for key, value in lists.items()}, items


async def main() -> None:
    settings = Settings()
    if not settings.serpapi_api_key:
        print("SERPAPI_API_KEY missing")
        return
    summaries: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=45) as client:
        for label, outbound, return_date in VARIANTS:
            params = {
                "engine": "google_travel_explore",
                "departure_id": "NCE",
                "type": "1",
                "currency": "EUR",
                "gl": "fr",
                "hl": "fr",
                "adults": "1",
                "max_price": "150",
                "stops": "2",
                "travel_mode": "1",
                "outbound_date": outbound,
                "return_date": return_date,
                "api_key": settings.serpapi_api_key,
            }
            response = await client.get(SERPAPI_URL, params=params)
            try:
                payload = response.json()
            except ValueError:
                payload = {"_text": response.text[:1000]}
            list_counts, items = _summary_items(payload)
            examples = [{"destination": _destination(item), "price": _price(item)} for item in items[:5]]
            presence = {code: any(_contains_code(item, code) for item in items) for code in ("SVQ", "STN", "FCO")}
            debug_dir = Path("data/debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            debug_path = debug_dir / (
                f"serpapi-google-travel-explore-smoke-{label.lower()}-"
                f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
            )
            debug_path.write_text(
                json.dumps(
                    scrub_payload(
                        {
                            "variant": label,
                            "params": _public_params(params),
                            "http_status": response.status_code,
                            "payload": payload,
                        }
                    ),
                    indent=2,
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            summary = {
                "variant": label,
                "http_status": response.status_code,
                "search_metadata_status": (payload.get("search_metadata") or {}).get("status"),
                "top_level_keys": list(payload.keys()),
                "list_keys": list_counts,
                "raw_count": len(items),
                "examples": examples,
                "presence": presence,
                "debug_path": str(debug_path),
            }
            summaries.append(summary)
            print(json.dumps(summary, ensure_ascii=False))
    print(f"TOTAL_RAW {sum(summary['raw_count'] for summary in summaries)}")


if __name__ == "__main__":
    asyncio.run(main())
