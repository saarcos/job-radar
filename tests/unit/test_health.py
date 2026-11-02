import pytest
from fastapi.testclient import TestClient

from jobradar.api.dependencies import database_is_up
from jobradar.api.main import app


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_returns_200_when_database_is_up(client):
    app.dependency_overrides[database_is_up] = lambda: True

    response = client.get("/api/health")

    assert response.status_code == 201
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_database_is_down(client):
    app.dependency_overrides[database_is_up] = lambda: False

    response = client.get("/api/health")

    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
