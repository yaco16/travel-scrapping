from datetime import date

from travel_scrapping.config import Settings, mask_secret, safe_settings_dict


def test_config_defaults_and_masking():
    settings = Settings(_env_file=None, serpapi_api_key="abcdef")
    assert settings.origin_airport == "NCE"
    assert settings.search_end_date == date(2026, 8, 31)
    assert settings.effective_search_end_date == date(2026, 8, 31)
    assert settings.email_to == "kwad16@gmail.com"
    assert mask_secret("abcdef") == "ab****ef"
    assert safe_settings_dict(settings)["serpapi_api_key"] == "ab****ef"
    assert "abcdef" not in str(safe_settings_dict(settings))


def test_email_warning_when_sender_missing():
    settings = Settings(_env_file=None, email_enabled=True, brevo_api_key="x", email_from="")
    assert "EMAIL_FROM missing; email sending disabled." in settings.warnings()


def test_email_disabled_by_default():
    assert Settings(_env_file=None).email_enabled is False


def test_deprecated_date_to_overrides_effective_search_end_date():
    settings = Settings(_env_file=None, date_to=date(2026, 8, 30))
    assert settings.effective_search_end_date == date(2026, 8, 30)
