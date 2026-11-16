"""پ۹۷ · بایگانیِ نرمِ محصولات: ستونِ افزودنی `products.retired_at`

Revision ID: b7d1e4a9c260
Revises: f8c3a1d6b240
Create Date: 2026-11-16 18:20:00.000000

مالکِ محصول خواست محصولاتِ دیجیتال حذف شوند (موردِ ۲۵). پ۷۸ درِ ساختنِ تازه را بست و پ۹۴ ابزارِ
حذفِ داده را با قفل ساخت. تصمیمِ فنیِ این فاز **بایگانیِ نرم** است: یکِ ستونِ nullable که اگر زمان
گرفت، محصول از فهرستِ پنل، کاتالوگِ مشتری و پرامپتِ AI بیرون می‌رود، ولی هیچ ردیف، هیچ کدِ دیجیتال و
هیچ سفارشی پاک نمی‌شود و تحویلِ سفارش‌هایِ قبلی همچنان کار می‌کند. `downgrade` فقط همین ستون را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d1e4a9c260"
down_revision: Union[str, Sequence[str], None] = "f8c3a1d6b240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "retired_at")
