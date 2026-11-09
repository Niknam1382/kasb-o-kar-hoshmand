"""P45 · ظرفیت: جدولِ `update_dedupe` برایِ دریافتِ webhookِ چندپروسه‌ای

تلگرام همان `update_id` را وقتی پاسخِ HTTP دیر برسد دوباره می‌فرستد. با یکِ پروسه، لیستِ
درِحافظهٔ «آپدیت‌هایِ دیده‌شده» کافی بود؛ با چند پروسهٔ webhook آن لیست در هر پروسه جدا است و
دوباره‌دریافت می‌تواند از پروسهٔ دوم هم رد شود ⇒ یکِ پیامِ مشتری دو بار به هوشِ مصنوعی و **دو بار
کسرِ کیف‌پول**. کلیدِ ترکیبیِ `(bot_id, update_id)` با `INSERT … ON CONFLICT DO NOTHING` همین
تشخیص را بینِ پروسه‌ها اتمیک می‌کند.

فقط افزودنِ جدول است؛ هیچ ستون/جدولی حذف نمی‌شود و هیچ دادهٔ موجودی دست نمی‌خورد. مسیرِ polling
(حالتِ پیش‌فرضِ امروز) اصلاً به این جدول کاری ندارد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d3a91e5b48"
down_revision: Union[str, Sequence[str], None] = "b5e2d9f7c1a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "update_dedupe",
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("update_id", sa.BigInteger(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("bot_id", "update_id", name="pk_update_dedupe"),
    )
    op.create_index("ix_update_dedupe_seen_at", "update_dedupe", ["seen_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_update_dedupe_seen_at", table_name="update_dedupe")
    op.drop_table("update_dedupe")
