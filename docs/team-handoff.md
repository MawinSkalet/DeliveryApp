# Checkpoint 1 team handoff

The CP1 backend, schema, seed, verification, and five required routes are implemented. This file records the three-person split using the supplied student IDs and Git identities.

| Student / Git identity | Implemented work | What to explain during the audit |
| --- | --- | --- |
| 670615020 Jirasak Boonsom / Jirasak | Setup, Orders, Products, integration, CI | Architecture, stock transaction, cross-database limits, clean setup |
| 670615035 Supanat Pudhom / beam2548 | Users, account migration, PostgreSQL seed/tests | Password hashing, token claims, case-insensitive email, relational seed |
| 650615037 Anakin arsa / Anakin_Arsa | Planning and handoff documentation | Scope, responsibilities, remaining milestones, documentation choices |

The original [Users/PostgreSQL brief](handoff-users-postgres.md) and [Products/MongoDB brief](handoff-products-mongo.md) remain as historical task specifications. The [seed contract](seed-contract.md) defines matching IDs across databases.

After cloning and setting local values in `.env`, run:

```bash
docker compose up -d --build --wait
docker compose exec -T api python -m scripts.seed
docker compose exec -T api python -m scripts.verify_seed
docker compose exec -T api python -m scripts.smoke_cp1
```

`docker compose up` applies the Alembic migrations automatically. The API is documented at `http://localhost:8000/docs`; the frontend setup page is at `http://localhost:5173`. These commands are checked in CI against fresh database volumes. Each member should continue to use a feature branch and a reviewed pull request, with meaningful incremental commits.
