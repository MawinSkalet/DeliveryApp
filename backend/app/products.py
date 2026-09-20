import os
from typing import Any
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from psycopg.errors import ForeignKeyViolation, UniqueViolation
from pymongo import ASCENDING, MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from app.errors import ApiError
from app.identity import current_user_claims

router = APIRouter(prefix="/api/v1/products", tags=["Products"])


class ProductInput(BaseModel):
    id: UUID | None = None
    restaurant_id: UUID
    name: str = Field(min_length=1, max_length=200)
    price_satang: int = Field(strict=True, ge=0)
    initial_stock: int = Field(strict=True, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


def _database_url() -> str:
    return os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)


def ensure_catalog_indexes() -> None:
    with MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000) as client:
        db = client.deliveryapp
        db.products.create_index(
            [("restaurant_id", ASCENDING), ("active", ASCENDING), ("_id", ASCENDING)],
            name="restaurant_active_id",
        )


def _public_product(document: dict) -> dict:
    return {
        "id": document["_id"],
        "restaurant_id": document["restaurant_id"],
        "name": document["name"],
        "price_satang": document["price_satang"],
        "active": document["active"],
        "attributes": document.get("attributes", {}),
    }


@router.get("")
def list_products(
    restaurant_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    query = {"restaurant_id": str(restaurant_id), "active": True}
    try:
        with MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000) as client:
            collection = client.deliveryapp.products
            total = collection.count_documents(query)
            documents = collection.find(query).sort("_id", ASCENDING).skip(offset).limit(limit)
            return {
                "items": [_public_product(document) for document in documents],
                "total": total,
                "limit": limit,
                "offset": offset,
            }
    except PyMongoError as error:
        raise ApiError(503, "CATALOG_UNAVAILABLE", "Product catalog is unavailable") from error


@router.post("", status_code=201)
def create_product(payload: ProductInput, claims: dict = Depends(current_user_claims)) -> dict:
    if claims.get("role") not in {"merchant", "admin"}:
        raise ApiError(403, "FORBIDDEN", "Merchant access required")

    product_id = payload.id or uuid4()
    document = {
        "_id": str(product_id),
        "restaurant_id": str(payload.restaurant_id),
        "name": payload.name,
        "price_satang": payload.price_satang,
        "active": True,
        "attributes": payload.attributes,
    }

    try:
        with psycopg.connect(_database_url()) as connection:
            restaurant = connection.execute(
                "SELECT 1 FROM restaurants WHERE id = %s", (payload.restaurant_id,)
            ).fetchone()
            if restaurant is None:
                raise ApiError(404, "RESTAURANT_NOT_FOUND", "Restaurant not found")
            connection.execute(
                "INSERT INTO inventory (product_id, restaurant_id, quantity) VALUES (%s, %s, %s)",
                (product_id, payload.restaurant_id, payload.initial_stock),
            )
    except (UniqueViolation, ForeignKeyViolation) as error:
        if isinstance(error, UniqueViolation):
            raise ApiError(409, "PRODUCT_ALREADY_EXISTS", "Product ID already exists") from error
        raise ApiError(404, "RESTAURANT_NOT_FOUND", "Restaurant not found") from error
    except psycopg.Error as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Inventory database is unavailable") from error

    try:
        with MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000) as client:
            client.deliveryapp.products.insert_one(document)
    except (PyMongoError, DuplicateKeyError) as error:
        # MongoDB writes cannot share the PostgreSQL transaction. Remove the new
        # stock row when catalog publication fails; verification catches any
        # orphan left by a process crash or an ambiguous network failure.
        try:
            with psycopg.connect(_database_url()) as connection:
                connection.execute("DELETE FROM inventory WHERE product_id = %s", (product_id,))
        except psycopg.Error as cleanup_error:
            raise ApiError(503, "RECONCILIATION_REQUIRED", "Product creation needs reconciliation") from cleanup_error
        if isinstance(error, DuplicateKeyError):
            raise ApiError(409, "PRODUCT_ALREADY_EXISTS", "Product ID already exists") from error
        raise ApiError(503, "CATALOG_UNAVAILABLE", "Product catalog is unavailable") from error

    return _public_product(document)
