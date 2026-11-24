# API Contract: Order and Restaurant Services

This document defines the formal API contract, schemas, error formats, status codes, seed catalogue, and architecture design decisions for both the Restaurant Service and Order Service.

---

## 1. Design Decisions

1. **Standardized Error Representation**:
   Both services return error responses with the exact structure:
   ```json
   {
     "error": {
       "code": "<CODE>",
       "message": "<safe message>",
       "correlation_id": "<id>"
     }
   }
   ```
   Internal details, stack traces, panic messages, or raw low-level Go errors are never leaked to the client.

2. **Validation and Strict JSON Decoding**:
   - In the Order Service, request bodies are parsed using `json.Decoder`.
   - Fields such as `restaurant_id`, `menu_item_id`, and `quantity` use pointer types (`*int`) so that missing fields are distinguishable from zero values.
   - Go's `json.Decoder` rejects invalid types (e.g., string `"2"`, boolean `true`, float `2.5` for integer fields), mapping any decode error to `400 INVALID_REQUEST`.
   - Any extra or trailing data following the valid JSON body is strictly rejected as `400 INVALID_REQUEST`.
   - Validation enforces: `restaurant_id > 0`, `menu_item_id > 0`, `quantity >= 1`, non-empty `items` array, and no duplicate `menu_item_id` in a single order request.

3. **Domain Error Semantics**:
   - `409 MENU_ITEM_UNAVAILABLE`: Returned when an item is recognized on the restaurant's menu but has `available: false`.
   - Duplicate `menu_item_id` values within the same order are rejected with `400 INVALID_REQUEST`.
   - Items not present on the restaurant's menu return `404 MENU_ITEM_NOT_FOUND`.
   - Non-existent restaurant returns `404 RESTAURANT_NOT_FOUND`.

4. **Identifiers and Timestamps**:
   - Order IDs are formatted as `ord-<UUID4>` generated using `crypto/rand` with RFC 4122 version 4 and variant bits properly set.
   - `created_at` timestamps are generated in UTC and formatted using RFC 3339 ending in `Z` (e.g. `2026-11-17T12:00:00Z`).

5. **Correlation ID Tracing**:
   - Every request is tagged with an `X-Correlation-ID`.
   - If an incoming `X-Correlation-ID` header is present and non-empty, it is preserved. Otherwise, a new UUIDv4 is generated.
   - The header is set on all HTTP responses before handler execution so all responses (including errors) include `X-Correlation-ID`.
   - The Order Service forwards `X-Correlation-ID` on all outbound HTTP calls to the Restaurant Service.

6. **Decoupled Architecture**:
   - The Order Service communicates with the Restaurant Service strictly over HTTP.
   - No code, structs, or packages are shared between services.
   - The Order Service repository holds an in-memory lock only for short map operations and never holds locks across network calls.

---

## 2. HTTP Status Codes and Error Codes

| Situation | HTTP Status | Code (`error.code`) | Safe Message (`error.message`) |
|---|---|---|---|
| Order created | 201 Created | *N/A* | *N/A* |
| Malformed JSON, trailing data, missing field, wrong type, non-positive ID/quantity, empty items, duplicate item ID, non-integer path parameter | 400 Bad Request | `INVALID_REQUEST` | Descriptive client-safe validation message |
| Restaurant not found | 404 Not Found | `RESTAURANT_NOT_FOUND` | `restaurant not found` |
| Menu item not found in restaurant menu | 404 Not Found | `MENU_ITEM_NOT_FOUND` | `menu item not found in restaurant menu` |
| Menu item is marked unavailable (`available: false`) | 409 Conflict | `MENU_ITEM_UNAVAILABLE` | `menu item is currently unavailable` |
| Order not found | 404 Not Found | `ORDER_NOT_FOUND` | `order not found` |
| Downstream Restaurant Service connection failure, timeout, 5xx, unexpected 4xx, or invalid payload | 503 Service Unavailable | `RESTAURANT_SERVICE_UNAVAILABLE` | `restaurant service unavailable` |
| Internal server error or recovered panic | 500 Internal Server Error | `INTERNAL_ERROR` | `internal server error` |

---

## 3. Restaurant Service Endpoints (`:8001`)

### 3.1 `GET /healthz`
Returns service liveness status.

- **Response `200 OK`**:
  ```json
  {
    "status": "ok"
  }
  ```

### 3.2 `GET /restaurants`
Returns the complete list of restaurants and their menu items in stable order.

- **Response `200 OK`**:
  ```json
  [
    {
      "id": 1,
      "name": "Burger House",
      "address": "123 Main St, Springfield",
      "items": [
        {
          "id": 101,
          "name": "Classic Burger",
          "price": 9.99,
          "available": true
        },
        {
          "id": 102,
          "name": "Chicken Burger",
          "price": 10.99,
          "available": true
        }
      ]
    },
    {
      "id": 2,
      "name": "Pizza Corner",
      "address": "456 Elm St, Springfield",
      "items": [
        {
          "id": 201,
          "name": "Margherita Pizza",
          "price": 12.50,
          "available": true
        },
        {
          "id": 202,
          "name": "Pepperoni Pizza",
          "price": 14.00,
          "available": true
        }
      ]
    },
    {
      "id": 3,
      "name": "Sushi World",
      "address": "789 Ocean Ave, Springfield",
      "items": [
        {
          "id": 301,
          "name": "California Roll",
          "price": 8.50,
          "available": true
        },
        {
          "id": 302,
          "name": "Salmon Roll",
          "price": 11.00,
          "available": true
        }
      ]
    }
  ]
  ```

