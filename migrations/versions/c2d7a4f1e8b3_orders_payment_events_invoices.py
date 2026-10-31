"""orders: payment/shipping columns, order_events, invoices, customer_addresses, cart_ai_proposals, direct_messages, legacy flag (P1-S4 / W2)

Revision ID: c2d7a4f1e8b3
Revises: b9e2f6a4c8d1
Create Date: 2026-10-27 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c2d7a4f1e8b3"
down_revision: Union[str, Sequence[str], None] = "b9e2f6a4c8d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("legacy_ai_order_detection", sa.Boolean(), server_default="false", nullable=False))

    for name, col in (
        ("paid_at", sa.DateTime(timezone=True)),
        ("delivered_at", sa.DateTime(timezone=True)),
        ("tracking_code", sa.String(length=128)),
        ("carrier_name", sa.String(length=64)),
        ("shipping_fee_toman", sa.Integer()),
        ("shipping_method_name", sa.String(length=64)),
        ("cancel_reason", sa.Text()),
        ("payment_method", sa.String(length=32)),
    ):
        op.add_column("orders_consultations", sa.Column(name, col, nullable=True))

    op.create_table(
        "order_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders_consultations.id"), nullable=True),
        sa.Column("group_id", sa.String(length=64), nullable=True),
        sa.Column("from_status", sa.String(length=32), nullable=True),
        sa.Column("to_status", sa.String(length=32), nullable=False),
        sa.Column("actor_type", sa.String(length=16), server_default="system", nullable=False),
        sa.Column("actor_ref", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        _created_at(),
    )
    op.create_index("ix_order_events_order_id", "order_events", ["order_id"])
    op.create_index("ix_order_events_group_id", "order_events", ["group_id"])

    op.create_table(
        "invoices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("group_id", sa.String(length=64), nullable=False),
        sa.Column("number", sa.String(length=48), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        _created_at(),
        sa.UniqueConstraint("number", name="uq_invoices_number"),
        sa.UniqueConstraint("shop_bot_id", "group_id", name="uq_invoices_shop_bot_id"),
    )
    op.create_index("ix_invoices_shop_bot_id", "invoices", ["shop_bot_id"])
    op.create_index("ix_invoices_group_id", "invoices", ["group_id"])

    op.create_table(
        "invoice_counters",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("last_seq", sa.Integer(), server_default="0", nullable=False),
        sa.UniqueConstraint("shop_bot_id", "period", name="uq_invoice_counters_shop_bot_id"),
    )
    op.create_index("ix_invoice_counters_shop_bot_id", "invoice_counters", ["shop_bot_id"])

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("province", sa.String(length=64), nullable=True),
        sa.Column("city", sa.String(length=64), nullable=True),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.String(length=10), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        _created_at(),
    )
    op.create_index("ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"])

    op.create_table(
        "cart_ai_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("ops_json", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.String(length=16), nullable=False),
        sa.Column("used", sa.Boolean(), server_default="false", nullable=False),
        _created_at(),
    )
    op.create_index("ix_cart_ai_proposals_cart_id", "cart_ai_proposals", ["cart_id"])

    op.create_table(
        "direct_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders_consultations.id"), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("delivered", sa.Boolean(), server_default="false", nullable=False),
        _created_at(),
    )
    op.create_index("ix_direct_messages_shop_bot_id", "direct_messages", ["shop_bot_id"])
    op.create_index("ix_direct_messages_customer_id", "direct_messages", ["customer_id"])


def downgrade() -> None:
    for t in ("direct_messages", "cart_ai_proposals", "customer_addresses", "invoice_counters", "invoices", "order_events"):
        op.drop_table(t)
    for name in (
        "payment_method", "cancel_reason", "shipping_method_name", "shipping_fee_toman",
        "carrier_name", "tracking_code", "delivered_at", "paid_at",
    ):
        op.drop_column("orders_consultations", name)
    op.drop_column("shop_bots", "legacy_ai_order_detection")
