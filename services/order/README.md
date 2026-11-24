# Order Service (Python / FastAPI)

Core order management service validating and persisting customer orders.

## Purpose
Validates order requests against the Restaurant Service catalogue over HTTP, enforces business rules, generates UUID4 order identifiers, and provides in-memory order persistence.

## Port
- `8000` (fixed)

## Environment Variables
- `RESTAURANT_URL`: **Required**. Base URL of the upstream Restaurant Service (e.g., `http://restaurant:8001` in Docker, `http://localhost:8001` standalone).
- `RESTAURANT_TIMEOUT_SECONDS`: Optional. Timeout in seconds for upstream HTTP calls (default `2.0`).

## Run Standalone (host with Python)
```zsh
export RESTAURANT_URL="http://localhost:8001"
cd services/order
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Run Standalone (Docker)
```zsh
docker build -t order-service services/order
docker run --rm -p 8000:8000 -e RESTAURANT_URL="http://host.docker.internal:8001" order-service
```

## Run Tests
### Host (with pytest)
```zsh
cd services/order && pytest -v
```

### Docker (host without Python)
```zsh
docker run --rm -v "$PWD/services/order:/app" -w /app python:3.12-slim sh -c "pip install -r requirements.txt && pytest -v"
```
