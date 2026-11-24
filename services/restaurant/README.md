# Restaurant Service (Python / FastAPI)

Read-only in-memory catalogue service for restaurants and menu items.

## Purpose
Provides endpoints to list all restaurants, inspect specific restaurant menus, and monitor service health.

## Port
- `8001` (fixed)

## Environment Variables
- None (catalogue is statically seeded in-memory at startup).

## Run Standalone (host with Python)
```zsh
cd services/restaurant
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

## Run Standalone (Docker)
```zsh
docker build -t restaurant-service services/restaurant
docker run --rm -p 8001:8001 restaurant-service
```

## Run Tests
### Host (with pytest)
```zsh
cd services/restaurant && pytest -v
```

### Docker (host without Python)
```zsh
docker run --rm -v "$PWD/services/restaurant:/app" -w /app python:3.12-slim sh -c "pip install -r requirements.txt && pytest -v"
```
