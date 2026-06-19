from fastapi.testclient import TestClient

from travel_scrapping.config import get_settings
from travel_scrapping.main import create_app


def test_dashboard_routes_return_200(tmp_path, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/web.db")
    client = TestClient(create_app())
    for path in ["/", "/search", "/results", "/history"]:
        response = client.get(path)
        assert response.status_code == 200
