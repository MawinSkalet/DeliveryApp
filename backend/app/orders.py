import hashlib
import json
import os
from contextlib import AbstractContextManager
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError

from app.db import get_connection
from app.errors import ApiError
from app.identity import current_customer_id
from app.mongo import get_mongo_client

router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


class OrderItemInput(BaseModel):
    product_id: UUID
    quantity: int = Field(ge=1, le=100)


class OrderInput(BaseModel):
    restaurant_id: UUID
    items: list[OrderItemInput] = Field(min_length=1, max_length=100)


def _connection() -> AbstractContextManager[psycopg.Connection]:
    return get_connection()


def _products(product_ids: list[str]) -> dict[str, dict]:
    try:
        documents = get_mongo_client().deliveryapp.products.find(
            {"_id": {"$in": product_ids}}
        )
        return {document["_id"]: document for document in documents}
    except PyMongoError as error:
        raise ApiError(503, "CATALOG_UNAVAILABLE", "Product catalog is unavailable") from error


def _order(connection: psycopg.Connection, order_id: UUID, customer_id: UUID) -> dict:
    row = connection.execute(
        """SELECT id, customer_id, restaurant_id, status, subtotal_satang,
                  delivery_fee, total_satang, created_at
           FROM orders WHERE id = %s AND customer_id = %s""",
        (order_id, customer_id),
    ).fetchone()
    if row is None:
        raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
    items = connection.execute(
        """SELECT product_id, product_name, quantity, unit_price_satang, line_total_satang
           FROM order_items WHERE order_id = %s ORDER BY product_id""",
        (order_id,),
    ).fetchall()
    return _serialize_order(row, items)


def _serialize_order(row: dict, items: list[dict]) -> dict:
    return {
        "id": str(row["id"]),
        "customer_id": str(row["customer_id"]),
        "restaurant_id": str(row["restaurant_id"]),
        "status": row["status"],
        "subtotal_satang": row["subtotal_satang"],
        "delivery_fee_satang": int(row["delivery_fee"] * 100),
        "total_satang": row["total_satang"],
        "created_at": row["created_at"].isoformat(),
        "items": [
            {**item, "product_id": str(item["product_id"])} for item in items
        ],
    }


def _request_hash(body: OrderInput) -> str:
    canonical = {
        "restaurant_id": str(body.restaurant_id),
        "items": sorted(
            [(str(item.product_id), item.quantity) for item in body.items]
        ),
    }
    return hashlib.sha256(json.dumps(canonical, sort_keys=True).encode()).hexdigest()


