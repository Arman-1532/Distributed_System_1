# Failure & Outage Experiment Report (Python / FastAPI)

This document records the exact steps, live curl executions, responses, elapsed times, and correlated service logs captured during the downstream dependency outage experiment.

---

## 1. Experiment Overview & Objective

The objective of this experiment is to verify the resilience and fault isolation of the Order Service when its downstream dependency (the Restaurant Service) becomes completely unavailable:
1. Confirm normal operation with both services running healthy.
2. Trace an end-to-end request across both services using a shared correlation ID (`trace-corr-py-001`).
3. Simulate an unexpected dependency outage by stopping the `restaurant` container.
4. Verify that requests to create orders return `503 Service Unavailable` within a strictly bounded duration without leaking raw errors.
5. Verify that the Order Service's own `/healthz` endpoint continues returning `200 OK` (fault isolation).
6. Restart the `restaurant` container and verify immediate recovery of order processing without stale connection errors.

---

## 2. Step-by-Step Execution and Real Output

### Step 2.1: Clean Startup and Health Verification
The environment was reset to a fresh state and started with Compose:
```zsh
docker compose down -v
docker compose up --build -d
```

Containers reached `healthy` status:
```zsh
docker compose ps
```
**Output:**
```
NAME                                IMAGE                             COMMAND                  SERVICE      STATUS
distributed_system_1-order-1        distributed_system_1-order        "uvicorn main:app --…"   order        Up (healthy)
distributed_system_1-restaurant-1   distributed_system_1-restaurant   "uvicorn main:app --…"   restaurant   Up (healthy)
```

---

### Step 2.2: Baseline Order Creation (Traced Across Both Services)
A baseline order was placed with an explicit correlation ID `trace-corr-py-001`:

```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: trace-corr-py-001" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Response (`201 Created`):**
```http
HTTP/1.1 201 Created
date: Wed, 18 Nov 2026 12:34:57 GMT
server: uvicorn
content-length: 110
content-type: application/json
x-correlation-id: trace-corr-py-001

{"order_id":"ord-b897060f-cc2c-4414-b547-8ba9869bdbfb","status":"created","created_at":"2026-11-18T12:34:58Z"}
```

**Log Correlation Trace Across Both Services:**
From `docs/logs/outage-experiment.log`:
```log
restaurant-1  | 2026-11-18 12:34:58,059 INFO [correlation_id=trace-corr-py-001] request completed method=GET path=/restaurants/1 status=200 elapsed_ms=0
order-1       | 2026-11-18 12:34:58,064 INFO [correlation_id=trace-corr-py-001] outbound call to restaurant service completed status=200 elapsed_ms=34
order-1       | 2026-11-18 12:34:58,065 INFO [correlation_id=trace-corr-py-001] order created successfully order_id=ord-b897060f-cc2c-4414-b547-8ba9869bdbfb restaurant_id=1 item_count=1
order-1       | 2026-11-18 12:34:58,065 INFO [correlation_id=trace-corr-py-001] request completed method=POST path=/orders status=201 elapsed_ms=37
```

---

### Step 2.3: Downstream Service Shutdown
The Restaurant Service was stopped:
```zsh
docker compose stop restaurant
```

---

### Step 2.4: Outage Request & Bounded Timing Verification
With the Restaurant Service stopped, an order creation request was submitted with correlation ID `outage-corr-fail-py-002`, timed using `curl -w`:

```zsh
curl -i -w "\nHTTP_STATUS: %{http_code}\nTIME_TOTAL: %{time_total}s\n" -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: outage-corr-fail-py-002" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Response (`503 Service Unavailable`):**
```http
HTTP/1.1 503 Service Unavailable
date: Wed, 18 Nov 2026 12:35:07 GMT
server: uvicorn
content-length: 137
content-type: application/json
x-correlation-id: outage-corr-fail-py-002

{"error":{"code":"RESTAURANT_SERVICE_UNAVAILABLE","message":"restaurant service unavailable","correlation_id":"outage-corr-fail-py-002"}}
HTTP_STATUS: 503
TIME_TOTAL: 0.347701s
```

**Key Findings:**
- The Order Service failed gracefully within **0.348s** (bounded by connect timeout, well within the 2.0s limit).
- The client received a safe `503 Service Unavailable` with `RESTAURANT_SERVICE_UNAVAILABLE`. No socket traces or unhandled exceptions leaked to the client.
- The Order Service internal log captured the real cause:
  ```log
  order-1       | 2026-11-18 12:35:08,245 ERROR [correlation_id=outage-corr-fail-py-002] outbound call to restaurant service failed error=[Errno -3] Temporary failure in name resolution elapsed_ms=341
  order-1       | 2026-11-18 12:35:08,245 INFO [correlation_id=outage-corr-fail-py-002] request completed method=POST path=/orders status=503 elapsed_ms=342
  ```

---

### Step 2.5: Order Service Health Check During Outage
The Order Service liveness probe was verified while the dependency was down:

```zsh
curl -i http://localhost:8000/healthz
```

**Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:35:13 GMT
server: uvicorn
content-length: 15
content-type: application/json
x-correlation-id: a97f9d9a-d470-4aa2-ae53-be8d438c2bbc

{"status":"ok"}
```
The Order Service remained healthy and independent.

---

### Step 2.6: Recovery and Post-Restart Verification
The Restaurant Service was started back up:
```zsh
docker compose start restaurant
```

Once the container regained `healthy` status, a new order creation request was submitted with correlation ID `outage-corr-recovery-py-003`:

```zsh
curl -i -w "\nHTTP_STATUS: %{http_code}\nTIME_TOTAL: %{time_total}s\n" -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: outage-corr-recovery-py-003" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Response (`201 Created`):**
```http
HTTP/1.1 201 Created
date: Wed, 18 Nov 2026 12:35:28 GMT
server: uvicorn
content-length: 110
content-type: application/json
x-correlation-id: outage-corr-recovery-py-003

{"order_id":"ord-9fc9bcd0-f6e9-4082-bfc2-51a18f6201cc","status":"created","created_at":"2026-11-18T12:35:28Z"}
HTTP_STATUS: 201
TIME_TOTAL: 0.016901s
```

---

## 3. Raw Log Reference
The complete raw logs from the experiment are persisted in:
`docs/logs/outage-experiment.log`
