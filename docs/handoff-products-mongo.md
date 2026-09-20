# Teammate B — Products and MongoDB

Historical assignment brief: this work is implemented and verified in the current CP1 branch. Use the root README for current setup commands.

## Mission

Make catalog products readable and orderable by the existing Orders API and provide the MongoDB half of CP1 data. Own Products, MongoDB indexes, and MongoDB seed. Tracking can follow after core CP1 work.

## Read first

- [README](../README.md): Compose commands and URLs
- [Orders product lookup](../backend/app/orders.py): exact checkout fields
- [API contract](api-contract.md): JSON and error conventions
- [Shared seed contract](seed-contract.md): product and restaurant IDs
- [Baseline migration](../backend/migrations/versions/0001_order_baseline.py): `inventory` structure

## Start

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/products-mongo
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
```

On PowerShell, use `Copy-Item .env.example .env`. Change local passwords and `AUTH_SECRET` in `.env`. Keep `.env` out of Git.

## Build in this order

1. Create `deliveryapp.products` and indexes for catalog queries, at minimum `restaurant_id` plus `active`. Create `rider_locations` as the second CP1 MongoDB collection and an index for its latest-location query, even if the Tracking API comes later.
2. Implement `GET /api/v1/products` with a required restaurant filter, predictable ordering, and pagination (`limit` 1–100; `offset` at least 0). Implement `POST /api/v1/products` with validation for nonempty name, nonnegative integer `price_satang`, `restaurant_id`, nonnegative initial stock, and dynamic `attributes`. Agree on merchant authorization with A before exposing product writes in a shared deployment.
3. Store each MongoDB document with `_id` as a UUID string, `restaurant_id` as the matching PostgreSQL restaurant UUID string, `name` as a nonempty string, `price_satang` as an integer, and `active` as a boolean. Optional `attributes` is an object. Create a PostgreSQL `inventory` row whose `product_id` equals MongoDB `_id`.
4. Product creation makes two writes, not an atomic distributed transaction. Document retry/reconciliation for partial failures. A safe starting order is inventory first, then MongoDB; if MongoDB fails, remove the unused inventory row or record it for retry. Do not present a product as orderable until both records exist.
5. Add `backend/scripts/seed_mongo.py` using [seed-contract.md](seed-contract.md): 1,000 products and at least 20 rider locations with stable IDs. Rerunning seed must not overwrite changed prices or locations.
6. Add `backend/scripts/verify_mongo.py`: check counts, indexes, required fields, UUID formats, restaurant IDs, and a matching PostgreSQL inventory row for every seeded product. The top-level `scripts.seed` and `scripts.verify_seed` wrappers are now implemented.
7. Add tests for pagination, filtering, invalid price/stock, duplicate IDs, repeated seed runs, and missing inventory. Keep the existing `scripts.smoke_orders` product fixtures valid under any new MongoDB schema validation, or update them in the same PR. Extend CI to run tests against test databases.

## Orders integration contract

Orders queries `deliveryapp.products` by `_id`. It accepts a document only when `restaurant_id` matches the order, `active` is exactly `true`, `price_satang` is a nonnegative integer, and `name` is nonempty. Orders snapshots name and price at purchase and decrements stock only in PostgreSQL. Do not change shared field names without updating Orders and the API contract in the same PR.

## Definition of done

- Products create/list works with validation, restaurant filtering, and pagination.
- A created product has matching PostgreSQL inventory and can be ordered.
- MongoDB has at least 1,000 product documents and a second collection; repeated seed does not increase counts or overwrite data.
- Cross-database verification and the Orders smoke test pass; the PR states test commands, indexes, and new environment variables.
