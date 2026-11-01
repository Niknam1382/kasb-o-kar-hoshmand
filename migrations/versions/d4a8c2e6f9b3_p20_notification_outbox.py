"""P20 suggestions: notification outbox table

Revision ID: d4a8c2e6f9b3
Revises: c3f7a1d5b8e2
Create Date: 2026-11-01 14:05:00.000000

یکِ جدولِ تازه (بدونِ حذف/تغییرِ هیچ ستونِ موجود): `notifications` — صفِ ماندگارِ اعلان‌هایی
که ارسالشان شکست خورد. جابِ هر ۳۰ دقیقه با backoff دوباره تلاش می‌کند و بعد از سقفِ تلاش،
ردیف `failed` می‌شود تا در پنل دیده شود؛ امروز همان پیام در `except TelegramAPIError` گم می‌شد.

همه‌یِ ستون‌ها برایِ ردیف‌هایِ موجود بی‌معنی‌اند (جدول تازه است) ⇒ هیچ داده‌ای دست‌نخورده.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a8c2e6f9b3"
down_revision: Union[str, Sequence[str], None] = "c3f7a1d5b8e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=64), nullable=True),
        sa.Column("platform", sa.String(length=16), server_default="telegram", nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_error", sa.String(length=200), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_bot_id"], ["shop_bots.id"], name=op.f("fk_notifications_shop_bot_id_shop_bots")),
        sa.ForeignKeyConstraint(["owner_id"], ["shop_owners.id"], name=op.f("fk_notifications_owner_id_shop_owners")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
    )
    op.create_index(op.f("ix_notifications_chat_id"), "notifications", ["chat_id"], unique=False)
    op.create_index(op.f("ix_notifications_status"), "notifications", ["status"], unique=False)
    op.create_index(op.f("ix_notifications_shop_bot_id"), "notifications", ["shop_bot_id"], unique=False)
    op.create_index(op.f("ix_notifications_owner_id"), "notifications", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_table("notifications")
