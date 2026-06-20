from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "sqlite:///./data/travel_scrapping.db"

    origin_airport: str = "NCE"
    default_currency: str = "EUR"
    default_locale: str = "fr-FR"
    default_market: str = "FR"
    search_end_date: date = date(2026, 8, 30)
    date_to: date | None = None
    min_nights: int = 3
    max_nights: int = 5
    max_roundtrip_price_eur: float = 100
    max_air_time_hours: float = 5
    max_layover_hours: float = 3
    allow_direct: bool = True
    allow_connections: bool = True
    allow_self_transfer: bool = True
    allow_overnight_airport: bool = False
    adults: int = 1
    cabin_bags: int = 0
    checked_bags: int = 0
    personal_item_only: bool = True
    top_results_limit: int = 50

    serpapi_api_key: str = ""
    api_ninjas_api_key: str = ""
    travelpayouts_token: str = ""
    travelpayouts_marker: str = ""
    kiwi_tequila_api_key: str = ""
    brevo_api_key: str = ""
    email_enabled: bool = False
    email_from: str = ""
    email_from_name: str = "Travel Scrapping"
    email_to: str = "kwad16@gmail.com"
    playwright_enabled: bool = True
    scraping_enabled: bool = True
    git_auto_commit: bool = True

    @field_validator("origin_airport", "default_currency")
    @classmethod
    def uppercase(cls, value: str) -> str:
        return value.upper()

    def warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.app_host == "0.0.0.0":
            warnings.append("App exposed on 0.0.0.0 without authentication.")
        if self.date_to is not None:
            warnings.append("DATE_TO is deprecated; use SEARCH_END_DATE.")
        if self.email_enabled and not self.email_from:
            warnings.append("EMAIL_FROM missing; email sending disabled.")
        if self.email_enabled and not self.brevo_api_key:
            warnings.append("BREVO_API_KEY missing; email sending disabled.")
        if not self.serpapi_api_key:
            warnings.append("SERPAPI_API_KEY missing; SerpAPI provider skipped.")
        if not self.travelpayouts_token:
            warnings.append("TRAVELPAYOUTS_TOKEN missing; Travelpayouts provider skipped.")
        if self.travelpayouts_token and not self.travelpayouts_marker:
            warnings.append("TRAVELPAYOUTS_MARKER missing; marker-required endpoints disabled.")
        return warnings

    @property
    def effective_search_end_date(self) -> date:
        return self.date_to or self.search_end_date


SECRET_FIELDS = {
    "serpapi_api_key",
    "api_ninjas_api_key",
    "travelpayouts_token",
    "travelpayouts_marker",
    "kiwi_tequila_api_key",
    "brevo_api_key",
}


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 4:
        return "****"
    return f"{value[:2]}****{value[-2:]}"


def safe_settings_dict(settings: Settings) -> dict[str, Any]:
    data = settings.model_dump(mode="json")
    for field in SECRET_FIELDS:
        data[field] = mask_secret(str(data.get(field, "")))
    return data


@lru_cache
def get_settings() -> Settings:
    return Settings()
