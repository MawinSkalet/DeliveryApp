# Teammate A — Users and PostgreSQL

Historical assignment brief: this work is implemented and verified in the current CP1 branch. Use the root README for current setup commands.

## Mission

Make customer accounts usable by the existing Orders API and provide the PostgreSQL half of the CP1 dataset. Own Users and PostgreSQL schema changes; do not reimplement Orders.

## Read first

- [README](../README.md): Compose commands and URLs
- [Order authentication dependency](../backend/app/identity.py): exact token contract
- [Baseline migration](../backend/migrations/versions/0001_order_baseline.py): existing tables
- [Shared seed contract](seed-contract.md): IDs and counts
- [API contract](api-contract.md): JSON and error conventions

## Start

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/users-postgres
cp .env.example .env
docker compose up -d --build
docker compose exec api alembic upgrade head
```

On PowerShell, use `Copy-Item .env.example .env`. Change local passwords and `AUTH_SECRET` in `.env`, and adjust host ports if occupied. Keep `.env` out of Git.

## Build in this order

1. Add an Alembic revision after `0001_order_baseline` for missing account fields such as `password_hash` and `role`. Keep `users.id` as UUID, reject email duplicates that differ only by letter case, and preserve existing foreign keys. If existing rows need a new non-null column, backfill before adding the constraint. If merchant ownership is needed for product writes, add it here. Do not edit the baseline revision.
2. Implement `POST /api/v1/users` for registration, `GET /api/v1/users/{id}` for an authorized read, and `POST /api/v1/auth/login`. Validate input, hash passwords before storing, never return a password hash, and return `409` for duplicate email. Use the shared JSON error shape in `app/errors.py`.
3. Login must issue an HS256 bearer token signed with `AUTH_SECRET`, containing `sub` (user UUID string), `role: "customer"`, and `exp` (future Unix timestamp). Orders already verifies these claims. Never commit the signing secret.
4. Add `backend/scripts/seed_postgres.py` using [seed-contract.md](seed-contract.md). Insert users (including rider-role IDs 80–99), restaurants, and inventory with stable IDs. Rerunning seed must not reset stock or passwords.
5. Add `backend/scripts/verify_postgres.py` to check counts, constraints, and inventory-to-restaurant relations. The top-level `scripts.seed` and `scripts.verify_seed` wrappers are now implemented.
6. Add tests for registration, duplicate email in different letter case, invalid login, token claims, authorized reads, and repeated seed runs. The existing `scripts.smoke_orders` inserts only `id`, `email`, and `name`; update its disposable fixtures in the same PR if your new user columns require values. Extend CI to run tests on a test database.

## Orders integration contract

Every order request uses `Authorization: Bearer <token>`. [Orders](../backend/app/orders.py) reads `sub`, `role`, and `exp`, then checks that `sub` exists in PostgreSQL `users`. A customer token must work for order creation; another user's token must not reveal the order. Seeded PostgreSQL inventory IDs must match B's MongoDB product IDs.

## Definition of done

- Migration succeeds from a fresh database without changing `0001_order_baseline`.
- A newly registered customer can log in and receive a token accepted by Orders.
- Duplicate email and invalid login return appropriate errors.
- PostgreSQL has at least 1,000 records; rerunning seed changes neither counts nor existing stock.
- Tests and the existing Orders smoke test pass; the PR states test commands, migration notes, and new environment variables.
