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

Confirm with the instructor whether the CP1 phrase “Dual-DB transaction” requires writes to both databases. The current order endpoint reads a MongoDB product and commits the order and stock change in PostgreSQL; it does not claim a distributed atomic commit. Also verify the official CP1 deadline: the project overview labels it Week 8, while the dedicated CP1 sheet says submission at the end of Week 11.

For later milestones, decide how merchant ownership maps to restaurants, how assigned riders are authorized, and how to reconcile ambiguous cross-database failures automatically. Chat, payment gateways, complex coupons, and competitive rider assignment are outside the current scope.
