import os
import unittest
from contextlib import redirect_stdout
from io import StringIO

import psycopg
from pymongo import MongoClient

from scripts.seed_mongo import seed_mongo
from scripts.seed_postgres import product_id, seed_postgres
from scripts.verify_mongo import verify_mongo
from scripts.verify_postgres import verify_postgres


class TestSeedIdempotence(unittest.TestCase):
    def test_rerun_preserves_existing_stock_and_catalog_price(self) -> None:
        if not all(os.getenv(name) for name in ("DATABASE_URL", "MONGO_URL", "SEED_USER_PASSWORD")):
            self.skipTest("Seed database configuration is unavailable")

        database_url = os.environ["DATABASE_URL"].replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        item_id = product_id(0)
        with psycopg.connect(database_url) as connection:
            original_stock = connection.execute(
                "SELECT quantity FROM inventory WHERE product_id = %s", (item_id,)
            ).fetchone()[0]
            connection.execute(
                "UPDATE inventory SET quantity = %s WHERE product_id = %s",
                (original_stock + 7, item_id),
            )
        with MongoClient(os.environ["MONGO_URL"]) as client:
            products = client.deliveryapp.products
            original_price = products.find_one({"_id": item_id})["price_satang"]
            products.update_one({"_id": item_id}, {"$set": {"price_satang": original_price + 100}})

        try:
            seed_postgres()
            seed_mongo()
            self.assertTrue(verify_postgres())
            self.assertTrue(verify_mongo())
            with psycopg.connect(database_url) as connection:
                stock = connection.execute(
                    "SELECT quantity FROM inventory WHERE product_id = %s", (item_id,)
                ).fetchone()[0]
            with MongoClient(os.environ["MONGO_URL"]) as client:
                price = client.deliveryapp.products.find_one({"_id": item_id})["price_satang"]
            self.assertEqual(stock, original_stock + 7)
            self.assertEqual(price, original_price + 100)
        finally:
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    "UPDATE inventory SET quantity = %s WHERE product_id = %s",
                    (original_stock, item_id),
                )
            with MongoClient(os.environ["MONGO_URL"]) as client:
                client.deliveryapp.products.update_one(
                    {"_id": item_id}, {"$set": {"price_satang": original_price}}
                )

    def test_verifier_detects_orphan_inventory(self) -> None:
        if not all(os.getenv(name) for name in ("DATABASE_URL", "MONGO_URL")):
            self.skipTest("Database URLs are not configured")
        from uuid import uuid4

        from scripts.seed_postgres import restaurant_id

        database_url = os.environ["DATABASE_URL"].replace(
            "postgresql+psycopg://", "postgresql://", 1
        )
        orphan_id = uuid4()
        with psycopg.connect(database_url) as connection:
            connection.execute(
                "INSERT INTO inventory (product_id, restaurant_id, quantity) VALUES (%s, %s, 1)",
                (orphan_id, restaurant_id(0)),
            )
        try:
            output = StringIO()
            with redirect_stdout(output):
                self.assertFalse(verify_mongo())
            self.assertIn("Inventory has no matching product", output.getvalue())
        finally:
            with psycopg.connect(database_url) as connection:
                connection.execute(
                    "DELETE FROM inventory WHERE product_id = %s", (orphan_id,)
                )
