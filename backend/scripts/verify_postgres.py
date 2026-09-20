import os
import sys

import psycopg


def verify_postgres() -> bool:
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://", 1)
    errors: list[str] = []

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            # 1. Restaurants count
            cur.execute("SELECT count(*) FROM restaurants")
            rest_count = cur.fetchone()[0]
            print(f"[CHECK] Restaurants count: {rest_count}")
            if rest_count < 10:
                errors.append(f"Expected at least 10 restaurants, found {rest_count}")

            # 2. Users count
            cur.execute("SELECT count(*) FROM users")
            user_count = cur.fetchone()[0]
            print(f"[CHECK] Total users count: {user_count}")
            if user_count < 100:
                errors.append(f"Expected at least 100 users, found {user_count}")

            # 2b. Role counts
            cur.execute("SELECT count(*) FROM users WHERE role = 'customer'")
            customer_count = cur.fetchone()[0]
            print(f"[CHECK] Customer users count: {customer_count}")
            if customer_count < 80:
                errors.append(f"Expected at least 80 customers, found {customer_count}")

            cur.execute("SELECT count(*) FROM users WHERE role = 'rider'")
            rider_count = cur.fetchone()[0]
            print(f"[CHECK] Rider users count: {rider_count}")
            if rider_count < 20:
                errors.append(f"Expected at least 20 riders, found {rider_count}")

            cur.execute("SELECT count(*) FROM users WHERE role = 'merchant'")
            merchant_count = cur.fetchone()[0]
            print(f"[CHECK] Merchant users count: {merchant_count}")
            if merchant_count < 1:
                errors.append("Expected a demo merchant account")

            # 3. Inventory count
            cur.execute("SELECT count(*) FROM inventory")
            inv_count = cur.fetchone()[0]
            print(f"[CHECK] Inventory items count: {inv_count}")
            if inv_count < 1000:
                errors.append(f"Expected at least 1,000 inventory items, found {inv_count}")

            # 4. Orphaned inventory check
            cur.execute(
                """
                SELECT count(*)
                FROM inventory i
                LEFT JOIN restaurants r ON i.restaurant_id = r.id
                WHERE r.id IS NULL
                """
            )
            orphaned = cur.fetchone()[0]
            print(f"[CHECK] Orphaned inventory items: {orphaned}")
            if orphaned > 0:
                errors.append(f"Found {orphaned} inventory items without valid restaurant references")

            # 5. Negative stock check
            cur.execute("SELECT count(*) FROM inventory WHERE quantity < 0")
            negative_stock = cur.fetchone()[0]
            print(f"[CHECK] Negative inventory items: {negative_stock}")
            if negative_stock > 0:
                errors.append(f"Found {negative_stock} inventory items with negative quantity")

            # 6. Check unique index on lower(email)
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'users' AND indexname = 'ix_users_email_lower'
                """
            )
            has_lower_index = cur.fetchone() is not None
            print(f"[CHECK] Index 'ix_users_email_lower' exists: {has_lower_index}")
            if not has_lower_index:
                errors.append("Unique index 'ix_users_email_lower' is missing on users")

    if errors:
        print("\n[FAIL] PostgreSQL verification failed:")
        for err in errors:
            print(f"  - {err}")
        return False

    print("\n[PASS] PostgreSQL dataset and schema verification passed.")
    return True


if __name__ == "__main__":
    success = verify_postgres()
    sys.exit(0 if success else 1)

