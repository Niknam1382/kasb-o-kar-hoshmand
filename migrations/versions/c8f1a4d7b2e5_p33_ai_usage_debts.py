"""P33-C: دفترِ بدهیِ مصرفِ هوش مصنوعی

Revision ID: c8f1a4d7b2e5
Revises: b7d4e2a9c3f6
Create Date: 2026-11-04 13:20:00.000000

سوییچِ «ادامهٔ سفارش با اعتبارِ صفر» (P30-C) هزینهٔ واقعیِ AI را بی‌ثبت می‌گذاشت
(`wallet_service.deduct` فقط logger.warning). این جدول افزودنیِ همان هزینه است تا سقفِ
بدهی، کلِ درَکِ فروشگاه را ببیند. هیچ ستون/جدولی حذف نمی‌شود و همه چیز server_default دارد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8f1a4d7b2e5"
down_revision: Union[str, Sequence[str], None] = "b7d4e2a9c3f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_usage_debts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_owner_id", sa.Integer(), nullable=False),
        sa.Column("amount_toman", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False, server_default="open"),
        sa.Column("note", sa.String(length=180), nullable=True),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_owner_id"], ["shop_owners.id"], name=op.f("fk_ai_usage_debts_shop_owner_id")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_debts")),
        sa.UniqueConstraint("idempotency_key", name="uq_ai_usage_debt_key"),
    )
    op.create_index(op.f("ix_ai_usage_debts_shop_owner_id"), "ai_usage_debts", ["shop_owner_id"], unique=False)
    op.create_index(op.f("ix_ai_usage_debts_status"), "ai_usage_debts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_usage_debts_status"), table_name="ai_usage_debts")
    op.drop_index(op.f("ix_ai_usage_debts_shop_owner_id"), table_name="ai_usage_debts")
    op.drop_table("ai_usage_debts")
