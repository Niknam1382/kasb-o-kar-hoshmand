"""add shopping cart

Revision ID: 4a5ff6ec25f3
Revises: add8532680c2
Create Date: 2026-09-27 00:00:00.000000

فازِ ۳ — سبدِ خریدِ واقعی:
- shop_bots.checkout_questions: سوال‌هایِ چک‌اوتِ فروشگاه‌دار-تعریف‌شده.
- orders_consultations.cart_checkout_group_id / checkout_answers: گروه‌بندیِ
  نمایشیِ سفارش‌هایِ حاصل از یه چک‌اوتِ سبد + جوابِ سوال‌هایِ چک‌اوت.
- دو جدولِ جدید: carts, cart_items.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4a5ff6ec25f3"
down_revision: Union[str, Sequence[str], None] = "add8532680c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("checkout_questions", sa.Text(), nullable=True))

    op.add_column("orders_consultations", sa.Column("cart_checkout_group_id", sa.String(length=64), nullable=True))
    op.create_index(
        op.f("ix_orders_consultations_cart_checkout_group_id"), "orders_consultations", ["cart_checkout_group_id"], unique=False
    )
    op.add_column("orders_consultations", sa.Column("checkout_answers", sa.Text(), nullable=True))

    op.create_table(
        "carts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shop_bot_id", "customer_id", name=op.f("uq_carts_shop_bot_id")),
    )
    op.create_index(op.f("ix_carts_shop_bot_id"), "carts", ["shop_bot_id"], unique=False)
    op.create_index(op.f("ix_carts_customer_id"), "carts", ["customer_id"], unique=False)

    op.create_table(
        "cart_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cart_id", sa.Integer(), sa.ForeignKey("carts.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("cart_id", "product_id", name=op.f("uq_cart_items_cart_id")),
    )
    op.alter_column("cart_items", "quantity", server_default=None)
    op.create_index(op.f("ix_cart_items_cart_id"), "cart_items", ["cart_id"], unique=False)


def downgrade() -> None:
    op.drop_table("cart_items")
    op.drop_table("carts")

    op.drop_column("orders_consultations", "checkout_answers")
    op.drop_index(op.f("ix_orders_consultations_cart_checkout_group_id"), table_name="orders_consultations")
    op.drop_column("orders_consultations", "cart_checkout_group_id")

    op.drop_column("shop_bots", "checkout_questions")
