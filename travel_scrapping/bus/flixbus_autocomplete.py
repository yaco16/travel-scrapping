from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from travel_scrapping.bus.flixbus_gtfs import normalize_text
from travel_scrapping.search.normalizer import scrub_payload

AUTOCOMPLETE_URL = "https://global.api.flixbus.com/mobile/v1/network/autocomplete"
CITY_CACHE_PATH = Path("data/cache/flixbus_city_ids.json")


@dataclass(frozen=True)
class AutocompleteDiagnostic:
    query: str
    endpoint: str
    params: dict[str, Any]
    status_code: int | None
    results: list[dict[str, Any]]
    raw_count: int
    error: str | None
    ambiguous: bool = False
    selected: dict[str, Any] | None = None


def autocomplete_sync(query: str, *, lang: str = "fr", limit: int = 50) -> AutocompleteDiagnostic:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        params = {"q": query, "limit": limit, "lang": lang}
        try:
            response = client.get(AUTOCOMPLETE_URL, params=params, headers=_headers())
            try:
                payload = response.json()
            except ValueError:
                payload = {"error": response.text[:300]}
            if response.status_code >= 400:
                return AutocompleteDiagnostic(
                    query, AUTOCOMPLETE_URL, params, response.status_code, [], 0, payload_error(payload)
                )
            results = autocomplete_results(payload)
            selected, ambiguous = select_unique_mapping(query, results)
            return AutocompleteDiagnostic(
                query=query,
                endpoint=AUTOCOMPLETE_URL,
                params=params,
                status_code=response.status_code,
                results=results,
                raw_count=len(results),
                error=None if results else "zero results",
                ambiguous=ambiguous,
                selected=selected,
            )
        except Exception as exc:
            return AutocompleteDiagnostic(query, AUTOCOMPLETE_URL, params, None, [], 0, str(exc)[:300])


async def autocomplete_city(
    query: str,
    *,
    client: httpx.AsyncClient | None = None,
    lang: str = "fr",
    limit: int = 50,
) -> AutocompleteDiagnostic:
    params = {"q": query, "limit": limit, "lang": lang}
    own_client = client is None
    http_client = client or httpx.AsyncClient(timeout=20, follow_redirects=True)
    status_code: int | None = None
    payload: Any = {}
    error: str | None = None
    try:
        response = await http_client.get(AUTOCOMPLETE_URL, params=params, headers=_headers())
        status_code = response.status_code
        try:
            payload = response.json()
        except ValueError:
            payload = {"error": response.text[:300]}
        if response.status_code >= 400:
            error = payload_error(payload) or f"autocomplete HTTP {response.status_code}"
            return AutocompleteDiagnostic(query, AUTOCOMPLETE_URL, params, status_code, [], 0, error)
        results = autocomplete_results(payload)
        selected, ambiguous = select_unique_mapping(query, results)
        return AutocompleteDiagnostic(
            query=query,
            endpoint=AUTOCOMPLETE_URL,
            params=params,
            status_code=status_code,
            results=results,
            raw_count=len(results),
            error=None if results else "zero results",
            ambiguous=ambiguous,
            selected=selected,
        )
    except Exception as exc:
        return AutocompleteDiagnostic(query, AUTOCOMPLETE_URL, params, status_code, [], 0, str(exc)[:300])
    finally:
        if own_client:
            await http_client.aclose()


def autocomplete_results(payload: Any) -> list[dict[str, Any]]:
    rows: Any
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("data") or payload.get("results") or payload.get("items") or payload.get("cities") or []
    else:
        return []
    if not isinstance(rows, list):
        return []
    return [public_result_fields(row) for row in rows if isinstance(row, dict)]


def public_result_fields(row: dict[str, Any]) -> dict[str, Any]:
    useful = {
        "name",
        "legacy_id",
        "id",
        "slug",
        "country_code",
        "city_id",
        "type",
        "subtype",
    }
    cleaned = {key: row.get(key) for key in useful if key in row}
    for key in ("coordinates", "location"):
        if key in row:
            cleaned[key] = row.get(key)
    return scrub_payload(cleaned)


def select_unique_mapping(query: str, results: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, bool]:
    candidates = [row for row in results if row.get("id")]
    if not candidates:
        return None, False
    normalized_query = normalize_text(query)
    exact = [row for row in candidates if normalize_text(str(row.get("name") or "")) == normalized_query]
    if len(exact) == 1:
        return exact[0], False
    if len(candidates) == 1:
        return candidates[0], False
    return None, True


def load_city_cache(path: Path = CITY_CACHE_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return payload if isinstance(payload, list) else []


def find_cached_mapping(query: str, path: Path = CITY_CACHE_PATH) -> dict[str, Any] | None:
    normalized = normalize_text(query)
    for row in load_city_cache(path):
        if row.get("normalized_query") == normalized and row.get("id"):
            return row
    return None


def save_city_mapping(
    *,
    query: str,
    id: str,
    legacy_id: str,
    name: str,
    slug: str | None = None,
    country_code: str | None = None,
    path: Path = CITY_CACHE_PATH,
) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [row for row in load_city_cache(path) if row.get("normalized_query") != normalize_text(query)]
    mapping = {
        "query": query,
        "normalized_query": normalize_text(query),
        "id": id,
        "legacy_id": legacy_id,
        "name": name,
        "slug": slug or "",
        "country_code": country_code or "",
        "source": "flixbus_autocomplete",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    rows.append(mapping)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=True), encoding="utf-8")
    return mapping


def mapping_from_result(query: str, result: dict[str, Any], *, path: Path = CITY_CACHE_PATH) -> dict[str, Any]:
    reservation_city_id = str(result.get("id") or "")
    legacy_id = str(result.get("legacy_id") or "")
    name = str(result.get("name") or query)
    return save_city_mapping(
        query=query,
        id=reservation_city_id,
        legacy_id=legacy_id,
        name=name,
        slug=str(result.get("slug") or ""),
        country_code=str(result.get("country_code") or ""),
        path=path,
    )


def payload_error(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    value = payload.get("message") or payload.get("error") or payload.get("detail")
    return str(value)[:300] if value else None


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (compatible; travel-scrapping/1.0)",
        "Accept": "application/json",
    }
