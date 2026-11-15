"""پ۷۴ · دسته‌بندیِ محصولات: ستونِ `products.category`

Revision ID: b4e9a1c7d320
Revises: a3d7c8e2b510
Create Date: 2026-11-15 09:10:00.000000

افزودنی و غیرقابلِ حذفِ داده: ستونِ `String(64)` با `server_default=""` ⇒ همهٔ ردیف‌هایِ موجود
«بی‌دسته» می‌شوند و هیچ رفتارِ قبلی (فهرستِ مشتری، پرامپتِ AI، اکسل، سبد) عوض نمی‌شود. چرا رشته و نه
جدولِ `categories`: دسته‌ها همیشه متعلق به خودِ فروشگاه‌اند، تعدادشان کم است، و با رشته، «دسته»
همان‌جا که محصول ساخته می‌شود نوشته می‌شود بدونِ نیاز به همگام‌سازیِ ردیفِ دوم یا حذفِ دستهٔ یتیم.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4e9a1c7d320"
down_revision: Union[str, Sequence[str], None] = "a3d7c8e2b510"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("products", sa.Column("category", sa.String(length=64), server_default="", nullable=False))
    op.create_index("ix_products_shop_category", "products", ["shop_bot_id", "category"])


def downgrade() -> None:
    op.drop_index("ix_products_shop_category", table_name="products")
    op.drop_column("products", "category")
