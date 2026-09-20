# Project backlog

Use `Todo → Doing → Review → Done`. Keep one main item in Doing per person. Owners match the team roster in the root README.

| ID | Work | Owner | Status / acceptance |
| --- | --- | --- | --- |
| SETUP-01 | Compose, environment template, health checks | Jirasak | Done; API starts after both databases and applies migrations |
| DB-01 | PostgreSQL schema and constraints | Jirasak + beam2548 | Done; seven transactional tables and account migration |
| API-01 | Users registration, login, and profile | Supanat Pudhom | Done; case-insensitive email and bearer tokens tested |
| API-03 | Orders, stock transaction, idempotency | Jirasak | Done; smoke test covers retries, race, and cancellation |
| DB-02 | MongoDB catalog and rider-location collections/indexes | Jirasak | Done; seed and verifier check both collections |
| API-02 | Product create/list with dynamic attributes | Jirasak | Done; pagination and inventory integration tested |
| DATA-01 | Reproducible seed and cross-database verification | Supanat Pudhom + Jirasak | Done; 1,000+ rows/documents in each database |
| CI-01 | Clean Compose integration checks | Jirasak | Done; seed, verification, unit tests, and smoke tests |
| DOC-01 | README, API contract, model, audit instructions | Jirasak + Anakin arsa | Done |
| TRACK-01 | Rider location write/read API and map | Unassigned | Later milestone; CP1 only needs the location collection and seed |
| CP2-01 | Expand/dual-write/backfill/switch/contract migration demo | Unassigned | Checkpoint 2 |
| CP3-01 | Concurrency and performance audit | Unassigned | Checkpoint 3 |

Before the CP1 instructor audit, each member should be able to explain their own commits, the PostgreSQL/MongoDB responsibility split, how seed IDs join across databases, and the limits of cross-database writes.
