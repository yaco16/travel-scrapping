from __future__ import annotations

from datetime import date, timedelta


def generate_roundtrip_dates(
    *,
    today: date,
    date_to: date,
    min_nights: int,
    max_nights: int,
    allow_return_after_end: bool = False,
) -> list[tuple[date, date, int]]:
    if min_nights < 1 or max_nights < min_nights:
        raise ValueError("invalid night range")
    pairs: list[tuple[date, date, int]] = []
    outbound = today
    while outbound <= date_to:
        for nights in range(min_nights, max_nights + 1):
            ret = outbound + timedelta(days=nights)
            if allow_return_after_end or ret <= date_to:
                pairs.append((outbound, ret, nights))
        outbound += timedelta(days=1)
    return pairs
