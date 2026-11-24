# Containerized Order and Restaurant Services (Python / FastAPI)

A decoupled two-service microservice application built with **Python 3.12** and **FastAPI**, containerized using multi-stage Dockerfiles, and orchestrated with **Docker Compose v2** for macOS (`zsh` on Apple Silicon).

---

## 1. System Overview

This application simulates a distributed food ordering workflow across two independent services communicating strictly over HTTP:

- **Restaurant Service (`:8001`)**: A read-only catalogue service storing restaurant profiles and menu items in memory, statically seeded at startup.
- **Order Service (`:8000`)**: An order management service that validates customer order submissions against the Restaurant Service catalogue over HTTP, enforces business rules, generates unique identifiers, and persists orders in a thread-safe in-memory store.

```
+----------------+           HTTP (:8001)           +--------------------+
|  Order Client  | ----> [ Order Service :8000 ] --> | Restaurant Service |
|  (curl/script) |       (validates & stores)        |  (catalogue :8001) |
+----------------+                                   +--------------------+
```

For step-by-step commands to demonstrate or grade the system, see [CHEATSHEET.md](CHEATSHEET.md).

---

## 2. Key Architectural Decisions

1. **Strict Service Decoupling**:
   - Order Service and Restaurant Service are completely independent services.
   - The Order Service never imports Restaurant code, classes, or database models. All inter-service communication happens over real HTTP calls.
2. **Mutex-Protected Concurrency**:
   - The Order Service manages state in memory using an `OrderRepository` guarded by a mutual exclusion primitive (`threading.Lock`).
   - The mutex is acquired **only** during quick dictionary additions or lookups and is **never** held across network HTTP calls, preventing concurrency bottlenecks.
3. **Strict Validation & Error Mapping**:
   - Raw JSON request payloads are strictly parsed to catch malformed syntax, extra trailing data, missing fields, invalid data types (e.g. `"2"`, `2.5`, `True`), empty items, non-positive numbers, and duplicate menu items.
   - All errors return a standardized JSON format:
     ```json
     {
       "error": {
         "code": "<CODE>",
         "message": "<safe message>",
         "correlation_id": "<id>"
       }
     }
     ```
4. **Distributed Correlation Tracing**:
   - Every request is tagged with an `X-Correlation-ID`.
   - Incoming headers are preserved; if missing, a new UUIDv4 is generated.
   - The correlation ID is propagated downstream from Order Service to Restaurant Service, echoed in response headers, and included on every log line.
5. **In-Memory Limitation**:
   - Both services use process-local memory. State is reset when containers restart. Persistent distributed storage (PostgreSQL) is planned for Assignment 2.

---

## 3. Tech Stack

- **Language & Framework**: Python 3.12, FastAPI, Uvicorn (ASGI server).
- **HTTP Client**: HTTPX (async client with explicit connection and request timeouts).
- **Testing**: Pytest (FastAPI `TestClient` for unit and integration testing).
- **Containerization**: Multi-stage `python:3.12-slim` Dockerfiles with built-in healthchecks.
- **Orchestration**: Docker Compose v2 with a user-defined bridge network (`order-restaurant-net`).

---

## 4. Directory Structure

```
.
├── CHEATSHEET.md             # Copy-pasteable presentation run sheet
├── README.md                 # Project architecture & system documentation
├── docker-compose.yml        # Multi-service container orchestration
├── docs/
│   ├── api-contract.md       # Formal API specifications & status tables
│   ├── failure-experiment.md # Downstream outage & recovery experiment report
│   ├── logs/
│   │   └── outage-experiment.log  # Raw container logs from the experiment
│   └── request-examples.md   # Copy-pasteable curl examples with real outputs
├── scripts/
│   └── test-concurrency/
│       └── main.py           # Automated 20-request concurrency verification script
└── services/
    ├── order/
    │   ├── Dockerfile
    │   ├── README.md
    │   ├── main.py           # Order service entrypoint & business logic
    │   ├── requirements.txt
    │   └── test_orders.py    # Automated test suite for Order Service
    └── restaurant/
        ├── Dockerfile
        ├── README.md
        ├── main.py           # Restaurant service entrypoint & catalogue
        ├── requirements.txt
        └── test_restaurant.py # Automated test suite for Restaurant Service
```

---

## 5. Environment Variables

| Service | Variable | Required | Default | Description |
|---|---|---|---|---|
| Order | `RESTAURANT_URL` | **Yes** | *None* | Base URL of upstream Restaurant Service (`http://restaurant:8001` in Compose, `http://localhost:8001` standalone). |
| Order | `RESTAURANT_TIMEOUT_SECONDS` | No | `2.0` | Timeout in seconds for upstream HTTP calls. |
| Restaurant | *None* | No | *N/A* | Catalogue is statically seeded in-memory at startup. |

---

## 6. API Endpoints

### Restaurant Service (`http://localhost:8001`)
| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/healthz` | Service health check | `200 OK` |
| `GET` | `/restaurants` | List all seeded restaurants and menus | `200 OK` |
| `GET` | `/restaurants/{id}` | Get restaurant details by integer ID | `200 OK`, `400 Bad Request`, `404 Not Found` |

### Order Service (`http://localhost:8000`)
| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/healthz` | Independent liveness probe | `200 OK` |
| `POST` | `/orders` | Validate and create an order | `201 Created`, `400 Bad Request`, `404 Not Found`, `409 Conflict`, `503 Service Unavailable` |
| `GET` | `/orders/{id}` | Retrieve order details by ID | `200 OK`, `404 Not Found` |

---

## 7. Quick Start

### 7.1 Using Docker Compose (Recommended)

```zsh
# Build images and start containers
docker compose up --build -d

# Verify container health status
docker compose ps

# Run automated tests in Docker
docker run --rm restaurant-service pytest -v
docker run --rm order-service pytest -v

# Run the 20-request concurrency verification script
docker run --rm --network order-restaurant-net -v "$PWD/scripts/test-concurrency:/src" -w /src python:3.12-slim python main.py http://order:8000

# Stop containers
docker compose down -v
```

### 7.2 Running Standalone on Host (with Python)

```zsh
# Terminal 1: Restaurant Service
cd services/restaurant
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 2: Order Service
cd services/order
pip install -r requirements.txt
export RESTAURANT_URL="http://localhost:8001"
uvicorn main:app --host 0.0.0.0 --port 8000
```
