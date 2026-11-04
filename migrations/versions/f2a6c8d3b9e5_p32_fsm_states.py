"""P32: جدولِ `fsm_states` برایِ نگه‌داشتنِ حالتِ مکالمه رویِ دیتابیس

Revision ID: f2a6c8d3b9e5
Revises: e1b7c9d4a6f2
Create Date: 2026-11-04 04:20:00.000000

چرا: FSM در `MemoryStorage` بود ⇒ هر ری‌استارتِ سرویس (هر دیپلوی، هر OOM، هر ری‌استارتِ
داکر) چک‌اوتِ نیمه‌کارهٔ مشتری را وسطِ آدرس/تلفن می‌انداخت. این جدول افزودنی است و هیچ
داده‌ای از هیچ جدولي حذف نمی‌شود (قاعدهٔ §۲-۴).

Redis گزینهٔ معمولِ این کار است، ولی در این محیط `files.pythonhosted.org` resolve نمی‌شود
(پکیج نصب نمی‌شود) و افزودنِ یکِ سرویسِ تازه به معماری هم خلافِ §۲-۱۱ بود؛ PostgreSQL که
هست همین کار را می‌کند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2a6c8d3b9e5"
down_revision: Union[str, Sequence[str], None] = "e1b7c9d4a6f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fsm_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=True),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_fsm_states")),
        sa.UniqueConstraint("bot_id", "chat_id", "user_id", name="uq_fsm_state_scope"),
    )
    op.create_index(op.f("ix_fsm_states_updated_at"), "fsm_states", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fsm_states_updated_at"), table_name="fsm_states")
    op.drop_table("fsm_states")
