from fastapi.testclient import TestClient
from main import app, SEED_RESTAURANTS

client = TestClient(app)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Correlation-ID" in response.headers


def test_list_restaurants():
    response = client.get("/restaurants")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["name"] == "Burger House"


def test_get_restaurant_by_id():
    response = client.get("/restaurants/1")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["name"] == "Burger House"
    assert len(data["items"]) == 2


def test_get_restaurant_unknown_id():
    response = client.get("/restaurants/999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "RESTAURANT_NOT_FOUND"
    assert data["error"]["message"] == "restaurant not found"
    assert "correlation_id" in data["error"]


def test_get_restaurant_non_integer_id():
    response = client.get("/restaurants/abc")
    assert response.status_code == 400
    data = response.json()
    assert data["error"]["code"] == "INVALID_REQUEST"
    assert data["error"]["message"] == "invalid restaurant id in path"


def test_seed_catalogue_requirements():
    assert len(SEED_RESTAURANTS) >= 3
    total_items = sum(len(r["items"]) for r in SEED_RESTAURANTS)
    assert total_items >= 6
