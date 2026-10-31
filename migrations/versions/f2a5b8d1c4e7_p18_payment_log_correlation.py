"""P18 · د(ز): correlation id on payment_event_logs

Revision ID: f2a5b8d1c4e7
Revises: e1f4a7c9b2d6
Create Date: 2026-10-31 13:00:00.000000

افزودنی و بدونِ حذف: `shop_bot_id` (ایندکس‌شده) و `group_ref` رویِ `payment_event_logs` تا هر ردیفِ لاگِ پرداخت
به فروشگاه و گروه/سفارشِ مربوطه قابلِ ردیابی باشد. ردیف‌هایِ قدیمی NULL می‌مانند (از دست نمی‌روند).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a5b8d1c4e7"
down_revision: Union[str, Sequence[str], None] = "e1f4a7c9b2d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("payment_event_logs", sa.Column("shop_bot_id", sa.Integer(), nullable=True))
    op.add_column("payment_event_logs", sa.Column("group_ref", sa.String(length=64), nullable=True))
    op.create_index("ix_payment_event_logs_shop_bot_id", "payment_event_logs", ["shop_bot_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_event_logs_shop_bot_id", table_name="payment_event_logs")
    op.drop_column("payment_event_logs", "group_ref")
    op.drop_column("payment_event_logs", "shop_bot_id")
