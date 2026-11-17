"""پ۱۰۹ · پنلِ نوشتنیِ وب: جدولِ تازهٔ `web_panel_sessions` (لینکِ یکبارمصرف + نشستِ امضاشده)

Revision ID: a3f7c2b5d810
Revises: b7d1e4a9c260
Create Date: 2026-11-17 18:20:00.000000

ضرورت: «پنجرهٔ نوشتنیِ وب» خواستهٔ بازِ پ۵۰ بود. رمزِ کاربری عمداً ساخته نشد، چون هویتِ این محصول
تلگرام است؛ در عوض رباتِ مرکزی لینکِ یکبارمصرفی می‌دهد که فقط هشِ آن اینجا می‌ماند (الگویِ رازِ
خودکارِ وبهوک در پ۲۰). کاملاً افزودنی است: هیچ جدول/ستونی حذف یا تغییر نمی‌کند و همهٔ ستون‌هایِ
غیرِ nullable مقدارِ پیش‌فرضِ سرور دارند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7c2b5d810"
down_revision: Union[str, Sequence[str], None] = "b7d1e4a9c260"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "web_panel_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.String(length=120), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("actions_count", sa.Integer(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_web_panel_sessions"),
        sa.UniqueConstraint("token_hash", name="uq_web_panel_sessions_token_hash"),
    )
    op.create_index("ix_web_panel_sessions_owner_telegram_id", "web_panel_sessions", ["owner_telegram_id"])


def downgrade() -> None:
    op.drop_index("ix_web_panel_sessions_owner_telegram_id", table_name="web_panel_sessions")
    op.drop_table("web_panel_sessions")
