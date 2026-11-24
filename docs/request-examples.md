# Request and Response Examples (Python / FastAPI)

This document provides copy-pasteable `curl` commands for all endpoints across both services, demonstrating successful responses and error scenarios according to the API contract.

Commands are written for macOS `zsh`. Every example reflects real responses obtained from live container runs.

---

## 1. Restaurant Service (`http://localhost:8001`)

### 1.1 Health Check (`GET /healthz`)
```zsh
curl -i http://localhost:8001/healthz
```

**Real Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:34:05 GMT
server: uvicorn
content-length: 15
content-type: application/json
x-correlation-id: f9099a47-f217-4047-85db-e4f36068e730

{"status":"ok"}
```

### 1.2 List All Restaurants (`GET /restaurants`)
```zsh
curl -i http://localhost:8001/restaurants
```

**Real Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:34:05 GMT
server: uvicorn
content-length: 626
content-type: application/json
x-correlation-id: 11cdb7b7-19f2-4729-94bb-44e03e5f4019

[{"id":1,"name":"Burger House","address":"123 Main St, Springfield","items":[{"id":101,"name":"Classic Burger","price":9.99,"available":true},{"id":102,"name":"Chicken Burger","price":10.99,"available":true}]},{"id":2,"name":"Pizza Corner","address":"456 Elm St, Springfield","items":[{"id":201,"name":"Margherita Pizza","price":12.5,"available":true},{"id":202,"name":"Pepperoni Pizza","price":14.0,"available":true}]},{"id":3,"name":"Sushi World","address":"789 Ocean Ave, Springfield","items":[{"id":301,"name":"California Roll","price":8.5,"available":true},{"id":302,"name":"Salmon Roll","price":11.0,"available":true}]}]
```

### 1.3 Get Single Restaurant (`GET /restaurants/1`)
```zsh
curl -i http://localhost:8001/restaurants/1
```

**Real Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:34:05 GMT
server: uvicorn
content-length: 208
content-type: application/json
x-correlation-id: bb13b3b3-d9b8-47c9-80ab-88a91cfb4f41

{"id":1,"name":"Burger House","address":"123 Main St, Springfield","items":[{"id":101,"name":"Classic Burger","price":9.99,"available":true},{"id":102,"name":"Chicken Burger","price":10.99,"available":true}]}
```

### 1.4 Restaurant Not Found (`GET /restaurants/999`)
```zsh
curl -i http://localhost:8001/restaurants/999
```

**Real Response (`404 Not Found`):**
```http
HTTP/1.1 404 Not Found
date: Wed, 18 Nov 2026 12:34:05 GMT
server: uvicorn
content-length: 130
content-type: application/json
x-correlation-id: 413b7d44-50ed-490a-956b-8526b8cbe6fb

{"error":{"code":"RESTAURANT_NOT_FOUND","message":"restaurant not found","correlation_id":"413b7d44-50ed-490a-956b-8526b8cbe6fb"}}
```

### 1.5 Non-Integer Restaurant ID (`GET /restaurants/abc`)
```zsh
curl -i http://localhost:8001/restaurants/abc
```

**Real Response (`400 Bad Request`):**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:05 GMT
server: uvicorn
content-length: 134
content-type: application/json
x-correlation-id: b4b0890f-75b7-4db5-a98b-2d02e14973cf

{"error":{"code":"INVALID_REQUEST","message":"invalid restaurant id in path","correlation_id":"b4b0890f-75b7-4db5-a98b-2d02e14973cf"}}
```

---

## 2. Order Service (`http://localhost:8000`)

### 2.1 Health Check (`GET /healthz`)
```zsh
curl -i http://localhost:8000/healthz
```

**Real Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:34:08 GMT
server: uvicorn
content-length: 15
content-type: application/json
x-correlation-id: 3d268c75-8aa9-4e7d-a411-b0d3529f9c45

{"status":"ok"}
```

### 2.2 Create Order - Success (`POST /orders`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 2}]}'
```

**Real Response (`201 Created`):**
```http
HTTP/1.1 201 Created
date: Wed, 18 Nov 2026 12:34:08 GMT
server: uvicorn
content-length: 110
content-type: application/json
x-correlation-id: b6b19415-ead0-4b7c-93ae-319cd98a315a

{"order_id":"ord-baebb753-e408-4375-8cb4-3a86e542d34d","status":"created","created_at":"2026-11-18T12:34:09Z"}
```

### 2.3 Create Order with Custom Correlation ID (`POST /orders`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: my-custom-corr-12345" \
  -d '{"restaurant_id": 2, "items": [{"menu_item_id": 201, "quantity": 1}]}'
```

**Real Response (`201 Created`):**
```http
HTTP/1.1 201 Created
date: Wed, 18 Nov 2026 12:34:08 GMT
server: uvicorn
content-length: 110
content-type: application/json
x-correlation-id: my-custom-corr-12345

{"order_id":"ord-cc50163b-48b0-4320-9952-89847e7c1bdc","status":"created","created_at":"2026-11-18T12:34:09Z"}
```

### 2.4 Get Order (`GET /orders/{id}`)
```zsh
curl -i http://localhost:8000/orders/ord-baebb753-e408-4375-8cb4-3a86e542d34d
```

**Real Response (`200 OK`):**
```http
HTTP/1.1 200 OK
date: Wed, 18 Nov 2026 12:34:22 GMT
server: uvicorn
content-length: 228
content-type: application/json
x-correlation-id: 11fb0854-f11a-45c6-b015-9e9d76bd0243

