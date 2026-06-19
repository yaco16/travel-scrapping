from datetime import date

import pytest
import respx
from httpx import Response

from travel_scrapping.config import Settings
from travel_scrapping.email.brevo import email_enabled, send_deals_email
from travel_scrapping.email.renderer import render_email
from travel_scrapping.schemas import DealCandidate


def test_email_disabled_without_sender():
    enabled, reason = email_enabled(Settings(_env_file=None, brevo_api_key="x", email_from=""))
    assert not enabled
    assert reason == "EMAIL_FROM missing"


def test_render_email():
    deal = DealCandidate(
        source="serpapi",
        origin_airport="NCE",
        destination_airport="BCN",
        outbound_date=date(2026, 7, 1),
        return_date=date(2026, 7, 4),
        nights=3,
        total_price=42,
        confidence="high",
    )
    subject, html, text = render_email([deal])
    assert "Bons plans vols depuis Nice" in subject
    assert "BCN" in html
    assert "Prix variables" in text


@pytest.mark.asyncio
@respx.mock
async def test_brevo_request_construction():
    route = respx.post("https://api.brevo.com/v3/smtp/email").mock(return_value=Response(201, json={"id": "1"}))
    settings = Settings(_env_file=None, brevo_api_key="secret", email_from="from@example.com", email_to="to@example.com")
    result = await send_deals_email(settings, [])
    assert result["sent"]
    sent = route.calls[0].request
    assert sent.headers["api-key"] == "secret"
    assert b"to@example.com" in sent.content
