"""add customer order confirmation fields

Revision ID: 071cef449d76
Revises: db68ee15015b
Create Date: 2026-09-25 00:00:00.000000

بازطراحیِ سفارش‌گیری:
- دو ستونِ ساختاریافته‌ی جدید روی orders_consultations برای تلفن/آدرسِ مشتری
  (قبلاً این‌ها فقط متنِ آزاد داخلِ summary بودن).
- یه ستونِ جدید روی admin_settings برای مهلتِ تاییدِ سفارش توسطِ مشتری.
- status جدیدِ OrderStatus.AWAITING_CUSTOMER_CONFIRMATION نیازی به مایگریشن
  نداره چون این ستون در سطحِ دیتابیس همیشه یه plain string بوده، نه native
  Postgres enum (طبق یادداشتِ مسترپرامپت).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "071cef449d76"
down_revision: Union[str, Sequence[str], None] = "db68ee15015b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders_consultations", sa.Column("customer_phone", sa.String(length=32), nullable=True))
    op.add_column("orders_consultations", sa.Column("customer_address", sa.Text(), nullable=True))

    op.add_column(
        "admin_settings",
        sa.Column("order_customer_confirmation_timeout_minutes", sa.Integer(), nullable=False, server_default="60"),
    )
    op.alter_column("admin_settings", "order_customer_confirmation_timeout_minutes", server_default=None)


def downgrade() -> None:
    op.drop_column("admin_settings", "order_customer_confirmation_timeout_minutes")
    op.drop_column("orders_consultations", "customer_address")
    op.drop_column("orders_consultations", "customer_phone")