### 3.3 `GET /restaurants/{id}`
Returns details for a single restaurant by integer identifier.

- **Response `200 OK`**:
  ```json
  {
    "id": 1,
    "name": "Burger House",
    "address": "123 Main St, Springfield",
    "items": [
      {
        "id": 101,
        "name": "Classic Burger",
        "price": 9.99,
        "available": true
      },
      {
        "id": 102,
        "name": "Chicken Burger",
        "price": 10.99,
        "available": true
      }
    ]
  }
  ```
- **Response `400 Bad Request`** (non-integer ID):
  ```json
  {
    "error": {
      "code": "INVALID_REQUEST",
      "message": "invalid restaurant id in path",
      "correlation_id": "c1f7b60b-8d8a-4465-b778-98e6ef58e980"
    }
  }
  ```
- **Response `404 Not Found`** (ID does not exist):
  ```json
  {
    "error": {
      "code": "RESTAURANT_NOT_FOUND",
      "message": "restaurant not found",
      "correlation_id": "c1f7b60b-8d8a-4465-b778-98e6ef58e980"
    }
  }
  ```

---

## 4. Order Service Endpoints (`:8000`)

### 4.1 `GET /healthz`
Returns liveness status. Does not call the Restaurant Service.

- **Response `200 OK`**:
  ```json
  {
    "status": "ok"
  }
  ```

### 4.2 `POST /orders`
Validates request, checks restaurant and menu item availability via HTTP with the Restaurant Service, and persists the order.

- **Request Headers**:
  `Content-Type: application/json`
  `X-Correlation-ID: <optional-uuid>`

- **Request Body**:
  ```json
  {
    "restaurant_id": 1,
    "items": [
      {
        "menu_item_id": 101,
        "quantity": 2
      }
    ]
  }
  ```

- **Response `201 Created`** (exactly these three fields):
  ```json
  {
    "order_id": "ord-d3b07384-d113-4663-80e2-696660142323",
    "status": "created",
    "created_at": "2026-11-17T12:00:00Z"
  }
  ```

- **Error Responses**:
  - `400 Bad Request` (`INVALID_REQUEST`):
    ```json
    {
      "error": {
        "code": "INVALID_REQUEST",
        "message": "quantity must be at least 1",
        "correlation_id": "..."
      }
    }
    ```
  - `404 Not Found` (`RESTAURANT_NOT_FOUND`):
    ```json
    {
      "error": {
        "code": "RESTAURANT_NOT_FOUND",
        "message": "restaurant not found",
        "correlation_id": "..."
      }
    }
    ```
  - `404 Not Found` (`MENU_ITEM_NOT_FOUND`):
    ```json
    {
      "error": {
        "code": "MENU_ITEM_NOT_FOUND",
        "message": "menu item not found in restaurant menu",
        "correlation_id": "..."
      }
    }
    ```
  - `409 Conflict` (`MENU_ITEM_UNAVAILABLE`):
    ```json
    {
      "error": {
        "code": "MENU_ITEM_UNAVAILABLE",
        "message": "menu item is currently unavailable",
        "correlation_id": "..."
      }
    }
    ```
  - `503 Service Unavailable` (`RESTAURANT_SERVICE_UNAVAILABLE`):
    ```json
    {
      "error": {
        "code": "RESTAURANT_SERVICE_UNAVAILABLE",
        "message": "restaurant service unavailable",
        "correlation_id": "..."
      }
    }
    ```

### 4.3 `GET /orders/{id}`
Retrieves an order by its `ord-<UUID>` identifier.

- **Response `200 OK`**:
  ```json
  {
    "order_id": "ord-d3b07384-d113-4663-80e2-696660142323",
    "status": "created",
    "created_at": "2026-11-17T12:00:00Z",
    "restaurant_id": 1,
    "items": [
      {
        "menu_item_id": 101,
        "quantity": 2
      }
    ],
    "correlation_id": "c1f7b60b-8d8a-4465-b778-98e6ef58e980"
  }
  ```

- **Response `404 Not Found`**:
  ```json
  {
    "error": {
      "code": "ORDER_NOT_FOUND",
      "message": "order not found",
      "correlation_id": "c1f7b60b-8d8a-4465-b778-98e6ef58e980"
    }
  }
  ```

---

## 5. Seed Catalogue Data

| Restaurant ID | Restaurant Name | Address | Menu Item ID | Item Name | Price | Available |
|---|---|---|---|---|---|---|
| 1 | Burger House | 123 Main St, Springfield | 101 | Classic Burger | $9.99 | `true` |
| 1 | Burger House | 123 Main St, Springfield | 102 | Chicken Burger | $10.99 | `true` |
| 2 | Pizza Corner | 456 Elm St, Springfield | 201 | Margherita Pizza | $12.50 | `true` |
| 2 | Pizza Corner | 456 Elm St, Springfield | 202 | Pepperoni Pizza | $14.00 | `true` |
| 3 | Sushi World | 789 Ocean Ave, Springfield | 301 | California Roll | $8.50 | `true` |
| 3 | Sushi World | 789 Ocean Ave, Springfield | 302 | Salmon Roll | $11.00 | `true` |
