"""Add an index for the paginated customer order list."""

from alembic import op

revision = "0004_cp3_order_list_index"
down_revision = "0003_expand_user_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """CREATE INDEX IF NOT EXISTS ix_orders_customer_created_id
           ON orders (customer_id, created_at DESC, id DESC)"""
    )
    op.execute("DROP INDEX IF EXISTS ix_orders_customer_created")


def downgrade() -> None:
    op.execute(
        """CREATE INDEX IF NOT EXISTS ix_orders_customer_created
           ON orders (customer_id, created_at DESC)"""
    )
    op.execute("DROP INDEX IF EXISTS ix_orders_customer_created_id")
