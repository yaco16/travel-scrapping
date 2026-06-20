# TODO

- Verifier abonnement/quota RapidAPI Flixbus2: l'API retourne `403/429` malgre `RAPIDAPI_KEY`.
- Relancer `.venv/bin/python -m travel_scrapping.cli bus-stations-search --query "Nice"` apres correction RapidAPI.
- Relancer `.venv/bin/python -m travel_scrapping.cli flixbus-smoke --origin "Nice" --destination "Venise" --depart 2026-07-30 --return 2026-08-02 --debug`.
- Relancer un E2E bus limite et verifier offres FlixBus actionnables en SQLite/diagnostics.
