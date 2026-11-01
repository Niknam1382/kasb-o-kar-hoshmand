"""P21 growth: low-stock alerts and scheduled broadcasts

Revision ID: b8e3f6a1d4c7
Revises: fa7d2b9c4e1a
Create Date: 2026-11-01 18:30:00.000000

افزودنیِ خالص (هیچ ستون/جدولی حذف یا تغییر نمی‌کند):

- `shop_bots.low_stock_alert_threshold` (NULL ⇒ خاموش) و `low_stock_notified_at` (سقفِ ۲۴ساعتهٔ
  اخطار): امروز فروشگاه‌دار فقط وقتی متوجهٔ اتمامِ موجودی می‌شود که مشتری سفارش بدهد و او رد کند.
- جدولِ `scheduled_broadcasts`: پخشِ پیامِ مشتری‌ها امروز فقط «همین الان» وجود دارد و اگر
  فروشگاه‌دار بخواند پیام را ساعتِ ۹ شب بفرستد، باید بیدار بماند. پیامِ زمان‌بندی‌شده اینجا
  می‌نشیند و جابِ دوره‌ای آن را **قطره‌قطره داخلِ صندوقِ اعلان‌ها** (P20) می‌ریزد ⇒ اگر تلگرام
  لحظه‌ای ۵۰۳ داد، هیچ گیرنده‌ای برایِ همیشه بی‌خبر نمی‌ماند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8e3f6a1d4c7"
down_revision: Union[str, Sequence[str], None] = "a7d2e5f9c3b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("low_stock_alert_threshold", sa.Integer(), nullable=True))
    op.add_column("shop_bots", sa.Column("low_stock_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "scheduled_broadcasts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        # NULL ⇒ همه‌یِ مشتری‌هایِ فروشگاه؛ وگرنه فهرستِ شناسه‌هایِ ردیفِ مشتری (گیرنده‌هایِ یک بخشِ CRM)
        sa.Column("recipient_ids", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("queued_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("note", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_bot_id"], ["shop_bots.id"], name=op.f("fk_scheduled_broadcasts_shop_bot_id_shop_bots")),
        sa.ForeignKeyConstraint(["owner_id"], ["shop_owners.id"], name=op.f("fk_scheduled_broadcasts_owner_id_shop_owners")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_broadcasts")),
    )
    op.create_index(op.f("ix_scheduled_broadcasts_shop_bot_id"), "scheduled_broadcasts", ["shop_bot_id"], unique=False)
    op.create_index(op.f("ix_scheduled_broadcasts_status"), "scheduled_broadcasts", ["status"], unique=False)
    op.create_index(op.f("ix_scheduled_broadcasts_scheduled_at"), "scheduled_broadcasts", ["scheduled_at"], unique=False)


def downgrade() -> None:
    op.drop_table("scheduled_broadcasts")
    op.drop_column("shop_bots", "low_stock_notified_at")
    op.drop_column("shop_bots", "low_stock_alert_threshold")
