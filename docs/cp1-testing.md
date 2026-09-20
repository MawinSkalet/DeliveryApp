# Checkpoint 1 testing guide

Run these commands in PowerShell from the extracted `DeliveryApp` folder or the repository root. The checks use local Docker containers and temporary test records; the smoke scripts remove their own records. Keep Docker Desktop running. On a fresh copy, run `Copy-Item .env.example .env`, then replace the placeholder passwords and `AUTH_SECRET` in `.env` with local values. Do not commit or upload `.env`.

## Start and check the databases

```powershell
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps
docker compose exec -T api alembic current
```

`docker compose config --quiet` should exit without an error. `postgres`, `mongo`, and `api` should show healthy in `docker compose ps`. The migration revision should be `0002_user_accounts (head)`. On this team's machine the database host ports may differ from 5432 and 27017 because `.env` overrides them; inside Compose, the database ports are still 5432 and 27017.

## Seed data and verify both database models

```powershell
docker compose exec -T api python -m scripts.seed
docker compose exec -T api python -m scripts.verify_seed
```

Expect 10 restaurants, 101 users, and 1,000 inventory rows in PostgreSQL. Expect the `products` and `rider_locations` MongoDB collections with 1,000 products and 20 rider locations. The verifier also checks indexes, required fields, product-to-inventory links, nonnegative stock, and no orphaned inventory.

## Test the API and order behavior

```powershell
docker compose exec -T api python -m unittest discover -s tests -p "test_*.py"
docker compose exec -T api python -m scripts.smoke_cp1
docker compose exec -T api python -m scripts.smoke_orders
docker compose exec -T api python -m scripts.verify_seed
```

The unit suite should finish with `OK`. `smoke_cp1` should print successful responses for the five required routes: `POST /api/v1/users` (201), `GET /api/v1/users/{id}` (200), `GET /api/v1/products` (200), `POST /api/v1/products` (201), and `POST /api/v1/orders` (201). It also checks dynamic product attributes, an order's MongoDB price lookup, PostgreSQL stock changing from 3 to 2, and stock returning to 3 on cancellation. `smoke_orders` checks invalid requests (400), missing orders (404), authentication, idempotent retries, stock conflicts, concurrent orders, and cancellation. The final seed verification should still pass after those tests.

You can inspect the API and frontend in a browser:

- `http://localhost:8000/health` should return `{"status":"ok"}`.
- `http://localhost:8000/docs` should list the five required routes and their request schemas.
- `http://localhost:5173` should load the current frontend setup page. The customer ordering UI and live rider map are later milestones.

Check that the frontend compiles:

```powershell
docker compose exec -T frontend npm run build
```

## Check the submission ZIP and GitHub

```powershell
python tools/package_cp1.py
python -c "from zipfile import ZipFile; z=ZipFile('dist/DeliveryApp_CP1_submission.zip'); assert z.testzip() is None; n=z.namelist(); assert 'DeliveryApp/README.md' in n and 'DeliveryApp/docker-compose.yml' in n; assert not any('/.git/' in x or ('/.env' in x and not x.endswith('/.env.example')) for x in n); print('ZIP OK:', len(n), 'files')"
git status --short --branch
```

The ZIP check should print `ZIP OK` and the Git working tree should have no uncommitted source changes. The package file is intentionally ignored by Git. Verify the latest `main` workflow at https://github.com/MawinSkalet/DeliveryApp/actions: the backend, frontend, and orders-integration jobs should pass. Git history is available at https://github.com/MawinSkalet/DeliveryApp/commits/main.

When finished, `docker compose down` stops the containers but preserves the seeded database volumes. Do not use `docker compose down -v` unless you intentionally want to erase the local database data.
