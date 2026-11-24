import os
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import httpx
import pytest
from fastapi.testclient import TestClient

# Ensure RESTAURANT_URL is set before importing app
os.environ["RESTAURANT_URL"] = "http://fake-restaurant:8001"
from main import app, repository

client = TestClient(app)


def fake_restaurant_response(status_code=200, json_data=None):
    if json_data is None:
        json_data = {
            "id": 1,
            "name": "Burger House",
            "items": [
                {"id": 101, "name": "Classic Burger", "price": 9.99, "available": True},
                {"id": 102, "name": "Chicken Burger", "price": 10.99, "available": False},
            ],
        }
    return httpx.Response(
        status_code=status_code,
        json=json_data,
        request=httpx.Request("GET", "http://fake-restaurant:8001/restaurants/1"),
    )


def test_order_success_and_retrieval():
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response()):
        payload = {"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 2}]}
        resp = client.post("/orders", json=payload)
        assert resp.status_code == 201

        data = resp.json()
        assert set(data.keys()) == {"order_id", "status", "created_at"}
        assert data["order_id"].startswith("ord-")
        assert data["status"] == "created"
        assert data["created_at"].endswith("Z")

        order_id = data["order_id"]
        get_resp = client.get(f"/orders/{order_id}")
        assert get_resp.status_code == 200
        get_data = get_resp.json()
        assert get_data["order_id"] == order_id
        assert get_data["restaurant_id"] == 1
        assert len(get_data["items"]) == 1
        assert get_data["items"][0] == {"menu_item_id": 101, "quantity": 2}
        assert "correlation_id" in get_data


def test_get_unknown_order():
    resp = client.get("/orders/ord-nonexistent")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "ORDER_NOT_FOUND"
    assert data["error"]["message"] == "order not found"


def test_validation_errors():
    initial_count = repository.count()

    cases = [
        ("bad quantity zero", '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 0}]}'),
        ("bad quantity negative", '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": -5}]}'),
        ("bad quantity string", '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": "2"}]}'),
        ("missing restaurant_id", '{"items": [{"menu_item_id": 101, "quantity": 1}]}'),
        ("non-positive restaurant_id", '{"restaurant_id": 0, "items": [{"menu_item_id": 101, "quantity": 1}]}'),
        ("missing menu_item_id", '{"restaurant_id": 1, "items": [{"quantity": 1}]}'),
        ("non-positive menu_item_id", '{"restaurant_id": 1, "items": [{"menu_item_id": 0, "quantity": 1}]}'),
        ("missing quantity", '{"restaurant_id": 1, "items": [{"menu_item_id": 101}]}'),
        ("empty items list", '{"restaurant_id": 1, "items": []}'),
        ("missing items array", '{"restaurant_id": 1}'),
        ("malformed JSON syntax", '{"restaurant_id": 1, "items": ['),
        (
            "duplicate menu_item_id",
            '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}, {"menu_item_id": 101, "quantity": 2}]}',
        ),
        (
            "trailing data after JSON",
            '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]} extra',
        ),
    ]

    for name, payload in cases:
        resp = client.post("/orders", content=payload, headers={"Content-Type": "application/json"})
        assert resp.status_code == 400, f"Failed case {name}: got {resp.status_code}"
        data = resp.json()
        assert data["error"]["code"] == "INVALID_REQUEST", f"Failed code for {name}"
        assert "correlation_id" in data["error"]

    assert repository.count() == initial_count


def test_dependency_errors():
    # 404 Restaurant Not Found
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response(status_code=404)):
        resp = client.post("/orders", json={"restaurant_id": 999, "items": [{"menu_item_id": 101, "quantity": 1}]})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "RESTAURANT_NOT_FOUND"

    # 404 Menu Item Not Found
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response()):
        resp = client.post("/orders", json={"restaurant_id": 1, "items": [{"menu_item_id": 999, "quantity": 1}]})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "MENU_ITEM_NOT_FOUND"

    # 409 Menu Item Unavailable
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response()):
        resp = client.post("/orders", json={"restaurant_id": 1, "items": [{"menu_item_id": 102, "quantity": 1}]})
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "MENU_ITEM_UNAVAILABLE"

    # 503 Downstream connection error
    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("connection refused")):
        resp = client.post("/orders", json={"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "RESTAURANT_SERVICE_UNAVAILABLE"

    # 503 Downstream timeout
    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("request timed out")):
        resp = client.post("/orders", json={"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "RESTAURANT_SERVICE_UNAVAILABLE"

    # 503 Downstream 500
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response(status_code=500)):
        resp = client.post("/orders", json={"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]})
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "RESTAURANT_SERVICE_UNAVAILABLE"

    # Healthz still 200 during downstream outage
    health_resp = client.get("/healthz")
    assert health_resp.status_code == 200
    assert health_resp.json() == {"status": "ok"}


def test_correlation_headers():
    custom_id = "test-custom-correlation-999"
    with patch("httpx.AsyncClient.get", return_value=fake_restaurant_response()) as mock_get:
        resp = client.post(
            "/orders",
            json={"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]},
            headers={"X-Correlation-ID": custom_id},
        )
        assert resp.status_code == 201
        assert resp.headers.get("X-Correlation-ID") == custom_id

        # Check header forwarded downstream
        _, kwargs = mock_get.call_args
        assert kwargs["headers"].get("X-Correlation-ID") == custom_id


def test_concurrency():
    concurrent_requests = 20

    async def fake_delayed_get(*args, **kwargs):
        time.sleep(0.01)
        return fake_restaurant_response()

    def send_order(i):
        return client.post(
            "/orders",
            json={"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]},
        )

    start_count = repository.count()
    with patch("httpx.AsyncClient.get", side_effect=fake_delayed_get):
        with ThreadPoolExecutor(max_workers=concurrent_requests) as executor:
            results = list(executor.map(send_order, range(concurrent_requests)))

    assert len(results) == concurrent_requests
    order_ids = set()
    for resp in results:
        assert resp.status_code == 201
        data = resp.json()
        order_ids.add(data["order_id"])

    assert len(order_ids) == concurrent_requests
    assert repository.count() == start_count + concurrent_requests
