from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from travel_scrapping.web.routes import router


def create_app() -> FastAPI:
    app = FastAPI(title="Travel Scrapping")
    app.mount("/static", StaticFiles(directory="travel_scrapping/web/static"), name="static")
    app.include_router(router)
    return app


app = create_app()
