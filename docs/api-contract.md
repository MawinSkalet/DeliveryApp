# API contract

Base path: `/api/v1`. Requests and responses use JSON. IDs are UUID strings, timestamps are ISO 8601 UTC, and money is integer satang in API payloads. Error responses use `{"error":{"code":"...","message":"...","details":{}}}`.

| Method | Route | Status | Access |
| --- | --- | --- | --- |
| POST | `/users` | Implemented | Public; registers `customer` or `rider` |
| POST | `/auth/login` | Implemented | Public; returns HS256 bearer token |
| GET | `/users/{id}` | Implemented | Own account or admin |
| GET | `/products` | Implemented | Public; requires `restaurant_id`, supports `limit` and `offset` |
| POST | `/products` | Implemented | Merchant or admin bearer token |
| POST | `/orders` | Implemented | Customer bearer token and `Idempotency-Key` |
| GET | `/orders`, `/orders/{id}` | Implemented | Own orders only |
| POST | `/orders/{id}/cancel` | Implemented | Own placed order only |
| POST/GET | `/deliveries/{id}/locations` | Later milestone | Assigned rider / authorized customer |

`POST /users` accepts `email`, `name`, `password` (at least eight characters), and optional `role` (`customer` by default). A case-insensitive duplicate email returns `409`. `POST /auth/login` accepts `email` and `password` and returns `access_token`, `token_type: "bearer"`, and a user summary. Tokens contain `sub` (user UUID), `role`, and `exp` and use the configured `AUTH_SECRET`.

`GET /products` requires a restaurant UUID and accepts `limit` 1–100 (default 20) and `offset` at least 0 (default 0). It returns active products sorted by UUID with `items`, `total`, `limit`, and `offset`. `POST /products` accepts this shape:

```json
{
  "restaurant_id": "4b6b748e-c8ba-4b06-bda5-981bf9cebe32",
  "name": "Khao Soi Chicken",
  "price_satang": 6500,
  "initial_stock": 12,
  "attributes": {"spice_level": "medium", "toppings": ["chicken"]}
}
```

An optional `id` UUID lets an integration client choose a product ID; duplicate IDs return `409`. Product creation checks that the restaurant exists, inserts matching PostgreSQL inventory, then publishes the MongoDB product. If MongoDB rejects the write, the API removes the new inventory row. A crash or ambiguous network outcome can still require reconciliation; `scripts.verify_seed` reports mismatches.

`POST /orders` reads the MongoDB product document, snapshots its name and price, and inserts the order while locking/decrementing PostgreSQL inventory in one PostgreSQL transaction:

```json
{
  "restaurant_id": "4b6b748e-c8ba-4b06-bda5-981bf9cebe32",
  "items": [{"product_id": "9b9fdbb9-4b46-4b40-8c1b-00fa95d982f8", "quantity": 2}]
}
```

The required `Idempotency-Key` header is 1–128 characters. The first successful order returns `201`; an identical replay returns `200` with the same order; reusing the key with a different body returns `409`. Missing/invalid tokens return `401`, wrong roles return `403`, missing records return `404`, invalid payloads return `422`, and unavailable databases return `503`.
