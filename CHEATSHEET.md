# Project Commands & Demo Cheatsheet (Raw Docker CLI)

Use this cheatsheet to demonstrate the project step-by-step in front of your professor using **raw Docker CLI commands** (`docker network`, `docker build`, `docker run`, `docker stop`, `docker rm`).

All commands are written for macOS (`zsh`) and are ready to copy and paste directly into your terminal.

---

### Step 1: Verify Docker Desktop is Running
*Description: Verifies that the Docker daemon is active on macOS before executing container commands.*
```zsh
docker info > /dev/null && echo "Docker Desktop is running."
```

---

### Step 2: Create Network & Build Docker Images
*Description: Creates an isolated user-defined bridge network named `assignment` and builds the native Docker images for both services.*

```zsh
# 2.1 Create user-defined bridge network
docker network create assignment

# 2.2 Build Restaurant Service image
docker build -t restaurant-svc services/restaurant

# 2.3 Build Order Service image
docker build -t order-svc services/order
```

---

### Step 3: Run Containers (Raw Docker Run)
*Description: Launches both services as named background containers attached to the `assignment` network, exposing their ports and injecting the required `RESTAURANT_URL`.*

```zsh
# 3.1 Run Restaurant Service container on port 8001
docker run -d --name restaurant --network assignment -p 8001:8001 restaurant-svc

# 3.2 Run Order Service container on port 8000 with RESTAURANT_URL pointing to the restaurant container
docker run -d --name order --network assignment -p 8000:8000 \
  -e RESTAURANT_URL=http://restaurant:8001 order-svc
```

*Wait 4 seconds, then verify both containers are running and healthy:*
```zsh
docker ps
```
*(Expected output: both `restaurant` and `order` containers are `Up` and `(healthy)`).*

---

### Step 4: Run Automated Test Suites (Inside Docker)
*Description: Runs all 12 unit and integration tests inside the built container images without needing Python on the host.*

```zsh
# Restaurant Service Tests (6 tests: health, catalogue, by-id, 404, 400, seed validation)
docker run --rm restaurant-svc pytest -v

# Order Service Tests (6 tests: success, retrieval, validation, dependency error mapping, correlation, concurrency)
docker run --rm order-svc pytest -v
```
*(Expected output: 100% of tests pass).*

---

### Step 5: Test Restaurant Service Endpoints (`:8001`)

```zsh
# 5.1 Check Restaurant Service health (Returns 200 OK)
curl -i http://localhost:8001/healthz

# 5.2 List all restaurants (Returns 3 seeded restaurants and 6 menu items)
curl -i http://localhost:8001/restaurants

# 5.3 Get details for Restaurant 1 (Returns 200 OK with menu items)
curl -i http://localhost:8001/restaurants/1

# 5.4 Query non-existent restaurant (Returns 404 RESTAURANT_NOT_FOUND)
curl -i http://localhost:8001/restaurants/999

# 5.5 Query with non-integer ID (Returns 400 INVALID_REQUEST)
curl -i http://localhost:8001/restaurants/abc
```

---

### Step 6: Test Order Service Endpoints (`:8000`)

```zsh
# 6.1 Check Order Service health (Independent liveness probe; does not call Restaurant)
curl -i http://localhost:8000/healthz

# 6.2 Create an order (Calls Restaurant over HTTP; returns 201 Created with exactly 3 fields)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 2}]}'

# 6.3 Retrieve an order by its ID (Replace <ORDER_ID> with the generated ID, e.g. ord-baebb753-...)
curl -i http://localhost:8000/orders/<ORDER_ID>

# 6.4 Query non-existent order (Returns 404 ORDER_NOT_FOUND)
curl -i http://localhost:8000/orders/ord-nonexistent

# 6.5 Create an order with custom Correlation ID (Demonstrates cross-service distributed tracing)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: prof-demo-trace-123" \
  -d '{"restaurant_id": 2, "items": [{"menu_item_id": 201, "quantity": 1}]}'
```

---

### Step 7: Test Input Validation Rejection (HTTP 400)
*Description: Proves that the Order Service strictly validates inputs and rejects invalid requests without corrupting order state.*

```zsh
# 7.1 Bad quantity: 0 (Returns 400 INVALID_REQUEST)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 0}]}'

# 7.2 Missing required field: restaurant_id omitted (Returns 400 INVALID_REQUEST)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"items": [{"menu_item_id": 101, "quantity": 1}]}'

# 7.3 Trailing payload data after valid JSON (Returns 400 INVALID_REQUEST)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]} extra_trailing_bytes'

# 7.4 Duplicate menu_item_id in a single order (Returns 400 INVALID_REQUEST)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}, {"menu_item_id": 101, "quantity": 2}]}'

# 7.5 Non-existent restaurant ID (Returns 404 RESTAURANT_NOT_FOUND)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 999, "items": [{"menu_item_id": 101, "quantity": 1}]}'

# 7.6 Non-existent menu item ID (Returns 404 MENU_ITEM_NOT_FOUND)
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 999, "quantity": 1}]}'
```

---

### Step 8: Demonstrate Concurrency (20 Simultaneous Requests)
*Description: Fires 20 concurrent POST requests against the running container; verifies thread-safe mutex execution, 20 unique IDs, and that all 20 orders are retrievable by GET.*

```zsh
docker run --rm --network assignment -v "$PWD/scripts/test-concurrency:/src" -w /src python:3.12-slim python main.py http://order:8000
```
*(Expected output: `PASS: All 20 orders successfully created and verified in ~0.2s`).*

---

### Step 9: Demonstrate Downstream Outage & Recovery Experiment
*Description: Demonstrates fault isolation and bounded failure time when the downstream Restaurant Service becomes completely unavailable.*

```zsh
# 9.1 Stop the Restaurant container
docker stop restaurant

# 9.2 Attempt to place an order (Fails gracefully with 503 RESTAURANT_SERVICE_UNAVAILABLE in < 0.2s)
curl -i -w "\nTIME_TOTAL: %{time_total}s\n" -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'

# 9.3 Verify Order Service health stays 200 OK (Fault isolation proof)
curl -i http://localhost:8000/healthz

# 9.4 Restart the Restaurant container
docker start restaurant
sleep 4

# 9.5 Verify immediate recovery (Order succeeds with 201 Created in ~0.03s)
curl -i -w "\nTIME_TOTAL: %{time_total}s\n" -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

---

### Step 10: View and Save Service Logs (Raw Docker Logs)
*Description: View live logs or save output to disk using raw Docker CLI commands.*

```zsh
# View live logs from the order service:
docker logs -f order

# View live logs from the restaurant service:
docker logs -f restaurant

# View the last 25 lines of logs:
docker logs --tail 25 order

# Save container logs to the assignment log file:
docker logs order > docs/logs/outage-experiment.log
docker logs restaurant >> docs/logs/outage-experiment.log
```

---

### Step 11: Clean Teardown (Raw Docker RM)
*Description: Stops and removes both containers, then deletes the `assignment` network.*

```zsh
# Stop and remove containers
docker rm -f order restaurant

# Remove the user-defined network
docker network rm assignment
```
