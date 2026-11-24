import copy
from datetime import datetime, timezone
import json
import logging
import os
import sys
import threading
import time
import uuid
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

class CorrelationFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return True

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [correlation_id=%(correlation_id)s] %(message)s",
)
for handler in logging.root.handlers:
    handler.addFilter(CorrelationFilter())

RESTAURANT_URL = os.getenv("RESTAURANT_URL", "").strip().rstrip("/")
if not RESTAURANT_URL:
    logging.error("missing required environment variable: RESTAURANT_URL")
    # Only exit if not in test environment
    if "pytest" not in sys.modules:
        sys.exit(1)

try:
    RESTAURANT_TIMEOUT_SECONDS = float(os.getenv("RESTAURANT_TIMEOUT_SECONDS", "2.0"))
except ValueError:
    RESTAURANT_TIMEOUT_SECONDS = 2.0


class OrderRepository:
    def __init__(self):
        self._lock = threading.Lock()
        self._orders: dict[str, dict[str, Any]] = {}

    def add(self, order: dict[str, Any]) -> None:
        with self._lock:
            self._orders[order["order_id"]] = copy.deepcopy(order)

    def get(self, order_id: str) -> dict[str, Any] | None:
        with self._lock:
            order = self._orders.get(order_id)
            return copy.deepcopy(order) if order else None

    def count(self) -> int:
        with self._lock:
            return len(self._orders)


repository = OrderRepository()
app = FastAPI(title="Order Service")


