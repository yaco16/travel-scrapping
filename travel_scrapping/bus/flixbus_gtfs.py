from __future__ import annotations

import csv
import io
import unicodedata
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

GTFS_URL = "http://gtfs.gis.flix.tech/gtfs_generic_eu.zip"
GTFS_CACHE_PATH = Path("data/gtfs/flixbus/gtfs_generic_eu.zip")
EXPECTED_FILES = ("stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "calendar.txt")


@dataclass(frozen=True)
class GtfsInfo:
    path: Path
    present: bool
    downloaded_at: datetime | None
    size_bytes: int | None
    files_present: dict[str, bool]
    stops_count: int
    routes_count: int
    trips_count: int
    valid_from: str | None
    valid_until: str | None
    nice_examples: list[dict[str, str]]
    paris_examples: list[dict[str, str]]
    error: str | None = None


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.casefold().split())


def refresh_gtfs(url: str = GTFS_URL, path: Path = GTFS_CACHE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    response = httpx.get(url, timeout=120, follow_redirects=True)
    response.raise_for_status()
    path.write_bytes(response.content)
    return path


def gtfs_info(path: Path = GTFS_CACHE_PATH) -> GtfsInfo:
    if not path.exists():
        return GtfsInfo(
            path=path,
            present=False,
            downloaded_at=None,
            size_bytes=None,
            files_present={name: False for name in (*EXPECTED_FILES, "feed_info.txt")},
            stops_count=0,
            routes_count=0,
            trips_count=0,
            valid_from=None,
            valid_until=None,
            nice_examples=[],
            paris_examples=[],
        )
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            files_present = {name: name in names for name in (*EXPECTED_FILES, "feed_info.txt")}
            stops = read_csv_rows(archive, "stops.txt")
            routes_count = count_rows(archive, "routes.txt")
            trips_count = count_rows(archive, "trips.txt")
            valid_from, valid_until = calendar_period(archive)
            return GtfsInfo(
                path=path,
                present=True,
                downloaded_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                size_bytes=path.stat().st_size,
                files_present=files_present,
                stops_count=len(stops),
                routes_count=routes_count,
                trips_count=trips_count,
                valid_from=valid_from,
                valid_until=valid_until,
                nice_examples=search_stops_in_rows(stops, "Nice")[:5],
                paris_examples=search_stops_in_rows(stops, "Paris")[:5],
            )
    except (OSError, zipfile.BadZipFile, UnicodeDecodeError, csv.Error) as exc:
        return GtfsInfo(
            path=path,
            present=True,
            downloaded_at=datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            size_bytes=path.stat().st_size,
            files_present={name: False for name in (*EXPECTED_FILES, "feed_info.txt")},
            stops_count=0,
            routes_count=0,
            trips_count=0,
            valid_from=None,
            valid_until=None,
            nice_examples=[],
            paris_examples=[],
            error=str(exc)[:300],
        )


def search_stops(query: str, path: Path = GTFS_CACHE_PATH, limit: int = 50) -> list[dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        return search_stops_in_rows(read_csv_rows(archive, "stops.txt"), query)[:limit]


def search_stops_in_rows(rows: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    normalized_query = normalize_text(query)
    exact: list[dict[str, str]] = []
    partial: list[dict[str, str]] = []
    for row in rows:
        name = row.get("stop_name", "")
        normalized_name = normalize_text(name)
        result = {
            "stop_id": row.get("stop_id", ""),
            "stop_name": name,
            "stop_lat": row.get("stop_lat", ""),
            "stop_lon": row.get("stop_lon", ""),
            "location_type": row.get("location_type", ""),
            "parent_station": row.get("parent_station", ""),
        }
        if normalized_name == normalized_query:
            exact.append(result)
        elif normalized_query and normalized_query in normalized_name:
            partial.append(result)
    return exact + partial


def read_csv_rows(archive: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    if name not in archive.namelist():
        return []
    with archive.open(name) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
        return [dict(row) for row in csv.DictReader(text)]


def count_rows(archive: zipfile.ZipFile, name: str) -> int:
    if name not in archive.namelist():
        return 0
    with archive.open(name) as handle:
        text = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
        reader = csv.reader(text)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _row in reader)


def calendar_period(archive: zipfile.ZipFile) -> tuple[str | None, str | None]:
    rows = read_csv_rows(archive, "calendar.txt")
    starts = [row.get("start_date", "") for row in rows if row.get("start_date")]
    ends = [row.get("end_date", "") for row in rows if row.get("end_date")]
    return (min(starts) if starts else None, max(ends) if ends else None)


def stop_public_fields(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stop_id": row.get("stop_id", ""),
        "stop_name": row.get("stop_name", ""),
        "stop_lat": row.get("stop_lat", ""),
        "stop_lon": row.get("stop_lon", ""),
        "location_type": row.get("location_type", ""),
        "parent_station": row.get("parent_station", ""),
    }
