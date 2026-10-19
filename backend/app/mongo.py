import os
from threading import Lock

from pymongo import MongoClient

_client: MongoClient | None = None
_client_lock = Lock()


def get_mongo_client() -> MongoClient:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = MongoClient(
                    os.environ["MONGO_URL"],
                    serverSelectionTimeoutMS=3000,
                    maxPoolSize=50,
                )
    return _client


def close_mongo_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None
