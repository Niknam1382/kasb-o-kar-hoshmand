"""add nightly report fields

Revision ID: 8ad0d7dc69f8
Revises: 071cef449d76
Create Date: 2026-09-26 00:00:00.000000

فازِ ۳ (شروع) — گزارشِ شبانه:
- دو ستونِ جدید روی admin_settings: فعال/غیرفعال‌بودنِ گزارشِ شبانه (پیش‌فرض
  فعال) و ساعتِ ارسال به‌وقتِ UTC (پیش‌فرض ۱۸ = ۲۱:۳۰ تهران).
- یه ستونِ جدید روی shop_bots: آخرین تاریخی که گزارشِ شبانه براش فرستاده شده
  (فقط تاریخ، نه زمان — برای تشخیصِ «امروز قبلاً فرستاده شده یا نه»).

این کاملاً جدا و اضافه‌ست به last_report_sent_at/periodic_report_frequency_days
ی که از قبل هست (اون یکی خلاصه‌ی سلامتِ کلی هر N روزه، این یکی گزارشِ روزانه‌ی
سرِ ساعتِ مشخصه).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8ad0d7dc69f8"
down_revision: Union[str, Sequence[str], None] = "071cef449d76"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("nightly_report_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.alter_column("admin_settings", "nightly_report_enabled", server_default=None)

    op.add_column("admin_settings", sa.Column("nightly_report_hour_utc", sa.Integer(), nullable=False, server_default="18"))
    op.alter_column("admin_settings", "nightly_report_hour_utc", server_default=None)

    op.add_column("shop_bots", sa.Column("last_nightly_report_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "last_nightly_report_date")
    op.drop_column("admin_settings", "nightly_report_hour_utc")
    op.drop_column("admin_settings", "nightly_report_enabled")
