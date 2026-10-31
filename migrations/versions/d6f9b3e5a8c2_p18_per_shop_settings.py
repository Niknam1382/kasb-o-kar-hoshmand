"""P18 · A5: per-shop overrides for settings that used to be global

Revision ID: d6f9b3e5a8c2
Revises: c5e8a2d4f7b1
Create Date: 2026-10-31 17:00:00.000000

افزودنی و بدونِ حذف: پنج ستونِ nullable رویِ `shop_bots`. NULL یعنی «همان پیش‌فرضِ سراسریِ
`admin_settings`» ⇒ هیچ ردیفی مهاجرت داده‌ای نمی‌خواهد و رفتارِ فروشگاه‌هایی که چیزی را تنظیم
نکرده‌اند دقیقاً مثلِ قبل می‌ماند. ستون‌هایِ سراسری پاک نمی‌شوند (پیش‌فرض‌اند) و بازه‌هایِ
`payment_deadline_*`/`review_hold_*` هم سرِ جایشان می‌مانند؛ فقط UIِ ادمین از آن‌ها برداشته شد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6f9b3e5a8c2"
down_revision: Union[str, Sequence[str], None] = "c5e8a2d4f7b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS: tuple[str, ...] = (
    "payment_reservation_minutes",
    "order_reservation_minutes",
    "order_confirmation_timeout_minutes",
    "conversation_retention_days",
    "knowledge_items_limit",
)


def upgrade() -> None:
    for name in _COLUMNS:
        op.add_column("shop_bots", sa.Column(name, sa.Integer(), nullable=True))


def downgrade() -> None:
    for name in reversed(_COLUMNS):
        op.drop_column("shop_bots", name)
