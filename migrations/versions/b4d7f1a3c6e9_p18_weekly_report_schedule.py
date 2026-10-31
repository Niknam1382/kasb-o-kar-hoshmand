"""P18 · B5: per-shop weekly report schedule in Tehran time

Revision ID: b4d7f1a3c6e9
Revises: a3c6e9f2b5d8
Create Date: 2026-10-31 15:00:00.000000

افزودنی و بدونِ حذف: گزارشِ دوره‌ای پیش از این «N روز از آخرین ارسال» بود و سرِ ساعتِ تصادفیِ همان لحظه
تکرار می‌شد (و مبنایش UTC). حالا هر فروشگاه روزِ هفته و ساعتِ دلخواهِ خودش را دارد و زمان‌بندی با
منطقه‌یِ زمانیِ تهران و بازه‌یِ هفتگی انجام می‌شود. `last_report_sent_at` دست‌نخورده می‌ماند و به‌عنوانِ
علامتِ «در این بازه فرستاده شد» استفاده می‌شود؛ پیش‌فرض‌ها رفتارِ «گزارش روشن» را حفظ می‌کنند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4d7f1a3c6e9"
down_revision: Union[str, Sequence[str], None] = "a3c6e9f2b5d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS: tuple[tuple[str, sa.types.TypeEngine, str], ...] = (
    ("weekly_report_enabled", sa.Boolean(), "true"),
    ("weekly_report_weekday", sa.Integer(), "0"),
    ("weekly_report_hour", sa.Integer(), "9"),
)


def upgrade() -> None:
    for name, type_, default in _COLUMNS:
        op.add_column("shop_bots", sa.Column(name, type_, nullable=False, server_default=default))


def downgrade() -> None:
    for name, _type, _default in reversed(_COLUMNS):
        op.drop_column("shop_bots", name)
