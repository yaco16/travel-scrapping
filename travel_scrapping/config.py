from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_SEARCH_HORIZON_DAYS = 180


def default_search_end_date() -> date:
    return date.today() + timedelta(days=DEFAULT_SEARCH_HORIZON_DAYS)


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
    search_start_date: date | None = Field(default_factory=date.today)
    search_end_date: date = Field(default_factory=default_search_end_date)
    date_to: date | None = None
    min_nights: int = 1
    max_nights: int = 7
    max_roundtrip_price_eur: int = 150
    max_stops: int = 1
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
    serpapi_targeted_enabled: bool = True
    serpapi_targeted_max_destinations: int = 8
    serpapi_targeted_max_date_pairs: int = 3
    serpapi_airline_targeted_enabled: bool = True
    serpapi_airline_targeted_codes: str = "U2,V7"
    serpapi_airline_targeted_max_destinations: int = 12
    serpapi_airline_targeted_max_date_pairs: int = 3
    api_ninjas_api_key: str = ""
    airport_resolver_order: str = "cache,ourairports,ninja,fallback"
    ourairports_enabled: bool = True
    api_ninjas_enabled: bool = True
    travelpayouts_token: str = ""
    travelpayouts_marker: str = ""
    include_indicative: bool = False
    bus_enabled: bool = True
    ground_max_date_pairs: int = 3
    flixbus_enabled: bool = True
    rapidapi_key: str = ""
    flixbus_rapidapi_host: str = ""
    flixbus_rapidapi_base_url: str = "https://flixbus2.p.rapidapi.com"
    flixbus_debug_save: bool = True
    distribusion_enabled: bool = False
    distribusion_api_key: str = ""
    distribusion_base_url: str = ""
    distribusion_partner_id: str = ""
    comparabus_enabled: bool = True
    comparabus_base_url: str = "https://www.comparabus.com"
    ryanair_enabled: bool = True
    amadeus_client_id: str = ""
    amadeus_client_secret: str = ""
    flixbus_openapi_enabled: bool = True
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
        if self.api_ninjas_enabled and not self.api_ninjas_api_key:
            warnings.append("API_NINJAS_API_KEY missing; API Ninjas airport fallback skipped.")
        if not self.ourairports_enabled:
            warnings.append("OurAirports airport resolver disabled.")
        if self.bus_enabled and self.flixbus_enabled and not self.rapidapi_key:
            warnings.append("RAPIDAPI_KEY missing; FlixBus provider skipped.")
        if not self.travelpayouts_token:
            warnings.append("TRAVELPAYOUTS_TOKEN missing; Travelpayouts provider skipped.")
        if self.travelpayouts_token and not self.travelpayouts_marker:
            warnings.append("Travelpayouts désactivé : TRAVELPAYOUTS_MARKER manquant")
        if not self.amadeus_client_id or not self.amadeus_client_secret:
            warnings.append("AMADEUS_CLIENT_ID/SECRET missing; Amadeus provider skipped.")
        return warnings

    @property
    def effective_search_end_date(self) -> date:
        return self.date_to or self.search_end_date


SECRET_FIELDS = {
    "serpapi_api_key",
    "api_ninjas_api_key",
    "rapidapi_key",
    "travelpayouts_token",
    "travelpayouts_marker",
    "distribusion_api_key",
    "distribusion_partner_id",
    "amadeus_client_id",
    "amadeus_client_secret",
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
