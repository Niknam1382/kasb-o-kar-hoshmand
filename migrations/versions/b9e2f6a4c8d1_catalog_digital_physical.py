"""catalog: physical/digital products, digital_codes, shipping_methods (P1-S3 / B2)

Revision ID: b9e2f6a4c8d1
Revises: f4d8b2c6a1e9
Create Date: 2026-10-26 12:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b9e2f6a4c8d1"
down_revision: Union[str, Sequence[str], None] = "f4d8b2c6a1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- products ---
    op.add_column("products", sa.Column("kind", sa.String(length=16), server_default="physical", nullable=False))
    op.add_column("products", sa.Column("weight_grams", sa.Integer(), nullable=True))
    op.add_column("products", sa.Column("delivery_note", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("return_policy", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("ai_instructions", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("digital_delivery", sa.String(length=16), nullable=True))
    op.add_column("products", sa.Column("digital_file_id", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("digital_file_shop_file_id", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("digital_file_name", sa.String(length=255), nullable=True))
    op.add_column("products", sa.Column("digital_link", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("digital_instructions", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("digital_max_downloads", sa.Integer(), nullable=True))

    # --- orders_consultations ---
    op.add_column("orders_consultations", sa.Column("digital_delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders_consultations", sa.Column("digital_download_count", sa.Integer(), server_default="0", nullable=False))

    # --- digital_codes ---
    op.create_table(
        "digital_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", name="fk_digital_codes_product_id_products"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="available", nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders_consultations.id", name="fk_digital_codes_order_id_orders_consultations"), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("product_id", "code_hash", name="uq_digital_codes_product_id"),
    )
    op.create_index("ix_digital_codes_product_id", "digital_codes", ["product_id"])
    op.create_index("ix_digital_codes_status", "digital_codes", ["status"])
    op.create_index("ix_digital_codes_order_id", "digital_codes", ["order_id"])

    # --- shipping_methods ---
    op.create_table(
        "shipping_methods",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id", name="fk_shipping_methods_shop_bot_id_shop_bots"), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("fee_toman", sa.Integer(), server_default="0", nullable=False),
        sa.Column("free_over_toman", sa.Integer(), nullable=True),
        sa.Column("eta_text", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_shipping_methods_shop_bot_id", "shipping_methods", ["shop_bot_id"])


def downgrade() -> None:
    op.drop_index("ix_shipping_methods_shop_bot_id", table_name="shipping_methods")
    op.drop_table("shipping_methods")
    op.drop_index("ix_digital_codes_order_id", table_name="digital_codes")
    op.drop_index("ix_digital_codes_status", table_name="digital_codes")
    op.drop_index("ix_digital_codes_product_id", table_name="digital_codes")
    op.drop_table("digital_codes")
    op.drop_column("orders_consultations", "digital_download_count")
    op.drop_column("orders_consultations", "digital_delivered_at")
    for col in (
        "digital_max_downloads", "digital_instructions", "digital_link", "digital_file_name",
        "digital_file_shop_file_id", "digital_file_id", "digital_delivery", "ai_instructions",
        "return_policy", "delivery_note", "weight_grams", "kind",
    ):
        op.drop_column("products", col)
