# Shared technical decisions

| Topic | Current decision |
| --- | --- |
| Scope | One restaurant per order, fixed delivery fee, simulated cash on delivery |
| IDs | UUID strings for IDs shared between PostgreSQL and MongoDB |
| Time | Store UTC timestamps and convert for display |
| Money | Integer satang in the API; PostgreSQL numeric where appropriate; no floating-point currency |
| Order price | Backend calculates and stores the product name and price at purchase time |
| Status | `PLACED → ACCEPTED → PREPARING → OUT_FOR_DELIVERY → DELIVERED` |
| Cancellation | Allowed only while placed; return stock exactly once |
| API | `/api/v1` prefix and shared JSON error shape |
| Authorization | Customers read only their records; product writes require merchant/admin tokens |
| Source of truth | PostgreSQL owns transactions and stock; MongoDB owns catalog and telemetry |
| Cross-database writes | No automatic atomicity; compensate known failures and verify for orphans |
| Seed | Stable UUID5 IDs and insert-if-missing behavior preserve later edits |

The CP1 handout names PostgreSQL and MongoDB as the target databases for `POST /api/v1/orders` and assigns transactional state to PostgreSQL. The endpoint reads the product and price from MongoDB, then commits the order and stock change atomically in PostgreSQL. This is the implemented dual-database order flow; it does not claim a distributed atomic commit across both engines. The dedicated CP1 handout states a submission deadline at the end of Week 11 despite its Week 8 heading; verify the course announcement for the calendar date.

For later milestones, decide how merchant ownership maps to restaurants, how assigned riders are authorized, and how to reconcile ambiguous cross-database failures automatically. Chat, payment gateways, complex coupons, and competitive rider assignment are outside the current scope.
