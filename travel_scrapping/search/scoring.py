from __future__ import annotations

from travel_scrapping.schemas import DealCandidate


CONFIDENCE_SCORE = {"high": 0, "medium": 1, "low": 2}


def duration_score(deal: DealCandidate) -> float:
    return (deal.outbound_duration_hours or 99) + (deal.return_duration_hours or 99)


def sort_deals(deals: list[DealCandidate]) -> list[DealCandidate]:
    return sorted(
        deals,
        key=lambda d: (
            d.total_price_eur if d.total_price_eur is not None else float("inf"),
            CONFIDENCE_SCORE[d.confidence],
            0 if d.is_direct else 1,
            duration_score(d),
            len(d.warnings),
            d.outbound_date,
        ),
    )
