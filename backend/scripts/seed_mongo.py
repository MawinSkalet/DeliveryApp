import os
from datetime import datetime, timezone

from pymongo import ASCENDING, DESCENDING, MongoClient, UpdateOne

from scripts.seed_postgres import product_id, restaurant_id, user_id


DISHES = [
    "Khao Soi", "Pad Thai", "Basil Chicken Rice", "Green Curry", "Chicken Rice",
    "Pork Noodle Soup", "Tom Yum Noodles", "Fried Rice", "Som Tam", "Grilled Pork Rice",
    "Mushroom Rice", "Vegetable Stir Fry", "Massaman Curry", "Panang Curry",
    "Chicken Satay", "Crispy Pork Rice", "Egg Noodles", "Rice Porridge",
    "Tofu Basil Rice", "Northern Sausage Rice",
]
VARIANTS = ["Classic", "Extra Egg", "Large", "Mild", "Spicy"]


def seed_mongo() -> None:
    with MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000) as client:
        db = client.deliveryapp
        if "products" not in db.list_collection_names():
            db.create_collection("products")
        if "rider_locations" not in db.list_collection_names():
            db.create_collection("rider_locations")

        db.products.create_index(
            [("restaurant_id", ASCENDING), ("active", ASCENDING), ("_id", ASCENDING)],
            name="restaurant_active_id",
        )
        db.rider_locations.create_index(
            [("rider_id", ASCENDING), ("updated_at", DESCENDING)],
            name="rider_latest_location",
        )

        product_writes = []
        for index in range(1000):
            dish = DISHES[index % len(DISHES)]
            variant = VARIANTS[(index // len(DISHES)) % len(VARIANTS)]
            restaurant_index = index // 100
            document = {
                "_id": product_id(index),
                "restaurant_id": restaurant_id(restaurant_index),
                "name": f"{dish} — {variant}",
                "price_satang": 4500 + (index % 20) * 250,
                "active": True,
                "attributes": {
                    "category": "meal",
                    "variant": variant,
                    "spice_level": "hot" if variant == "Spicy" else "regular",
                },
            }
            product_writes.append(
                UpdateOne({"_id": document["_id"]}, {"$setOnInsert": document}, upsert=True)
            )
        db.products.bulk_write(product_writes, ordered=False)

        locations = []
        for index in range(20):
            rider = user_id(80 + index)
            document = {
                "_id": rider,
                "rider_id": rider,
                "latitude": 18.795 + (index % 5) * 0.002,
                "longitude": 98.952 + (index // 5) * 0.003,
                "updated_at": datetime.now(timezone.utc),
            }
            locations.append(UpdateOne({"_id": rider}, {"$setOnInsert": document}, upsert=True))
        db.rider_locations.bulk_write(locations, ordered=False)

    print("MongoDB seed completed: 1000 products and 20 rider locations.")


if __name__ == "__main__":
    seed_mongo()
