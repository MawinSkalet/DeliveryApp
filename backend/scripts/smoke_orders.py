"""Run against a local Compose stack after `alembic upgrade head`."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import jwt
import psycopg
from pymongo import MongoClient

BASE_URL = "http://127.0.0.1:8000/api/v1/orders"


def call(method: str, path: str, token: str, body: dict | None = None, key: str | None = None) -> tuple[int, dict]:
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if key is not None:
        headers["Idempotency-Key"] = key
    request = Request(
        BASE_URL + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers=headers,
        method=method,
    )
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def token(user_id: str) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "role": "customer",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        os.environ["AUTH_SECRET"],
        algorithm="HS256",
    )


def main() -> None:
    customer_id = str(uuid4())
    other_id = str(uuid4())
    restaurant_id = str(uuid4())
    product_a = str(uuid4())
    product_b = str(uuid4())
    mongo = MongoClient(os.environ["MONGO_URL"])
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    pg = psycopg.connect(url, autocommit=True)
    try:
        with pg.transaction():
            pg.execute(
                "INSERT INTO users (id, email, name) VALUES (%s, %s, 'Smoke Customer'), (%s, %s, 'Other Customer')",
                (customer_id, f"{customer_id}@example.test", other_id, f"{other_id}@example.test"),
            )
            pg.execute("INSERT INTO restaurants (id, name) VALUES (%s, 'Smoke Restaurant')", (restaurant_id,))
            pg.execute(
                "INSERT INTO inventory (product_id, restaurant_id, quantity) VALUES (%s, %s, 4), (%s, %s, 1)",
                (product_a, restaurant_id, product_b, restaurant_id),
            )
        mongo.deliveryapp.products.insert_many(
            [
                {"_id": product_a, "restaurant_id": restaurant_id, "name": "Rice", "price_satang": 5000, "active": True},
                {"_id": product_b, "restaurant_id": restaurant_id, "name": "Tea", "price_satang": 2000, "active": True},
            ]
        )

        customer_token = token(customer_id)
        status, unauthenticated = call("GET", "", "")
        assert status == 401 and unauthenticated["error"]["code"] == "UNAUTHENTICATED"
        order_body = {
            "restaurant_id": restaurant_id,
            "items": [
                {"product_id": product_a, "quantity": 1},
                {"product_id": product_b, "quantity": 1},
            ],
        }
        status, created = call("POST", "", customer_token, order_body, "first-order")
        assert status == 201, (status, created)
        assert created["subtotal_satang"] == 7000
        assert created["total_satang"] == 7000 + int(os.getenv("DELIVERY_FEE_SATANG", "1500"))
        order_id = created["id"]
        status, listed = call("GET", "", customer_token)
        assert status == 200 and listed["items"][0]["id"] == order_id
        status, invalid = call(
            "POST", "", customer_token,
            {"restaurant_id": restaurant_id, "items": [{"product_id": product_a, "quantity": 0}]},
            "invalid-order",
        )
        assert status == 400 and invalid["error"]["code"] == "VALIDATION_ERROR"

        status, replayed = call("POST", "", customer_token, order_body, "first-order")
        assert status == 200 and replayed["id"] == order_id, (status, replayed)
        status, conflict = call(
            "POST", "", customer_token,
            {"restaurant_id": restaurant_id, "items": [{"product_id": product_a, "quantity": 2}]},
            "first-order",
        )
        assert status == 409 and conflict["error"]["code"] == "IDEMPOTENCY_CONFLICT"

        status, denied = call("GET", f"/{order_id}", token(other_id))
        assert status == 404 and denied["error"]["code"] == "ORDER_NOT_FOUND"

        status, out_of_stock = call("POST", "", customer_token, order_body, "no-stock")
        assert status == 409 and out_of_stock["error"]["code"] == "OUT_OF_STOCK"

        same_key_body = {"restaurant_id": restaurant_id, "items": [{"product_id": product_a, "quantity": 1}]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(call, "POST", "", customer_token, same_key_body, "same-key-race")
                for _ in range(2)
            ]
            same_key_results = [future.result() for future in futures]
        assert sorted(result[0] for result in same_key_results) == [200, 201], same_key_results
        assert same_key_results[0][1]["id"] == same_key_results[1][1]["id"]

        concurrent_body = {"restaurant_id": restaurant_id, "items": [{"product_id": product_a, "quantity": 2}]}
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(call, "POST", "", customer_token, concurrent_body, f"race-{index}")
                for index in range(2)
            ]
            results = [future.result() for future in futures]
        assert sorted(result[0] for result in results) == [201, 409], results

        status, cancelled = call("POST", f"/{order_id}/cancel", customer_token)
        assert status == 200 and cancelled["status"] == "CANCELLED"
        status, cancelled_again = call("POST", f"/{order_id}/cancel", customer_token)
        assert status == 200 and cancelled_again["status"] == "CANCELLED"

        quantity_a = pg.execute("SELECT quantity FROM inventory WHERE product_id = %s", (product_a,)).fetchone()[0]
        quantity_b = pg.execute("SELECT quantity FROM inventory WHERE product_id = %s", (product_b,)).fetchone()[0]
        assert (quantity_a, quantity_b) == (1, 1), (quantity_a, quantity_b)
        print("Orders smoke test passed: create, replay, conflict, authorization, stock, race, cancellation")
    finally:
        with pg.transaction():
            pg.execute("DELETE FROM orders WHERE customer_id = %s", (customer_id,))
            pg.execute("DELETE FROM inventory WHERE restaurant_id = %s", (restaurant_id,))
            pg.execute("DELETE FROM restaurants WHERE id = %s", (restaurant_id,))
            pg.execute("DELETE FROM users WHERE id IN (%s, %s)", (customer_id, other_id))
        mongo.deliveryapp.products.delete_many({"_id": {"$in": [product_a, product_b]}})
        pg.close()
        mongo.close()


if __name__ == "__main__":
    main()
