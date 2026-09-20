"""Verify the CP1 dataset and its cross-database product/inventory links."""

from scripts.verify_mongo import verify_mongo
from scripts.verify_postgres import verify_postgres


if __name__ == "__main__":
    postgres_ok = verify_postgres()
    mongo_ok = verify_mongo()
    raise SystemExit(0 if postgres_ok and mongo_ok else 1)
