from __future__ import annotations

from abc import ABC, abstractmethod

from travel_scrapping.config import Settings
from travel_scrapping.schemas import Offer
from travel_scrapping.search.providers.base import ProviderStatus


class BusProvider(ABC):
    name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def status(self) -> ProviderStatus: ...

    @abstractmethod
    async def station_search(self, query: str) -> list[dict]: ...

    @abstractmethod
    async def search_roundtrip(self, origin: str, destination: str, depart: str, ret: str) -> list[Offer]: ...