@router.post("", status_code=201)
def create_order(
    body: OrderInput,
    response: Response,
    x_user_id: UUID = Depends(current_customer_id),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=1, max_length=128),
) -> dict:
    product_ids = [str(item.product_id) for item in body.items]
    if len(product_ids) != len(set(product_ids)):
        raise ApiError(400, "DUPLICATE_PRODUCT", "Each product may appear only once")

    request_hash = _request_hash(body)
    try:
        with _connection() as connection:
            # The advisory lock serializes retries for the same customer and key.
            with connection.pipeline():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (f"{x_user_id}:{idempotency_key}",),
                )
                existing_cursor = connection.execute(
                    "SELECT id, request_hash FROM orders WHERE customer_id = %s AND idempotency_key = %s",
                    (x_user_id, idempotency_key),
                )
            existing = existing_cursor.fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise ApiError(409, "IDEMPOTENCY_CONFLICT", "Idempotency key was used for a different order")
                response.status_code = 200
                return _order(connection, existing["id"], x_user_id)

            participants = connection.execute(
                """SELECT EXISTS (SELECT 1 FROM users WHERE id = %s) AS customer_exists,
                          EXISTS (SELECT 1 FROM restaurants WHERE id = %s) AS restaurant_exists""",
                (x_user_id, body.restaurant_id),
            ).fetchone()
            if not participants["customer_exists"] or not participants["restaurant_exists"]:
                raise ApiError(404, "PARTICIPANT_NOT_FOUND", "Customer or restaurant not found")

            catalog = _products(product_ids)
            for product_id in product_ids:
                product = catalog.get(product_id)
                if (
                    product is None
                    or product.get("restaurant_id") != str(body.restaurant_id)
                    or product.get("active") is not True
                    or not isinstance(product.get("price_satang"), int)
                    or isinstance(product.get("price_satang"), bool)
                    or product["price_satang"] < 0
                    or not isinstance(product.get("name"), str)
                    or not product["name"]
                ):
                    raise ApiError(404, "PRODUCT_NOT_FOUND", "Product is unavailable at this restaurant")

            quantities = {str(item.product_id): item.quantity for item in body.items}
            stock_rows = connection.execute(
                """SELECT product_id, quantity FROM inventory
                   WHERE restaurant_id = %s AND product_id = ANY(%s)
                   ORDER BY product_id FOR UPDATE""",
                (body.restaurant_id, [UUID(product_id) for product_id in product_ids]),
            ).fetchall()
            stock_by_product = {str(row["product_id"]): row["quantity"] for row in stock_rows}
            if any(
                stock_by_product.get(product_id, 0) < quantities[product_id]
                for product_id in product_ids
            ):
                raise ApiError(409, "OUT_OF_STOCK", "Insufficient stock")

            subtotal = sum(catalog[product_id]["price_satang"] * quantities[product_id] for product_id in product_ids)
            fee = int(os.getenv("DELIVERY_FEE_SATANG", "1500"))
            order_id = uuid4()
            response_items = []
            with connection.pipeline():
                order_cursor = connection.execute(
                    """INSERT INTO orders
                       (id, customer_id, restaurant_id, status, subtotal_satang,
                        delivery_fee, total_satang, idempotency_key, request_hash)
                       VALUES (%s, %s, %s, 'PLACED', %s, %s, %s, %s, %s)
                       RETURNING id, customer_id, restaurant_id, status, subtotal_satang,
                                 delivery_fee, total_satang, created_at""",
                    (
                        order_id, x_user_id, body.restaurant_id, subtotal,
                        Decimal(fee) / 100, subtotal + fee, idempotency_key, request_hash,
                    ),
                )
                for product_id in product_ids:
                    product = catalog[product_id]
                    quantity = quantities[product_id]
                    connection.execute(
                        """INSERT INTO order_items
                           (id, order_id, product_id, product_name, quantity,
                            unit_price_satang, line_total_satang)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            uuid4(), order_id, UUID(product_id), product["name"], quantity,
                            product["price_satang"], product["price_satang"] * quantity,
                        ),
                    )
                    connection.execute(
                        "UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s",
                        (quantity, UUID(product_id)),
                    )
                    response_items.append(
                        {
                            "product_id": UUID(product_id),
                            "product_name": product["name"],
                            "quantity": quantity,
                            "unit_price_satang": product["price_satang"],
                            "line_total_satang": product["price_satang"] * quantity,
                        }
                    )
                connection.execute(
                    "INSERT INTO order_status_history (id, order_id, status) VALUES (%s, %s, 'PLACED')",
                    (uuid4(), order_id),
                )
            order_row = order_cursor.fetchone()
            response_items.sort(key=lambda item: str(item["product_id"]))
            return _serialize_order(order_row, response_items)
    except psycopg.Error as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Order database is unavailable") from error


@router.get("/{order_id}")
def get_order(order_id: UUID, x_user_id: UUID = Depends(current_customer_id)) -> dict:
    try:
        with _connection() as connection:
            return _order(connection, order_id, x_user_id)
    except psycopg.Error as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Order database is unavailable") from error


@router.get("")
def list_orders(
    x_user_id: UUID = Depends(current_customer_id),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    try:
        with _connection() as connection:
            rows = connection.execute(
                """WITH page AS (
                       SELECT id, customer_id, restaurant_id, status, subtotal_satang,
                              delivery_fee, total_satang, created_at
                       FROM orders
                       WHERE customer_id = %s
                       ORDER BY created_at DESC, id DESC
                       LIMIT %s OFFSET %s
                   )
                   SELECT page.id, page.customer_id, page.restaurant_id, page.status,
                          page.subtotal_satang, page.delivery_fee, page.total_satang, page.created_at,
                          i.product_id AS item_product_id, i.product_name,
                          i.quantity AS item_quantity, i.unit_price_satang,
                          i.line_total_satang
                   FROM page
                   LEFT JOIN order_items AS i ON i.order_id = page.id
                   ORDER BY page.created_at DESC, page.id DESC, i.product_id""",
                (x_user_id, limit, offset),
            ).fetchall()
            orders: dict[UUID, dict] = {}
            for row in rows:
                order = orders.get(row["id"])
                if order is None:
                    order = {
                        "id": str(row["id"]),
                        "customer_id": str(row["customer_id"]),
                        "restaurant_id": str(row["restaurant_id"]),
                        "status": row["status"],
                        "subtotal_satang": row["subtotal_satang"],
                        "delivery_fee_satang": int(row["delivery_fee"] * 100),
                        "total_satang": row["total_satang"],
                        "created_at": row["created_at"].isoformat(),
                        "items": [],
                    }
                    orders[row["id"]] = order
                if row["item_product_id"] is not None:
                    order["items"].append(
                        {
                            "product_id": str(row["item_product_id"]),
                            "product_name": row["product_name"],
                            "quantity": row["item_quantity"],
                            "unit_price_satang": row["unit_price_satang"],
                            "line_total_satang": row["line_total_satang"],
                        }
                    )
            return {"items": list(orders.values()), "limit": limit, "offset": offset}
    except psycopg.Error as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Order database is unavailable") from error


@router.post("/{order_id}/cancel")
def cancel_order(order_id: UUID, x_user_id: UUID = Depends(current_customer_id)) -> dict:
    try:
        with _connection() as connection:
            row = connection.execute(
                """SELECT id, customer_id, restaurant_id, status, subtotal_satang,
                          delivery_fee, total_satang, created_at
                   FROM orders WHERE id = %s AND customer_id = %s FOR UPDATE""",
                (order_id, x_user_id),
            ).fetchone()
            if row is None:
                raise ApiError(404, "ORDER_NOT_FOUND", "Order not found")
            if row["status"] == "CANCELLED":
                items = connection.execute(
                    """SELECT product_id, product_name, quantity, unit_price_satang, line_total_satang
                       FROM order_items WHERE order_id = %s ORDER BY product_id""",
                    (order_id,),
                ).fetchall()
                return _serialize_order(row, items)
            if row["status"] != "PLACED":
                raise ApiError(409, "CANNOT_CANCEL", "Only placed orders may be cancelled")
            items = connection.execute(
                """SELECT product_id, product_name, quantity, unit_price_satang, line_total_satang
                   FROM order_items WHERE order_id = %s ORDER BY product_id""",
                (order_id,),
            ).fetchall()
            with connection.pipeline():
                for item in items:
                    connection.execute(
                        "UPDATE inventory SET quantity = quantity + %s WHERE product_id = %s",
                        (item["quantity"], item["product_id"]),
                    )
                connection.execute("UPDATE orders SET status = 'CANCELLED' WHERE id = %s", (order_id,))
                connection.execute(
                    "INSERT INTO order_status_history (id, order_id, status) VALUES (%s, %s, 'CANCELLED')",
                    (uuid4(), order_id),
                )
            row["status"] = "CANCELLED"
            return _serialize_order(row, items)
    except psycopg.Error as error:
        raise ApiError(503, "DATABASE_UNAVAILABLE", "Order database is unavailable") from error
