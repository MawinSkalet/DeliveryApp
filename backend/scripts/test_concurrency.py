"""Verify that parallel orders cannot purchase the same last unit of stock."""

import json
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

import jwt
import psycopg
from pymongo import MongoClient

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000/api/v1/orders").rstrip("/")
ATTEMPTS = 20


def call(url: str, token: str, body: dict, key: str, start_barrier: Barrier) -> int:
    request = Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Idempotency-Key": key,
        },
        method="POST",
    )
    start_barrier.wait(timeout=30)
    try:
        with urlopen(request, timeout=30) as response:
            return response.status
    except HTTPError as error:
        return error.code


def main() -> None:
    customer_id = str(uuid4())
    restaurant_id = str(uuid4())
    product_id = str(uuid4())
    mongo = MongoClient(os.environ["MONGO_URL"])
    database_url = os.environ["DATABASE_URL"].replace(
        "postgresql+psycopg://", "postgresql://", 1
    )
    postgres = psycopg.connect(database_url, autocommit=True)
    try:
        postgres.execute(
            "INSERT INTO users (id, email, name) VALUES (%s, %s, %s)",
            (customer_id, f"{customer_id}@example.test", "Concurrency Test"),
        )
        postgres.execute(
            "INSERT INTO restaurants (id, name) VALUES (%s, %s)",
            (restaurant_id, "Concurrency Test"),
        )
        postgres.execute(
            """INSERT INTO inventory (product_id, restaurant_id, quantity)
               VALUES (%s, %s, 1)""",
            (product_id, restaurant_id),
        )
        mongo.deliveryapp.products.insert_one(
            {
                "_id": product_id,
                "restaurant_id": restaurant_id,
                "name": "Last unit",
                "price_satang": 100,
                "active": True,
            }
        )

        token = jwt.encode(
            {
                "sub": customer_id,
                "role": "customer",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
            },
            os.environ["AUTH_SECRET"],
            algorithm="HS256",
        )
        body = {
            "restaurant_id": restaurant_id,
            "items": [{"product_id": product_id, "quantity": 1}],
        }
        start_barrier = Barrier(ATTEMPTS)
        with ThreadPoolExecutor(max_workers=ATTEMPTS) as executor:
            futures = [
                executor.submit(
                    call,
                    API_URL,
                    token,
                    body,
                    f"last-unit-race-{index}",
                    start_barrier,
                )
                for index in range(ATTEMPTS)
            ]
            statuses = [future.result() for future in futures]

        successes = statuses.count(201)
        conflicts = statuses.count(409)
        print(
            f"Concurrent last-unit test: {successes} success (expected 1), "
            f"{conflicts} conflicts (expected {ATTEMPTS - 1})"
        )
        assert successes == 1 and conflicts == ATTEMPTS - 1, statuses
    finally:
        postgres.execute("DELETE FROM orders WHERE customer_id = %s", (customer_id,))
        postgres.execute("DELETE FROM inventory WHERE product_id = %s", (product_id,))
        postgres.execute("DELETE FROM restaurants WHERE id = %s", (restaurant_id,))
        postgres.execute("DELETE FROM users WHERE id = %s", (customer_id,))
        mongo.deliveryapp.products.delete_one({"_id": product_id})
        postgres.close()
        mongo.close()


if __name__ == "__main__":
    main()
