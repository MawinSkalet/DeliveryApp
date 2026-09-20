# Checkpoint 1 submission and instructor audit

The CP1 handout specifies a code repository and a 10-minute instructor evaluation audit. The assignment upload instructions add two submission options: **upload the project as a ZIP file**, or provide a public Google Drive/OneDrive link. **Only one team member submits for the whole team; the score is shared equally.** This guide uses the ZIP option; no public cloud sharing is needed.

Create the upload file from the checked-in source with:

```bash
python tools/package_cp1.py
```

Upload `dist/DeliveryApp_CP1_submission.zip` to the assignment's file-upload field. The ZIP contains the source, migrations, seed scripts, README, and this audit guide. It excludes the local `.env`, Git history folder, caches, database files, and generated build output. The `dist/` folder is ignored by Git. Do not upload `.env` separately.

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

| CP1 requirement | Repository evidence | Audit command or result |
| --- | --- | --- |
| Root Compose with persistent PostgreSQL and MongoDB | [`docker-compose.yml`](../docker-compose.yml) | `docker compose up -d --build --wait`; `docker compose ps` |
| PostgreSQL transactional model, PK/FK/indexes, at least three tables | [`0001_order_baseline`](../backend/migrations/versions/0001_order_baseline.py), [`0002_user_accounts`](../backend/migrations/versions/0002_user_accounts.py), [data model](data-model.md) | Migrations apply when API starts; seven relational tables |
| MongoDB flexible documents, at least two collections | [`seed_mongo.py`](../backend/scripts/seed_mongo.py), [`verify_mongo.py`](../backend/scripts/verify_mongo.py) | `products` and `rider_locations`, with query indexes |
| Reproducible seed, at least 1,000 records/documents per database | [`seed.py`](../backend/scripts/seed.py), [`verify_seed.py`](../backend/scripts/verify_seed.py) | 10 restaurants + 101 users + 1,000 inventory rows; 1,000 products + 20 rider locations |
| `POST /api/v1/users` and `GET /api/v1/users/{id}` | [`users.py`](../backend/app/users.py) | `scripts.smoke_cp1` prints 201 and 200 |
| Paginated `GET /api/v1/products` and dynamic `POST /api/v1/products` | [`products.py`](../backend/app/products.py) | `scripts.smoke_cp1` prints 200 and 201 |
| `POST /api/v1/orders` uses PostgreSQL + MongoDB | [`orders.py`](../backend/app/orders.py), [API contract](api-contract.md) | `scripts.smoke_cp1` prints 201 and confirms stock 3 → 2 |
| README setup, roster, architecture diagram, API summary | [root README](../README.md) | Open the README and Swagger at `http://localhost:8000/docs` |
| Git history and checks | [commits](https://github.com/MawinSkalet/DeliveryApp/commits/main), [GitHub Actions](https://github.com/MawinSkalet/DeliveryApp/actions) | Show contributions and successful backend/frontend/integration jobs |

`POST /api/v1/orders` reads the MongoDB product name and price, validates that the product belongs to the restaurant, then locks PostgreSQL inventory and commits the order, items, status history, and stock decrement in one PostgreSQL transaction. This uses both databases for the order flow while keeping transactional state in PostgreSQL, as the CP1 objectives specify. It is not a distributed atomic commit across the two database engines.

## Prepare the demo machine

Clone the repository, copy `.env.example` to `.env`, replace the local placeholder credentials and `AUTH_SECRET`, and set `SEED_USER_PASSWORD` to a local demo password of at least eight characters. Never commit `.env`. Then run:

```bash
docker compose up -d --build --wait
docker compose exec -T api python -m scripts.seed
docker compose exec -T api python -m scripts.verify_seed
docker compose exec -T api python -m scripts.smoke_cp1
```

The smoke script prints the HTTP result for each required route and removes its temporary customer, restaurant, product, and order afterward. Run `docker compose exec -T api python -m scripts.smoke_orders` if the instructor asks about duplicate requests, stock conflicts, cancellation, or concurrent orders. Swagger is available at `http://localhost:8000/docs`.

## Ten-minute audit sequence

| Time | Presenter | Demonstration |
| --- | --- | --- |
| 0:00–1:00 | Anakin | State the app scope, team roles, and PostgreSQL/MongoDB split using the README diagram |
| 1:00–2:30 | Jirasak | Show `docker compose ps`, root Compose volumes, and the Alembic migration history |
| 2:30–4:00 | Supanat | Run `scripts.verify_seed`; explain Users, constraints, stable seed IDs, and record counts |
| 4:00–7:30 | Jirasak | Open Swagger and run `scripts.smoke_cp1`; point out all five route results and dynamic product attributes |
| 7:30–9:00 | Jirasak | Explain the MongoDB catalog read, PostgreSQL row lock/transaction, and stock change during order creation |
| 9:00–10:00 | All | Show passing GitHub Actions and answer questions on individual commits |

The rubric also assesses balanced Git contributions. The current history has work from all three members but is not evenly distributed because the final CP1 integration was completed under Jirasak's identity. Present the history honestly; do not fabricate or reassign commits.
