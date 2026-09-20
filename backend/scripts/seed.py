"""Seed PostgreSQL first, then the matching MongoDB catalog and locations."""

from scripts.seed_mongo import seed_mongo
from scripts.seed_postgres import seed_postgres


if __name__ == "__main__":
    seed_postgres()
    seed_mongo()