def error_response(status_code: int, code: str, message: str, correlation_id: str) -> JSONResponse:
    content = {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": correlation_id,
        }
    }
    response = JSONResponse(status_code=status_code, content=content)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    corr_id = request.headers.get("X-Correlation-ID")
    if not corr_id or not corr_id.strip():
        corr_id = str(uuid.uuid4())
    request.state.correlation_id = corr_id

    extra = {"correlation_id": corr_id}
    start = time.perf_counter()

    try:
        response = await call_next(request)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Correlation-ID"] = corr_id
        logging.getLogger("order").info(
            f"request completed method={request.method} path={request.url.path} status={response.status_code} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
        return response
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.getLogger("order").error(
            f"unhandled error method={request.method} path={request.url.path} error={exc} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
        return error_response(500, "INTERNAL_ERROR", "internal server error", corr_id)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
async def create_order(request: Request):
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    extra = {"correlation_id": corr_id}

    # Raw body decode to strictly catch malformed JSON and trailing data
    body_bytes = await request.body()
    body_str = body_bytes.decode("utf-8", errors="replace").strip()
    if not body_str:
        return error_response(400, "INVALID_REQUEST", "malformed JSON request body", corr_id)

    decoder = json.JSONDecoder()
    try:
        data, end = decoder.raw_decode(body_str)
    except Exception:
        return error_response(400, "INVALID_REQUEST", "malformed JSON request body", corr_id)

    if end < len(body_str) and body_str[end:].strip():
        return error_response(400, "INVALID_REQUEST", "unexpected trailing data after JSON body", corr_id)

    if not isinstance(data, dict):
        return error_response(400, "INVALID_REQUEST", "invalid JSON data type", corr_id)

    # Validate restaurant_id
    if "restaurant_id" not in data or data["restaurant_id"] is None:
        return error_response(400, "INVALID_REQUEST", "missing restaurant_id", corr_id)

    rest_id_raw = data["restaurant_id"]
    if not isinstance(rest_id_raw, int) or isinstance(rest_id_raw, bool):
        return error_response(400, "INVALID_REQUEST", "invalid JSON data type", corr_id)

    if rest_id_raw <= 0:
        return error_response(400, "INVALID_REQUEST", "restaurant_id must be greater than 0", corr_id)

    restaurant_id = rest_id_raw

    # Validate items list
    if "items" not in data or data["items"] is None:
        return error_response(400, "INVALID_REQUEST", "items list cannot be empty", corr_id)

    items_raw = data["items"]
    if not isinstance(items_raw, list) or len(items_raw) == 0:
        return error_response(400, "INVALID_REQUEST", "items list cannot be empty", corr_id)

    validated_items = []   # ordered items
    seen_menu_items = set()

    for item in items_raw:
        if not isinstance(item, dict):
            return error_response(400, "INVALID_REQUEST", "invalid JSON data type", corr_id)

        if "menu_item_id" not in item or item["menu_item_id"] is None:
            return error_response(400, "INVALID_REQUEST", "missing menu_item_id", corr_id)
        mid_raw = item["menu_item_id"]
        if not isinstance(mid_raw, int) or isinstance(mid_raw, bool):
            return error_response(400, "INVALID_REQUEST", "invalid JSON data type", corr_id)
        if mid_raw <= 0:
            return error_response(400, "INVALID_REQUEST", "menu_item_id must be greater than 0", corr_id)

        if "quantity" not in item or item["quantity"] is None:
            return error_response(400, "INVALID_REQUEST", "missing quantity", corr_id)
        qty_raw = item["quantity"]
        if not isinstance(qty_raw, int) or isinstance(qty_raw, bool):
            return error_response(400, "INVALID_REQUEST", "invalid JSON data type", corr_id)
        if qty_raw < 1:
            return error_response(400, "INVALID_REQUEST", "quantity must be at least 1", corr_id)

        if mid_raw in seen_menu_items:
            return error_response(400, "INVALID_REQUEST", "duplicate menu_item_id in items list", corr_id)

        seen_menu_items.add(mid_raw)
        validated_items.append({"menu_item_id": mid_raw, "quantity": qty_raw})

    # Outbound HTTP call to Restaurant Service
    rest_url = os.getenv("RESTAURANT_URL", "").strip().rstrip("/")
    if not rest_url:
        return error_response(503, "RESTAURANT_SERVICE_UNAVAILABLE", "restaurant service unavailable", corr_id)

    target_url = f"{rest_url}/restaurants/{restaurant_id}"
    timeout = httpx.Timeout(RESTAURANT_TIMEOUT_SECONDS, connect=1.0)
    headers = {"X-Correlation-ID": corr_id}

    start = time.perf_counter()

    #checks whether the restaurant exist or not
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(target_url, headers=headers)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.getLogger("order").info(
            f"outbound call to restaurant service completed status={resp.status_code} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.getLogger("order").error(
            f"outbound call to restaurant service failed error={exc} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
        return error_response(503, "RESTAURANT_SERVICE_UNAVAILABLE", "restaurant service unavailable", corr_id)

    if resp.status_code == 404:
        return error_response(404, "RESTAURANT_NOT_FOUND", "restaurant not found", corr_id)
    if resp.status_code != 200:
        return error_response(503, "RESTAURANT_SERVICE_UNAVAILABLE", "restaurant service unavailable", corr_id)

    try:
        restaurant_data = resp.json()
    except Exception:
        return error_response(503, "RESTAURANT_SERVICE_UNAVAILABLE", "restaurant service unavailable", corr_id)

    # ki ki items pawa jaay
    restaurant_items = {it["id"]: it for it in restaurant_data.get("items", [])}


    # checks if ordered items exist in restaurant
    for it in validated_items:
        mid = it["menu_item_id"]
        if mid not in restaurant_items:
            return error_response(404, "MENU_ITEM_NOT_FOUND", "menu item not found in restaurant menu", corr_id)
        if not restaurant_items[mid].get("available", True):
            return error_response(409, "MENU_ITEM_UNAVAILABLE", "menu item is currently unavailable", corr_id)

    # Persist order
    order_id = f"ord-{uuid.uuid4()}"
    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    order_record = {
        "order_id": order_id,
        "status": "created",
        "created_at": created_at,
        "restaurant_id": restaurant_id,
        "items": validated_items,
        "correlation_id": corr_id,
    }

    #creates order
    repository.add(order_record)

    logging.getLogger("order").info(
        f"order created successfully order_id={order_id} restaurant_id={restaurant_id} item_count={len(validated_items)}",
        extra=extra,
    )

    # Exactly these three fields in 201 response
    content = {
        "order_id": order_id,
        "status": "created",
        "created_at": created_at,
    }
    response = JSONResponse(status_code=201, content=content)
    response.headers["X-Correlation-ID"] = corr_id
    return response


@app.get("/orders/{id}")
async def get_order(id: str, request: Request):
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    order = repository.get(id)
    if not order:
        return error_response(404, "ORDER_NOT_FOUND", "order not found", corr_id)

    response = JSONResponse(status_code=200, content=order)
    response.headers["X-Correlation-ID"] = corr_id
    return response


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
