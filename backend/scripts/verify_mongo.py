import os
from uuid import UUID

import psycopg
from pymongo import MongoClient

from scripts.seed_postgres import product_id, restaurant_id, user_id


def verify_mongo() -> bool:
    errors: list[str] = []
    with MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000, tz_aware=True) as client:
        db = client.deliveryapp
        collection_names = set(db.list_collection_names())
        print(f"[CHECK] MongoDB collections: {sorted(collection_names)}")
        if not {"products", "rider_locations"}.issubset(collection_names):
            errors.append("products and rider_locations collections are required")

        product_count = db.products.count_documents({})
        location_count = db.rider_locations.count_documents({})
        print(f"[CHECK] Products: {product_count}; rider locations: {location_count}")
        if product_count < 1000 or product_count + location_count < 1000:
            errors.append("MongoDB needs at least 1000 seeded product documents")
        if location_count < 20:
            errors.append("MongoDB needs at least 20 rider locations")
        if "restaurant_active_id" not in db.products.index_information():
            errors.append("Missing restaurant_active_id product index")
        if "rider_latest_location" not in db.rider_locations.index_information():
            errors.append("Missing rider_latest_location index")

        products = list(db.products.find({}, {"restaurant_id": 1, "name": 1, "price_satang": 1, "active": 1, "attributes": 1}))
        for document in products:
            try:
                UUID(document["_id"])
                UUID(document["restaurant_id"])
            except (KeyError, ValueError, TypeError, AttributeError):
                errors.append(f"Invalid product IDs: {document.get('_id')}")
                continue
            price = document.get("price_satang")
            if (
                not isinstance(document.get("name"), str)
                or not document["name"].strip()
                or not isinstance(price, int)
                or isinstance(price, bool)
                or price < 0
                or document.get("active") is not True
                or not isinstance(document.get("attributes"), dict)
            ):
                errors.append(f"Invalid product fields: {document['_id']}")

        by_id = {document["_id"]: document for document in products}
        for index in range(1000):
            product = by_id.get(product_id(index))
            if product is None or product.get("restaurant_id") != restaurant_id(index // 100):
                errors.append(f"Missing or mismatched seeded product {index}")

        location_ids = set()
        for document in db.rider_locations.find({}):
            location_ids.add(document.get("rider_id"))
            if (
                document.get("_id") != document.get("rider_id")
                or not isinstance(document.get("latitude"), (int, float))
                or not isinstance(document.get("longitude"), (int, float))
                or not 18.7 <= document["latitude"] <= 18.9
                or not 98.8 <= document["longitude"] <= 99.1
                or not getattr(document.get("updated_at"), "tzinfo", None)
            ):
                errors.append(f"Invalid rider location: {document.get('_id')}")
        for index in range(80, 100):
            if user_id(index) not in location_ids:
                errors.append(f"Missing seeded rider location {index}")

    database_url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(database_url) as connection:
        inventory = {
            str(row[0]): str(row[1])
            for row in connection.execute("SELECT product_id, restaurant_id FROM inventory")
        }
    for document in products:
        if inventory.get(document["_id"]) != document.get("restaurant_id"):
            errors.append(f"Product has no matching inventory: {document['_id']}")
    for index in range(1000):
        if inventory.get(product_id(index)) != restaurant_id(index // 100):
            errors.append(f"Seeded inventory mismatch for product {index}")

    if errors:
        for error in errors[:20]:
            print(f"[FAIL] {error}")
        if len(errors) > 20:
            print(f"[FAIL] ... and {len(errors) - 20} more errors")
        return False
    print("[PASS] MongoDB seed, indexes, and PostgreSQL inventory match.")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if verify_mongo() else 1)
