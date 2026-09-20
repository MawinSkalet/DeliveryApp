"""Exercise all five required CP1 routes against the seeded Compose stack."""

import os
from uuid import uuid4

import httpx
import psycopg
from pymongo import MongoClient


def require(response: httpx.Response, expected: int) -> dict:
    if response.status_code != expected:
        raise AssertionError(f"Expected {expected}, got {response.status_code}: {response.text}")
    return response.json()


def main() -> None:
    restaurant_id = str(uuid4())
    customer_id = None
    product_id = None
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    password = os.environ["SEED_USER_PASSWORD"]

    with psycopg.connect(database_url) as connection:
        connection.execute(
            "INSERT INTO restaurants (id, name) VALUES (%s, %s)",
            (restaurant_id, "CP1 Smoke Restaurant"),
        )

    try:
        with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
            email = f"cp1-{uuid4()}@example.test"
            customer = require(
                client.post(
                    "/api/v1/users",
                    json={"email": email, "name": "CP1 Demo Customer", "password": password},
                ),
                201,
            )
            customer_id = customer["id"]
            customer_login = require(
                client.post("/api/v1/auth/login", json={"email": email, "password": password}),
                200,
            )
            customer_headers = {"Authorization": f"Bearer {customer_login['access_token']}"}
            profile = require(
                client.get(f"/api/v1/users/{customer_id}", headers=customer_headers), 200
            )
            assert profile["id"] == customer_id

            merchant_login = require(
                client.post(
                    "/api/v1/auth/login",
                    json={"email": "merchant@cmu.example", "password": password},
                ),
                200,
            )
            merchant_headers = {"Authorization": f"Bearer {merchant_login['access_token']}"}
            product = require(
                client.post(
                    "/api/v1/products",
                    headers=merchant_headers,
                    json={
                        "restaurant_id": restaurant_id,
                        "name": "Khao Soi Chicken",
                        "price_satang": 6500,
                        "initial_stock": 3,
                        "attributes": {"spice_level": "medium", "size": "regular"},
                    },
                ),
                201,
            )
            product_id = product["id"]
            catalog = require(
                client.get(
                    "/api/v1/products",
                    params={"restaurant_id": restaurant_id, "limit": 1, "offset": 0},
                ),
                200,
            )
            assert catalog["total"] == 1 and catalog["items"][0]["id"] == product_id

            order = require(
                client.post(
                    "/api/v1/orders",
                    headers={**customer_headers, "Idempotency-Key": str(uuid4())},
                    json={
                        "restaurant_id": restaurant_id,
                        "items": [{"product_id": product_id, "quantity": 1}],
                    },
                ),
                201,
            )
            assert order["subtotal_satang"] == 6500
            assert order["items"][0]["product_id"] == product_id
            with psycopg.connect(database_url) as connection:
                stock = connection.execute(
                    "SELECT quantity FROM inventory WHERE product_id = %s", (product_id,)
                ).fetchone()[0]
            assert stock == 2
            cancelled = require(
                client.post(f"/api/v1/orders/{order['id']}/cancel", headers=customer_headers),
                200,
            )
            assert cancelled["status"] == "CANCELLED"
            print("CP1 smoke test passed: Users, Products, Orders, and cross-database stock")
    finally:
        if product_id is not None:
            with MongoClient(os.environ["MONGO_URL"]) as mongo:
                mongo.deliveryapp.products.delete_one({"_id": product_id})
        with psycopg.connect(database_url) as connection:
            if customer_id is not None:
                connection.execute("DELETE FROM orders WHERE customer_id = %s", (customer_id,))
            connection.execute("DELETE FROM inventory WHERE restaurant_id = %s", (restaurant_id,))
            connection.execute("DELETE FROM restaurants WHERE id = %s", (restaurant_id,))
            if customer_id is not None:
                connection.execute("DELETE FROM users WHERE id = %s", (customer_id,))


if __name__ == "__main__":
    main()
