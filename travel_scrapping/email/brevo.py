from __future__ import annotations

import httpx

from travel_scrapping.config import Settings
from travel_scrapping.email.renderer import render_email


def email_enabled(settings: Settings) -> tuple[bool, str | None]:
    if not settings.brevo_api_key:
        return False, "BREVO_API_KEY missing"
    if not settings.email_from:
        return False, "EMAIL_FROM missing"
    return True, None


async def send_deals_email(settings: Settings, deals) -> dict:
    enabled, reason = email_enabled(settings)
    if not enabled:
        return {"sent": False, "reason": reason}
    subject, html_body, text_body = render_email(deals)
    payload = {
        "sender": {"name": settings.email_from_name, "email": settings.email_from},
        "to": [{"email": settings.email_to}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.brevo_api_key, "content-type": "application/json"},
            json=payload,
        )
        response.raise_for_status()
        return {"sent": True, "response": response.json() if response.content else {}}
