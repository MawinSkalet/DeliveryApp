import os
import unittest
from unittest.mock import patch
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

from app.main import app
from app.security import create_access_token


class TestProductsApi(unittest.TestCase):
    def setUp(self) -> None:
        if not os.getenv("DATABASE_URL") or not os.getenv("MONGO_URL"):
            self.skipTest("Database URLs are not configured")
        self.client = TestClient(app)
        self.restaurant_id = uuid4()
        self.product_ids = []
        self.database_url = os.environ["DATABASE_URL"].replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "INSERT INTO restaurants (id, name) VALUES (%s, %s)",
                (self.restaurant_id, "Products API Test Restaurant"),
            )
        self.merchant_headers = {
            "Authorization": f"Bearer {create_access_token(uuid4(), 'merchant')}"
        }

    def tearDown(self) -> None:
        if not hasattr(self, "restaurant_id"):
            return
        with MongoClient(os.environ["MONGO_URL"]) as client:
            client.deliveryapp.products.delete_many(
                {"restaurant_id": str(self.restaurant_id)}
            )
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                "DELETE FROM inventory WHERE restaurant_id = %s", (self.restaurant_id,)
            )
            connection.execute(
                "DELETE FROM restaurants WHERE id = %s", (self.restaurant_id,)
            )

    def _payload(self, product_id=None, name="Khao Soi") -> dict:
        product_id = product_id or uuid4()
        self.product_ids.append(product_id)
        return {
            "id": str(product_id),
            "restaurant_id": str(self.restaurant_id),
            "name": name,
            "price_satang": 6500,
            "initial_stock": 12,
            "attributes": {"spice_level": "medium", "toppings": ["chicken"]},
        }

    def test_create_list_pagination_and_duplicate_id(self) -> None:
        first = self._payload()
        second = self._payload(name="Pad Thai")
        for payload in (first, second):
            response = self.client.post(
                "/api/v1/products", json=payload, headers=self.merchant_headers
            )
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["attributes"], payload["attributes"])

        page = self.client.get(
            "/api/v1/products",
            params={"restaurant_id": str(self.restaurant_id), "limit": 1, "offset": 1},
        )
        self.assertEqual(page.status_code, 200, page.text)
        self.assertEqual(page.json()["total"], 2)
        self.assertEqual(len(page.json()["items"]), 1)
        self.assertEqual(page.json()["offset"], 1)

        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                "SELECT product_id, quantity FROM inventory WHERE restaurant_id = %s",
                (self.restaurant_id,),
            ).fetchall()
        self.assertEqual({str(row[0]) for row in rows}, {first["id"], second["id"]})
        self.assertTrue(all(row[1] == 12 for row in rows))

        duplicate = self.client.post(
            "/api/v1/products", json=first, headers=self.merchant_headers
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_validation_permissions_and_missing_restaurant(self) -> None:
        payload = self._payload()
        self.assertEqual(self.client.post("/api/v1/products", json=payload).status_code, 401)
        customer_headers = {
            "Authorization": f"Bearer {create_access_token(uuid4(), 'customer')}"
        }
        self.assertEqual(
            self.client.post("/api/v1/products", json=payload, headers=customer_headers).status_code,
            403,
        )
        for invalid in ({"price_satang": -1}, {"initial_stock": -1}, {"name": "  "}, {"price_satang": True}):
            response = self.client.post(
                "/api/v1/products", json={**payload, **invalid}, headers=self.merchant_headers
            )
            self.assertEqual(response.status_code, 422, response.text)
        missing = self.client.post(
            "/api/v1/products",
            json={**payload, "restaurant_id": str(uuid4())},
            headers=self.merchant_headers,
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            self.client.get("/api/v1/products", params={"restaurant_id": str(self.restaurant_id), "limit": 0}).status_code,
            422,
        )

    def test_mongo_failure_removes_new_inventory(self) -> None:
        payload = self._payload()
        with patch(
            "app.products.MongoClient",
            side_effect=ServerSelectionTimeoutError("simulated catalog outage"),
        ):
            response = self.client.post(
                "/api/v1/products", json=payload, headers=self.merchant_headers
            )
        self.assertEqual(response.status_code, 503, response.text)
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                "SELECT 1 FROM inventory WHERE product_id = %s", (payload["id"],)
            ).fetchone()
        self.assertIsNone(row)
