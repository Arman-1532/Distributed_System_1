import logging
import time
import uuid
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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

SEED_RESTAURANTS = [
    {
        "id": 1,
        "name": "Burger House",
        "address": "123 Main St, Springfield",
        "items": [
            {"id": 101, "name": "Classic Burger", "price": 9.99, "available": True},
            {"id": 102, "name": "Chicken Burger", "price": 10.99, "available": True},
        ],
    },
    {
        "id": 2,
        "name": "Pizza Corner",
        "address": "456 Elm St, Springfield",
        "items": [
            {"id": 201, "name": "Margherita Pizza", "price": 12.50, "available": True},
            {"id": 202, "name": "Pepperoni Pizza", "price": 14.00, "available": True},
        ],
    },
    {
        "id": 3,
        "name": "Sushi World",
        "address": "789 Ocean Ave, Springfield",
        "items": [
            {"id": 301, "name": "California Roll", "price": 8.50, "available": True},
            {"id": 302, "name": "Salmon Roll", "price": 11.00, "available": True},
        ],
    },
]

app = FastAPI(title="Restaurant Service")


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
        logging.getLogger("restaurant").info(
            f"request completed method={request.method} path={request.url.path} status={response.status_code} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
        return response
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logging.getLogger("restaurant").error(
            f"unhandled error method={request.method} path={request.url.path} error={exc} elapsed_ms={elapsed_ms}",
            extra=extra,
        )
        return error_response(500, "INTERNAL_ERROR", "internal server error", corr_id)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/restaurants")
async def list_restaurants():
    return SEED_RESTAURANTS


@app.get("/restaurants/{id}")
async def get_restaurant(id: str, request: Request):
    corr_id = getattr(request.state, "correlation_id", str(uuid.uuid4()))
    try:
        restaurant_id = int(id)
        if restaurant_id <= 0:
            return error_response(400, "INVALID_REQUEST", "invalid restaurant id in path", corr_id)
    except ValueError:
        return error_response(400, "INVALID_REQUEST", "invalid restaurant id in path", corr_id)

    for rest in SEED_RESTAURANTS:
        if rest["id"] == restaurant_id:
            return rest

    return error_response(404, "RESTAURANT_NOT_FOUND", "restaurant not found", corr_id)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8001)
