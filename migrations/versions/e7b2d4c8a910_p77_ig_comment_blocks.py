"""پ۷۷ · «به این حساب جواب نده»: جدولِ تازهٔ `instagram_comment_blocks`

Revision ID: e7b2d4c8a910
Revises: d6a9c3e5b170
Create Date: 2026-11-15 11:20:00.000000

فهرستِ per-فروشگاهِ نام‌هایِ کاربریِ کامنت‌کننده که ربات نباید به آن‌ها جواب دهد (حلقهٔ چهارمِ
اینستاگرام). جدولِ کاملاً افزودنی است: هیچ ستون/جدولی حذف نمی‌شود و `downgrade` فقط همین را
برمی‌گرداند. نامِ کاربری به‌صورتِ نرمال‌شدهٔ کوچک ذخیره می‌شود و یکتاییِ (فروشگاه، نام)
جلویِ درجِ دوباره را می‌گیرد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7b2d4c8a910"
down_revision: Union[str, Sequence[str], None] = "d6a9c3e5b170"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instagram_comment_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shop_bot_id"], ["shop_bots.id"], name="fk_instagram_comment_blocks_shop_bot_id_shop_bots"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instagram_comment_blocks"),
        sa.UniqueConstraint("shop_bot_id", "username", name="uq_ig_block_shop_username"),
    )
    op.create_index("ix_ig_comment_blocks_shop_created", "instagram_comment_blocks", ["shop_bot_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ig_comment_blocks_shop_created", table_name="instagram_comment_blocks")
    op.drop_table("instagram_comment_blocks")
