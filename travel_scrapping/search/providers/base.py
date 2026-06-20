from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from travel_scrapping.config import Settings
from travel_scrapping.schemas import DealCandidate, Destination


@dataclass(slots=True)
class ProviderStatus:
    name: str
    enabled: bool
    ok: bool = True
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    key_present: bool = False
    attempted: bool = False
    http_status: int | None = None
    raw_count: int = 0
    normalized_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    main_rejection_reason: str | None = None
    request_params: dict[str, object] = field(default_factory=dict)
    destination_examples: list[str] = field(default_factory=list)


class FlightProvider(ABC):
    name: str

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    def status(self) -> ProviderStatus: ...

    @abstractmethod
    async def search(
        self,
        destinations: list[Destination],
        date_pairs: list[tuple],
        *,
        limit: int,
    ) -> list[DealCandidate]: ...
