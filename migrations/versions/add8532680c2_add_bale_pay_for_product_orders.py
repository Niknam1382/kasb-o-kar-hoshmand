"""add bale pay for product orders

Revision ID: add8532680c2
Revises: 8ad0d7dc69f8
Create Date: 2026-09-27 00:00:00.000000

فازِ ۳ — بله‌پی برایِ سفارشِ محصول:
- shop_bots.bale_provider_token: کدِ درگاهِ بله‌پیِ خودِ هر فروشگاه (نه
  پلتفرم)، مشابهِ zarinpal_merchant_idِ ازقبل‌موجود ولی هیچ‌وقت استفاده‌نشده
  روی همین جدول.
- orders_consultations.bale_invoice_payload / bale_transaction_id / bale_paid_at:
  ردگیریِ پرداختِ آنلاینِ هر سفارش، مستقل از status (که همچنان از همون مسیرِ
  همیشگیِ فروشگاه‌دار پیش می‌ره).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "add8532680c2"
down_revision: Union[str, Sequence[str], None] = "8ad0d7dc69f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("bale_provider_token", sa.String(length=128), nullable=True))

    op.add_column("orders_consultations", sa.Column("bale_invoice_payload", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_orders_consultations_bale_invoice_payload"), "orders_consultations", ["bale_invoice_payload"], unique=False)
    op.add_column("orders_consultations", sa.Column("bale_transaction_id", sa.String(length=128), nullable=True))
    op.add_column("orders_consultations", sa.Column("bale_paid_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("orders_consultations", "bale_paid_at")
    op.drop_column("orders_consultations", "bale_transaction_id")
    op.drop_index(op.f("ix_orders_consultations_bale_invoice_payload"), table_name="orders_consultations")
    op.drop_column("orders_consultations", "bale_invoice_payload")

    op.drop_column("shop_bots", "bale_provider_token")
