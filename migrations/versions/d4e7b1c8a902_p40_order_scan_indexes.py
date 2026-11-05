"""P40-A5: دو ایندکسِ partial برایِ دو اسکنِ پرتکرارِ سفارش‌ها

Revision ID: d4e7b1c8a902
Revises: c8f1a4d7b2e5
Create Date: 2026-11-05 21:40:00.000000

دو خواندنی که همیشه کلِ `orders_consultations` را sequential scan می‌کردند:

۱) جابِ مهلت (`order_payment_service.expire_stale_payment_groups` و
   `order_service.expire_stale_reservations`) با فیلترِ `reservation_expires_at < now` و بدونِ
   `shop_bot_id` — هر ~۶۰ ثانیه، رویِ سریع‌ترین جدولِ در حالِ رشدِ سرویس.
۲) `order_service.bale_transaction_used_elsewhere` که `bale_transaction_id = …` را در *هر*
   وب‌هوکِ پرداختِ بله می‌پرسد (محافظِ تراکنشِ بازپخش‌شده).

ایندکسِ ترکیبیِ موجود (`shop_bot_id, status, created_at`) هیچ‌کدام را پوشش نمی‌داد. افزودنیِ
خالص: هیچ ستون/جدولی حذف نمی‌شود، هر دو ایندکس partial‌اند (فقط ردیف‌هایِ دارایِ مقدار) و
downgrade تمیز دارند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4e7b1c8a902"
down_revision: Union[str, Sequence[str], None] = "c8f1a4d7b2e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_orders_reservation_expires",
        "orders_consultations",
        ["reservation_expires_at"],
        unique=False,
        postgresql_where=sa.text("reservation_expires_at IS NOT NULL"),
    )
    op.create_index(
        "ix_orders_bale_transaction",
        "orders_consultations",
        ["bale_transaction_id"],
        unique=False,
        postgresql_where=sa.text("bale_transaction_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_orders_bale_transaction", table_name="orders_consultations")
    op.drop_index("ix_orders_reservation_expires", table_name="orders_consultations")
