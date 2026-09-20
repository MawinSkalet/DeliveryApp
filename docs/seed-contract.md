# Shared CP1 seed contract

The checked-in `scripts.seed` runs both database seeds, and `scripts.verify_seed` checks their counts and links. Use Python `uuid.uuid5` with `uuid.NAMESPACE_URL` and these exact names so IDs match:

```python
from uuid import NAMESPACE_URL, uuid5

def restaurant_id(index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"deliveryapp:restaurant:{index}"))

def product_id(index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"deliveryapp:product:{index}"))

def user_id(index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"deliveryapp:user:{index}"))
```

| Data | Owner | IDs / relation | Minimum count |
| --- | --- | --- | --- |
| `restaurants` in PostgreSQL | Users owner | `restaurant_id(0..9)` | 10 |
| `users` in PostgreSQL | Users owner | `user_id(0..100)`; 0–79 customers, 80–99 riders, 100 demo merchant | 101 |
| `inventory` in PostgreSQL | Users owner | `product_id(0..999)`, restaurant `restaurant_id(index // 100)`, positive quantity | 1,000 |
| `products` in MongoDB | Catalog owner | `_id = product_id(0..999)`, restaurant `restaurant_id(index // 100)`, nonempty name, integer `price_satang`, `active: true` | 1,000 |
| `rider_locations` in MongoDB | Catalog owner | `rider_id = user_id(80..99)`, UTC `updated_at`, valid CMU-area coordinates | 20 |

The scripts use insert-if-missing operations on reruns. They do not reset stock after orders have been placed, replace password hashes, or overwrite menu changes. The verifier checks per-database counts and one-to-one seeded product/inventory IDs. The disposable records in `scripts.smoke_cp1` and `scripts.smoke_orders` are integration tests, not CP1 seed data.
