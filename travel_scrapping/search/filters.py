from __future__ import annotations

from datetime import date

from travel_scrapping.config import Settings
from travel_scrapping.schemas import DealCandidate


def validate_deal(deal: DealCandidate, settings: Settings, *, today: date | None = None) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    warnings = list(deal.warnings)
    today = today or date.today()
    normalized_nights = (deal.return_date - deal.outbound_date).days
    deal.nights = normalized_nights
    if deal.origin_airport != settings.origin_airport:
        reasons.append("origin mismatch")
    if deal.return_date <= deal.outbound_date or normalized_nights < 1:
        reasons.append("invalid return date")
    if not settings.min_nights <= normalized_nights <= settings.max_nights:
        reasons.append("night range mismatch")
    if deal.return_date > settings.effective_search_end_date:
        reasons.append("return after search end date")
    if deal.outbound_date < today:
        reasons.append("past outbound date")
    if deal.total_price <= 0:
        reasons.append("invalid price")
    if deal.currency != "EUR" and deal.total_price_eur is None:
        reasons.append("non-EUR price without conversion")
    if (deal.total_price_eur or 0) >= settings.max_roundtrip_price_eur:
        reasons.append("over budget")
    if deal.max_layover_hours is not None and deal.max_layover_hours > settings.max_layover_hours:
        reasons.append("layover too long")
    if deal.has_overnight_airport and not settings.allow_overnight_airport:
        reasons.append("overnight airport stay")
    if deal.outbound_duration_hours is not None and deal.outbound_duration_hours > settings.max_air_time_hours:
        reasons.append("outbound air time too long")
    if deal.return_duration_hours is not None and deal.return_duration_hours > settings.max_air_time_hours:
        reasons.append("return air time too long")
    if deal.has_connection and not settings.allow_connections:
        reasons.append("connections disabled")
    if deal.self_transfer and not settings.allow_self_transfer:
        reasons.append("self-transfer disabled")
    if deal.has_connection is None:
        warnings.append("connection status unknown")
    if deal.max_layover_hours is None:
        warnings.append("layover unknown")
    deal.warnings = sorted(set(warnings))
    return not reasons, reasons
