"""shop_payment_settings, order_payments (P1-S5b/c / W3-W4)

Revision ID: d4a9c6e2b8f1
Revises: c2d7a4f1e8b3
Create Date: 2026-10-27 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4a9c6e2b8f1"
down_revision: Union[str, Sequence[str], None] = "c2d7a4f1e8b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "shop_payment_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("card_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("card_number_enc", sa.Text(), nullable=True),
        sa.Column("card_holder_name", sa.String(length=80), nullable=True),
        sa.Column("bank_name", sa.String(length=64), nullable=True),
        sa.Column("card_deadline_minutes", sa.Integer(), server_default="60", nullable=False),
        sa.Column("receipt_review_hold_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("bale_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("bale_deadline_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("zarinpal_enabled", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("zarinpal_merchant_id_enc", sa.Text(), nullable=True),
        sa.Column("zarinpal_deadline_minutes", sa.Integer(), server_default="15", nullable=False),
        sa.Column("manual_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("auto_accept_online", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("receipt_ai_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("max_receipt_attempts", sa.Integer(), server_default="5", nullable=False),
        _created_at(),
        sa.UniqueConstraint("shop_bot_id", name="uq_shop_payment_settings_shop_bot_id"),
    )

    op.create_table(
        "order_payments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="initiated", nullable=False),
        sa.Column("amount_toman", sa.Integer(), nullable=False),
        sa.Column("receipt_sha256", sa.String(length=64), nullable=True),
        sa.Column("tracking_ref", sa.String(length=64), nullable=True),
        sa.Column("ai_json", sa.Text(), nullable=True),
        sa.Column("ai_verdict", sa.String(length=16), nullable=True),
        sa.Column("flags", sa.String(length=200), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(length=32), nullable=True),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("attempt_no", sa.Integer(), server_default="1", nullable=False),
        sa.Column("provider_ref", sa.String(length=160), nullable=True),
        sa.Column("transaction_ref", sa.String(length=80), nullable=True),
        sa.Column("needs_review", sa.Boolean(), server_default="false", nullable=False),
        _created_at(),
        sa.UniqueConstraint("transaction_ref", name="uq_order_payments_transaction_ref"),
    )
    for col in ("group_id", "shop_bot_id", "receipt_sha256", "tracking_ref", "provider_ref"):
        op.create_index(f"ix_order_payments_{col}", "order_payments", [col])


def downgrade() -> None:
    op.drop_table("order_payments")
    op.drop_table("shop_payment_settings")
