# Checkpoint 1 submission

The CP1 handout requires a code repository. The assignment upload instructions allow two submission options: **upload the project as a ZIP file**, or provide a public Google Drive/OneDrive link. **Only one team member submits for the whole team; the score is shared equally.** This guide uses the ZIP option; no public cloud sharing is needed.

Create the upload file from the checked-in source with:

```bash
python tools/package_cp1.py
```

Upload `dist/DeliveryApp_CP1_submission.zip` to the assignment's file-upload field. The ZIP contains the source, migrations, seed scripts, README, and the [testing guide](cp1-testing.md). It excludes the local `.env`, Git history folder, caches, database files, and generated build output. The `dist/` folder is ignored by Git. Do not upload `.env` separately.

The project repository remains available at the URL below for the instructor to inspect the commit history and CI:

**Repository:** https://github.com/MawinSkalet/DeliveryApp

**Project:** Food delivery around Chiang Mai University

| Student ID | Member | CP1 work to explain |
| --- | --- | --- |
| 670615020 | Jirasak Boonsom | Compose setup, Orders, Products, cross-database integration, CI |
| 670615035 | Supanat Pudhom | Users API, account migration, PostgreSQL seed and tests |
| 650615037 | Anakin arsa | Scope and handoff documentation |

The dedicated CP1 sheet states a deadline at the **end of Week 11** (although its heading says Week 8). Check the course announcement for the exact calendar date.

## Optional upload description

> DeliveryApp implements a FastAPI food-delivery backend using PostgreSQL for accounts, orders, and inventory, and MongoDB for the product catalog and rider-location documents. The attached ZIP contains Docker Compose, Alembic migrations, reproducible seed scripts for more than 1,000 records/documents in each database, all five required CP1 API routes, a root README with the team roster and architecture diagram, and automated integration checks. The source and commit history are also available at https://github.com/MawinSkalet/DeliveryApp.

## Requirement-to-evidence checklist

| CP1 requirement | Repository evidence | Verification command or result |
| --- | --- | --- |
| Root Compose with persistent PostgreSQL and MongoDB | [`docker-compose.yml`](../docker-compose.yml) | `docker compose up -d --build --wait`; `docker compose ps` |
| PostgreSQL transactional model, PK/FK/indexes, at least three tables | [`0001_order_baseline`](../backend/migrations/versions/0001_order_baseline.py), [`0002_user_accounts`](../backend/migrations/versions/0002_user_accounts.py), [data model](data-model.md) | Migrations apply when API starts; seven relational tables |
| MongoDB flexible documents, at least two collections | [`seed_mongo.py`](../backend/scripts/seed_mongo.py), [`verify_mongo.py`](../backend/scripts/verify_mongo.py) | `products` and `rider_locations`, with query indexes |
| Reproducible seed, at least 1,000 records/documents per database | [`seed.py`](../backend/scripts/seed.py), [`verify_seed.py`](../backend/scripts/verify_seed.py) | 10 restaurants + 101 users + 1,000 inventory rows; 1,000 products + 20 rider locations |
| `POST /api/v1/users` and `GET /api/v1/users/{id}` | [`users.py`](../backend/app/users.py) | `scripts.smoke_cp1` prints 201 and 200 |
| Paginated `GET /api/v1/products` and dynamic `POST /api/v1/products` | [`products.py`](../backend/app/products.py) | `scripts.smoke_cp1` prints 200 and 201 |
| `POST /api/v1/orders` uses PostgreSQL + MongoDB | [`orders.py`](../backend/app/orders.py), [API contract](api-contract.md) | `scripts.smoke_cp1` prints 201 and confirms stock 3 → 2 |
| Standard JSON responses and 200/201/400/404 status codes | [`errors.py`](../backend/app/errors.py), [API contract](api-contract.md) | Unit tests and `scripts.smoke_orders` cover validation and missing records |
| README setup, roster, architecture diagram, API summary | [root README](../README.md) | Open the README and Swagger at `http://localhost:8000/docs` |
| Git history and checks | [commits](https://github.com/MawinSkalet/DeliveryApp/commits/main), [GitHub Actions](https://github.com/MawinSkalet/DeliveryApp/actions) | Show contributions and successful backend/frontend/integration jobs |

`POST /api/v1/orders` reads the MongoDB product name and price, validates that the product belongs to the restaurant, then locks PostgreSQL inventory and commits the order, items, status history, and stock decrement in one PostgreSQL transaction. This uses both databases for the order flow while keeping transactional state in PostgreSQL, as the CP1 objectives specify. It is not a distributed atomic commit across the two database engines.

## Verify before upload

Clone the repository, copy `.env.example` to `.env`, replace the local placeholder credentials and `AUTH_SECRET`, and set `SEED_USER_PASSWORD` to a local demo password of at least eight characters. Never commit `.env`. Then run:

```bash
docker compose up -d --build --wait
docker compose exec -T api python -m scripts.seed
docker compose exec -T api python -m scripts.verify_seed
docker compose exec -T api python -m scripts.smoke_cp1
```

The smoke script prints the HTTP result for each required route and removes its temporary customer, restaurant, product, and order afterward. The [testing guide](cp1-testing.md) covers the full local check, expected results, frontend build, GitHub Actions, and ZIP verification. Swagger is available at `http://localhost:8000/docs`.

The rubric also assesses balanced Git contributions. The current history has work from all three members but is not evenly distributed because the final CP1 integration was completed under Jirasak's identity. Present the history honestly; do not fabricate or reassign commits.
