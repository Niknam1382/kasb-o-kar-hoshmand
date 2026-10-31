"""P18 · A2: mandatory shop-bot biography (branding)

Revision ID: a9c3e6b8d1f5
Revises: f8b2d8e1a4c7
Create Date: 2026-11-01 11:00:00.000000

افزودنی و بدونِ حذف:
* `admin_settings.branding_text` (≤۶۰) و `branding_synced_at` — متنِ اجباریِ ادمین + برچسبِ زمانِ آخرین
  همگام‌سازیِ موفقی که جابِ ۶ ساعته با آن تصمیم می‌گیرد.
* `shop_bots.branding_owner_text` (≤۱۲۰)، `branding_tamper_count`، `branding_set_at` — متنِ خودِ
  فروشگاه‌دار که کنارِ متنِ ادمین می‌آید و شمارنده‌یِ تخلفِ دست‌کاری.

پیش‌فرض‌ها یعنی «هیچ برچسبی تنظیم نشده ⇒ هیچ رباتی دست نمی‌خورد» ⇒ رفتارِ امروز حفظ است.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9c3e6b8d1f5"
down_revision: Union[str, Sequence[str], None] = "f8b2d8e1a4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("branding_text", sa.String(length=60), nullable=True))
    op.add_column("admin_settings", sa.Column("branding_synced_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_bots", sa.Column("branding_owner_text", sa.String(length=120), nullable=True))
    op.add_column("shop_bots", sa.Column("branding_tamper_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("shop_bots", sa.Column("branding_set_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for table, name in (
        ("shop_bots", "branding_set_at"),
        ("shop_bots", "branding_tamper_count"),
        ("shop_bots", "branding_owner_text"),
        ("admin_settings", "branding_synced_at"),
        ("admin_settings", "branding_text"),
    ):
        op.drop_column(table, name)
