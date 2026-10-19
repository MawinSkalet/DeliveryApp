from unittest import TestCase
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.products import list_products


class TestProductListProjection(TestCase):
    def test_list_fetches_only_public_product_fields(self) -> None:
        restaurant_id = uuid4()
        product = {
            "_id": str(uuid4()),
            "restaurant_id": str(restaurant_id),
            "name": "Khao Soi",
            "price_satang": 6500,
            "active": True,
            "attributes": {"spice_level": "medium"},
        }
        client = MagicMock()
        collection = client.deliveryapp.products
        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.skip.return_value = cursor
        cursor.limit.return_value = [product]
        collection.find.return_value = cursor
        collection.count_documents.return_value = 1

        with patch("app.products.get_mongo_client", return_value=client):
            result = list_products(restaurant_id, limit=10, offset=0)

        collection.count_documents.assert_called_once_with(
            {"restaurant_id": str(restaurant_id), "active": True}
        )
        collection.find.assert_called_once_with(
            {"restaurant_id": str(restaurant_id), "active": True},
            {
                "restaurant_id": 1,
                "name": 1,
                "price_satang": 1,
                "active": 1,
                "attributes": 1,
            },
        )
        self.assertEqual(result["items"][0]["id"], product["_id"])
