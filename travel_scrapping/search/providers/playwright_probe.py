from __future__ import annotations

from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus
from travel_scrapping.schemas import DealCandidate, Destination


class PlaywrightProbeProvider(FlightProvider):
    name = "playwright_probe"

    def status(self) -> ProviderStatus:
        if not self.settings.playwright_enabled or not self.settings.scraping_enabled:
            return ProviderStatus(self.name, enabled=False, warnings=["Playwright scraping disabled"])
        return ProviderStatus(
            self.name,
            enabled=False,
            warnings=["Safe probe skeleton only; no captcha, login, proxy, or anti-bot bypass"],
        )

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        return []
