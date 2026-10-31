"""add campaigns

Revision ID: 5e8b1c3a9d27
Revises: 4a5ff6ec25f3
Create Date: 2026-10-02 00:00:00.000000

فازِ ۳ — سازنده‌ی کمپین (تخفیفِ مخصوصِ مشتری):
- جدولِ جدیدِ campaigns (هر ردیف یه کمپینِ تخفیفِ یه فروشگاه؛ code نال = خودکار).
- orders_consultations.campaign_id / discount_toman: کمپینِ اعمال‌شده و سهمِ همون
  ردیف از تخفیفِ سبد (هر دو نال‌پذیر؛ ردیف‌هایِ قدیمی دست‌نخورده می‌مونن).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5e8b1c3a9d27"
down_revision: Union[str, Sequence[str], None] = "4a5ff6ec25f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=True),
        sa.Column("discount_type", sa.String(length=32), nullable=False),
        sa.Column("discount_value", sa.Integer(), nullable=False),
        sa.Column("max_discount_toman", sa.Integer(), nullable=True),
        sa.Column("min_cart_total_toman", sa.Integer(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_usage_limit", sa.Integer(), nullable=True),
        sa.Column("per_customer_limit", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shop_bot_id", "code", name=op.f("uq_campaigns_shop_bot_id")),
    )
    op.alter_column("campaigns", "is_active", server_default=None)
    op.create_index(op.f("ix_campaigns_shop_bot_id"), "campaigns", ["shop_bot_id"], unique=False)

    op.add_column("orders_consultations", sa.Column("campaign_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_orders_consultations_campaign_id_campaigns"), "orders_consultations", "campaigns", ["campaign_id"], ["id"]
    )
    op.create_index(op.f("ix_orders_consultations_campaign_id"), "orders_consultations", ["campaign_id"], unique=False)
    op.add_column("orders_consultations", sa.Column("discount_toman", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders_consultations", "discount_toman")
    op.drop_index(op.f("ix_orders_consultations_campaign_id"), table_name="orders_consultations")
    op.drop_constraint(op.f("fk_orders_consultations_campaign_id_campaigns"), "orders_consultations", type_="foreignkey")
    op.drop_column("orders_consultations", "campaign_id")

    op.drop_table("campaigns")
