"""پ۵۵ · موردِ ۲۳: نسبت‌دادنِ مصرفِ AI به خودِ مشتری + دو اهرمِ مدیریتیِ هر کاربر

· `wallet_transactions.customer_id`  ← کسرِ هزینهٔ AI به مشتریِ ایجادکننده هم وصل می‌شود
· `ix_wallet_transactions_customer_created` ← رتبه‌بندیِ بازه‌دار بدونِ اسکنِ کاملِ دفتر
· `customers.ai_daily_limit_toman`   ← سقفِ مصرفِ AI در روز برایِ یکِ کاربر (NULL = بدونِ سقف)
· `customers.ai_paused_until`        ← توقفِ موقتِ پاسخِ خودکار برایِ یکِ کاربر (NULL = فعال)

همه nullable و افزودنی‌اند ⇒ هیچ ردیفِ موجودی مقدارِ تازه یا رفتارِ تازه نمی‌گیرد؛ ردیف‌هایِ
قدیمیِ دفترِ کیف‌پول `customer_id = NULL` می‌مانند و رتبه‌بندی عمداً فقط مصرفِ *آینده* را می‌شمارد
(عددِ ساختگی از گذشته ساخته نمی‌شود). هیچ ستون یا جدولی حذف نمی‌شود و `downgrade` فقط همین
افزوده‌ها را به ترتیبِ معکوس برمی‌گرداند.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d3e8a2c451"
down_revision: Union[str, Sequence[str], None] = "f4a8c1d7b206"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_transactions",
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index(
        "ix_wallet_transactions_customer_created",
        "wallet_transactions",
        ["customer_id", "created_at"],
    )
    op.add_column("customers", sa.Column("ai_daily_limit_toman", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("ai_paused_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("customers", "ai_paused_until")
    op.drop_column("customers", "ai_daily_limit_toman")
    op.drop_index("ix_wallet_transactions_customer_created", table_name="wallet_transactions")
    op.drop_column("wallet_transactions", "customer_id")
