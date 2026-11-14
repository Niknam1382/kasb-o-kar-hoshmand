"""پ۷۳ · گزارشِ کامنت‌هایِ اینستاگرام: جدولِ تازهٔ `instagram_comment_events`

Revision ID: a3d7c8e2b510
Revises: f2c5b9a1d340
Create Date: 2026-11-14 20:40:00.000000

چرا جدولِ تازه و نه ستون رویِ چیزی که هست: کامنت نه مشتری است، نه گفتگو، نه تراکنش — تا پیش ازِ این
هیچ‌جا ذخیره نمی‌شد (پ۶۳ صریح نوشت «کامنت‌ها شمارش نمی‌شوند»). ردیفِ افزودنیِ کامل است: هیچ دادهٔ
موجودی لمس نمی‌شود، هیچ ستونی حذف نمی‌شود و `downgrade` فقط همین جدول را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3d7c8e2b510"
down_revision: Union[str, Sequence[str], None] = "f2c5b9a1d340"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instagram_comment_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), nullable=False),
        sa.Column("comment_id", sa.String(length=64), nullable=False),
        sa.Column("media_id", sa.String(length=64), nullable=True),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("comment_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome", sa.String(length=32), server_default="received", nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("ai_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_toman", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["shop_bot_id"], ["shop_bots.id"], name="fk_instagram_comment_events_shop_bot_id_shop_bots"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instagram_comment_events"),
        sa.UniqueConstraint("shop_bot_id", "comment_id", name="uq_ig_comment_shop_comment"),
    )
    op.create_index(
        "ix_ig_comment_events_shop_created", "instagram_comment_events", ["shop_bot_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ig_comment_events_shop_created", table_name="instagram_comment_events")
    op.drop_table("instagram_comment_events")
