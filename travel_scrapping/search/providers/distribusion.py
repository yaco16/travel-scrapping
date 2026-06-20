from __future__ import annotations

from travel_scrapping.config import Settings
from travel_scrapping.schemas import DealCandidate, Destination
from travel_scrapping.search.providers.base import FlightProvider, ProviderStatus


class DistribusionGroundTransportProvider(FlightProvider):
    name = "distribusion"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.last_attempted = False

    def status(self) -> ProviderStatus:
        key_present = bool(self.settings.distribusion_api_key)
        configured = bool(
            self.settings.distribusion_enabled
            and self.settings.distribusion_api_key
            and self.settings.distribusion_base_url
        )
        warnings: list[str] = []
        if not configured:
            warnings.append("DISTRIBUSION credentials missing")
        return ProviderStatus(
            name=self.name,
            enabled=configured,
            ok=True,
            warnings=warnings,
            key_present=key_present,
            attempted=False,
            request_params={"provider": "distribusion", "modes": "bus,train"},
        )

    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]:
        self.last_attempted = False
        return []
