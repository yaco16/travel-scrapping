from __future__ import annotations

import html
from datetime import date


def render_email(deals) -> tuple[str, str, str]:
    subject = f"Bons plans vols depuis Nice - {date.today().isoformat()}"
    rows: list[str] = []
    text_rows: list[str] = []
    for deal in deals:
        destination = html.escape(getattr(deal, "destination_airport", ""))
        price = getattr(deal, "total_price_eur", None)
        url = html.escape(getattr(deal, "booking_url", "") or "")
        rows.append(
            f"<tr><td>{destination}</td><td>{deal.outbound_date} - {deal.return_date}</td>"
            f"<td>{price:.2f} EUR</td><td>{html.escape(getattr(deal, 'source', ''))}</td>"
            f"<td>{html.escape(getattr(deal, 'confidence', ''))}</td><td><a href='{url}'>Lien</a></td></tr>"
        )
        text_rows.append(f"{destination} {deal.outbound_date}-{deal.return_date} {price:.2f} EUR")
    disclaimer = "Prix variables; verifier avant reservation."
    html_body = (
        "<h1>Bons plans vols depuis Nice</h1><table>"
        "<tr><th>Destination</th><th>Dates</th><th>Prix</th><th>Source</th><th>Confiance</th><th>Lien</th></tr>"
        + "".join(rows)
        + f"</table><p>{disclaimer}</p>"
    )
    text_body = "\n".join(text_rows + ["", disclaimer])
    return subject, html_body, text_body