{"order_id":"ord-baebb753-e408-4375-8cb4-3a86e542d34d","status":"created","created_at":"2026-11-18T12:34:09Z","restaurant_id":1,"items":[{"menu_item_id":101,"quantity":2}],"correlation_id":"b6b19415-ead0-4b7c-93ae-319cd98a315a"}
```

### 2.5 Order Not Found (`GET /orders/ord-nonexistent`)
```zsh
curl -i http://localhost:8000/orders/ord-nonexistent
```

**Real Response (`404 Not Found`):**
```http
HTTP/1.1 404 Not Found
date: Wed, 18 Nov 2026 12:34:22 GMT
server: uvicorn
content-length: 120
content-type: application/json
x-correlation-id: 2108d6e1-8648-45b2-bbd7-fc1e14c0fb6f

{"error":{"code":"ORDER_NOT_FOUND","message":"order not found","correlation_id":"2108d6e1-8648-45b2-bbd7-fc1e14c0fb6f"}}
```

---

## 3. Order Service Error Scenarios

### 3.1 Malformed JSON (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": ['
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 132
content-type: application/json
x-correlation-id: b24411b7-53e1-4d87-af92-f91a6a23e915

{"error":{"code":"INVALID_REQUEST","message":"malformed JSON request body","correlation_id":"b24411b7-53e1-4d87-af92-f91a6a23e915"}}
```

### 3.2 Trailing Data After JSON (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]} extra'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 145
content-type: application/json
x-correlation-id: a9fd57ae-85eb-4221-9a2e-6e916cbef498

{"error":{"code":"INVALID_REQUEST","message":"unexpected trailing data after JSON body","correlation_id":"a9fd57ae-85eb-4221-9a2e-6e916cbef498"}}
```

### 3.3 Missing Required Field (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 126
content-type: application/json
x-correlation-id: 00249b1c-fbd6-4e6c-a297-8f1af06caa5a

{"error":{"code":"INVALID_REQUEST","message":"missing restaurant_id","correlation_id":"00249b1c-fbd6-4e6c-a297-8f1af06caa5a"}}
```

### 3.4 Wrong Type (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": "2"}]}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 127
content-type: application/json
x-correlation-id: 770f251a-f2de-4ce6-b6cf-6b34284bbde3

{"error":{"code":"INVALID_REQUEST","message":"invalid JSON data type","correlation_id":"770f251a-f2de-4ce6-b6cf-6b34284bbde3"}}
```

### 3.5 Non-Positive Restaurant ID (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 0, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 141
content-type: application/json
x-correlation-id: 261b5bb1-f4fd-4fb6-9eb8-0a99ef627819

{"error":{"code":"INVALID_REQUEST","message":"restaurant_id must be greater than 0","correlation_id":"261b5bb1-f4fd-4fb6-9eb8-0a99ef627819"}}
```

### 3.6 Invalid Quantity (`quantity < 1`) (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 0}]}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 132
content-type: application/json
x-correlation-id: 6d7b031d-e4dc-4914-b40c-6cb0a5fa9ed9

{"error":{"code":"INVALID_REQUEST","message":"quantity must be at least 1","correlation_id":"6d7b031d-e4dc-4914-b40c-6cb0a5fa9ed9"}}
```

### 3.7 Empty Items Array (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": []}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 131
content-type: application/json
x-correlation-id: 4d64af49-0372-4ce0-bc41-9442f8649480

{"error":{"code":"INVALID_REQUEST","message":"items list cannot be empty","correlation_id":"4d64af49-0372-4ce0-bc41-9442f8649480"}}
```

### 3.8 Duplicate Menu Item ID (`400 Bad Request`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}, {"menu_item_id": 101, "quantity": 2}]}'
```

**Real Response:**
```http
HTTP/1.1 400 Bad Request
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 141
content-type: application/json
x-correlation-id: 59712f6b-9fca-4600-b334-551cdf3099a1

{"error":{"code":"INVALID_REQUEST","message":"duplicate menu_item_id in items list","correlation_id":"59712f6b-9fca-4600-b334-551cdf3099a1"}}
```

### 3.9 Non-Existent Restaurant (`404 Not Found`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 999, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Real Response:**
```http
HTTP/1.1 404 Not Found
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 130
content-type: application/json
x-correlation-id: 387e71ce-4e65-4faf-863d-989951ddd6b7

{"error":{"code":"RESTAURANT_NOT_FOUND","message":"restaurant not found","correlation_id":"387e71ce-4e65-4faf-863d-989951ddd6b7"}}
```

### 3.10 Non-Existent Menu Item for Restaurant (`404 Not Found`)
```zsh
curl -i -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 999, "quantity": 1}]}'
```

**Real Response:**
```http
HTTP/1.1 404 Not Found
date: Wed, 18 Nov 2026 12:34:28 GMT
server: uvicorn
content-length: 147
content-type: application/json
x-correlation-id: f35a5851-e891-4a10-82ec-caca814130fd

{"error":{"code":"MENU_ITEM_NOT_FOUND","message":"menu item not found in restaurant menu","correlation_id":"f35a5851-e891-4a10-82ec-caca814130fd"}}
```

### 3.11 Downstream Restaurant Service Unavailable (`503 Service Unavailable`)
```zsh
curl -i -w "\nHTTP_STATUS: %{http_code}\nTIME_TOTAL: %{time_total}s\n" -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -H "X-Correlation-ID: outage-corr-fail-py-002" \
  -d '{"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}'
```

**Real Response:**
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
