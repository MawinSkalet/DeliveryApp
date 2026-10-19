import os
from concurrent.futures import ThreadPoolExecutor
from unittest import TestCase
from unittest.mock import patch

import app.db as db
import app.mongo as mongo


class TestConnectionReuse(TestCase):
    def test_postgres_pool_is_initialized_once_for_concurrent_requests(self) -> None:
        previous_pool = db._pool
        db._pool = None
        self.addCleanup(setattr, db, "_pool", previous_pool)

        with (
            patch.object(db, "ConnectionPool") as pool_factory,
            patch.dict(
                os.environ,
                {"DB_POOL_MIN_SIZE": "2", "DB_POOL_MAX_SIZE": "50"},
            ),
        ):
            with ThreadPoolExecutor(max_workers=16) as executor:
                pools = list(executor.map(lambda _: db.get_pool(), range(32)))

        self.assertEqual(pool_factory.call_count, 1)
        self.assertTrue(all(pool is pool_factory.return_value for pool in pools))
        self.assertEqual(pool_factory.call_args.kwargs["max_size"], 50)

    def test_mongo_client_is_reused_and_closed(self) -> None:
        with (
            patch.object(mongo, "_client", None),
            patch.object(mongo, "MongoClient") as client_factory,
            patch.dict(os.environ, {"MONGO_URL": "mongodb://localhost"}),
        ):
            client = mongo.get_mongo_client()
            self.assertIs(mongo.get_mongo_client(), client)
            client_factory.assert_called_once_with(
                "mongodb://localhost",
                serverSelectionTimeoutMS=3000,
                maxPoolSize=50,
            )

            mongo.close_mongo_client()

        client.close.assert_called_once()


if __name__ == "__main__":
    import unittest

    unittest.main()
