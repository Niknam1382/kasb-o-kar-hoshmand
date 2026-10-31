"""W5: text receipts + per-shop product photo file_id cache

Revision ID: d9e3a6b8c2f5
Revises: c8d2f5a7e1b4
Create Date: 2026-10-30 10:00:00.000000

افزودنی و nullable (بدونِ دست‌زدن به داده‌یِ موجود).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d9e3a6b8c2f5"
down_revision: Union[str, Sequence[str], None] = "c8d2f5a7e1b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("order_payments", sa.Column("receipt_text", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("photo_shop_file_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "photo_shop_file_id")
    op.drop_column("order_payments", "receipt_text")
