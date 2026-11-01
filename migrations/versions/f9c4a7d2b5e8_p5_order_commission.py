"""PHASE 5D: percentage commission on successful shop orders

Revision ID: f9c4a7d2b5e8
Revises: e8b3d6f1a4c9
Create Date: 2026-11-01 21:00:00.000000

همه‌یِ تغییرات افزودنی‌اند و هیچ ستون/ردیفی حذف نمی‌شود:
* `admin_settings.commission_enabled` (پیش‌فرض false ⇒ هیچ پولی today جابه‌جا نمی‌شود)
  و `admin_settings.commission_percent` NUMERIC(5,2) (پیش‌فرض ۰؛ ۰٫۵٪ ممکن است).
* `shop_owners.commission_reserved_toman` —holdِ کمیسیونِ سفارش‌هایِ در‌جریانِ پرداخت.
  این عدد موجودی را کم **نمی‌کند**، فقط «اعتبارِ قابل‌مصرف» را برایِ شروعِ جریانِ پرداخت
  جدید می‌سنجد؛ ردیفِ دفترِ آن amount=0 است تا همسنجیِ PHASE 5E نخورد.
* `orders_consultations.commission_percent/commission_toman/commission_status` —
  snapshotِ نرخ و نتیجه به‌ازایِ هر گروه؛ تغییرِ بعدیِ ادمین سفارشِ باز را عوض نمی‌کند.

pre-existing rows همه با server_default مقدارِ خنثی می‌گیرند ⇒ رفتارِ امروز دست‌نخورده.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f9c4a7d2b5e8"
down_revision: Union[str, Sequence[str], None] = "e8b3d6f1a4c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("commission_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("admin_settings", sa.Column("commission_percent", sa.Numeric(precision=5, scale=2), nullable=False, server_default="0"))
    op.add_column("shop_owners", sa.Column("commission_reserved_toman", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("orders_consultations", sa.Column("commission_percent", sa.Numeric(precision=5, scale=2), nullable=True))
    op.add_column("orders_consultations", sa.Column("commission_toman", sa.Integer(), nullable=True))
    op.add_column("orders_consultations", sa.Column("commission_status", sa.String(length=16), nullable=True))


def downgrade() -> None:
    for table, name in (
        ("orders_consultations", "commission_status"),
        ("orders_consultations", "commission_toman"),
        ("orders_consultations", "commission_percent"),
        ("shop_owners", "commission_reserved_toman"),
        ("admin_settings", "commission_percent"),
        ("admin_settings", "commission_enabled"),
    ):
        op.drop_column(table, name)
