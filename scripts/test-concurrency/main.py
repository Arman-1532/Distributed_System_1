import concurrent.futures
import json
import sys
import time
import urllib.request
import urllib.error

def post_order(base_url: str):
    url = f"{base_url}/orders"
    payload = json.dumps({"restaurant_id": 1, "items": [{"menu_item_id": 101, "quantity": 1}]}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            body = json.loads(response.read().decode("utf-8"))
            return {"status_code": status_code, "body": body, "error": None}
    except urllib.error.HTTPError as e:
        return {"status_code": e.code, "body": None, "error": str(e)}
    except Exception as e:
        return {"status_code": 0, "body": None, "error": str(e)}

def get_order(base_url: str, order_id: str):
    url = f"{base_url}/orders/{order_id}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            body = json.loads(response.read().decode("utf-8"))
            return {"status_code": status_code, "body": body, "error": None}
    except urllib.error.HTTPError as e:
        return {"status_code": e.code, "body": None, "error": str(e)}
    except Exception as e:
        return {"status_code": 0, "body": None, "error": str(e)}

def main():
    base_url = "http://localhost:8000"
    if len(sys.argv) > 1 and sys.argv[1].strip():
        base_url = sys.argv[1].strip().rstrip("/")

    total_requests = 20
    print(f"Starting concurrency test against {base_url} with {total_requests} requests...")

    start_time = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=total_requests) as executor:
        futures = [executor.submit(post_order, base_url) for _ in range(total_requests)]
        results = [f.result() for f in futures]
    elapsed = time.perf_counter() - start_time

    failed = False
    unique_ids = set()

    for idx, res in enumerate(results, start=1):
        if res["error"]:
            print(f"FAIL: Request {idx} encountered error: {res['error']}")
            failed = True
            continue
        if res["status_code"] != 201:
            print(f"FAIL: Request {idx} returned status {res['status_code']}, expected 201")
            failed = True
            continue
        order_id = res["body"].get("order_id") if res["body"] else None
        if not order_id:
            print(f"FAIL: Request {idx} returned empty order_id")
            failed = True
            continue
        if order_id in unique_ids:
            print(f"FAIL: Duplicate order_id detected: {order_id}")
            failed = True
            continue
        unique_ids.add(order_id)

    if len(unique_ids) != total_requests:
        print(f"FAIL: Expected {total_requests} unique IDs, got {len(unique_ids)}")
        failed = True

    print(f"Verifying all {len(unique_ids)} orders are retrievable via GET /orders/{{id}}...")
    for order_id in unique_ids:
        get_res = get_order(base_url, order_id)
        if get_res["error"] or get_res["status_code"] != 200:
            print(f"FAIL: GET /orders/{order_id} failed: status={get_res['status_code']}, error={get_res['error']}")
            failed = True
            continue
        retrieved_id = get_res["body"].get("order_id") if get_res["body"] else None
        if retrieved_id != order_id:
            print(f"FAIL: Mismatch in retrieved order_id: expected {order_id}, got {retrieved_id}")
            failed = True

    if failed:
        print(f"FAIL: Concurrency verification failed after {elapsed:.3f}s")
        sys.exit(1)

    print(f"PASS: All 20 orders successfully created and verified in {elapsed:.3f}s")

if __name__ == "__main__":
    main()
