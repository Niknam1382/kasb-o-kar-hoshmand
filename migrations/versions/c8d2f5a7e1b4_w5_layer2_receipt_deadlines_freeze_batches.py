"""W5 layer 2: receipt AI cost, deadline bounds, jobs pause, review warning, restock, time freezes, credit batches

Revision ID: c8d2f5a7e1b4
Revises: b7c1e4a9d2f3
Create Date: 2026-10-28 18:00:00.000000

فقط افزودنی است (هیچ ستون/جدولی حذف نمی‌شود). ستون‌هایِ NOT NULL با server_default می‌آیند تا ردیف‌هایِ موجود پر بشن.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c8d2f5a7e1b4"
down_revision: Union[str, Sequence[str], None] = "b7c1e4a9d2f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("wallet_cost_receipt_analysis_toman", sa.Integer(), server_default="500", nullable=False))
    op.add_column("admin_settings", sa.Column("payment_deadline_min_minutes", sa.Integer(), server_default="5", nullable=False))
    op.add_column("admin_settings", sa.Column("payment_deadline_max_minutes", sa.Integer(), server_default="1440", nullable=False))
    op.add_column("admin_settings", sa.Column("review_hold_min_hours", sa.Integer(), server_default="1", nullable=False))
    op.add_column("admin_settings", sa.Column("review_hold_max_hours", sa.Integer(), server_default="72", nullable=False))
    op.add_column("admin_settings", sa.Column("jobs_paused", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("admin_settings", sa.Column("jobs_paused_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("admin_settings", sa.Column("jobs_paused_by", sa.String(length=64), nullable=True))
    op.add_column("admin_settings", sa.Column("jobs_paused_groups", sa.String(length=200), nullable=True))
    op.add_column("order_payments", sa.Column("review_warned_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders_consultations", sa.Column("restocked_at", sa.DateTime(timezone=True), nullable=True))

    op.create_table(
        "time_freezes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("scope", sa.String(length=8), nullable=False),
        sa.Column("shop_owner_id", sa.Integer(), sa.ForeignKey("shop_owners.id"), nullable=True),
        sa.Column("status", sa.String(length=12), server_default="active", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_days", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_by", sa.String(length=64), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resumed_by", sa.String(length=64), nullable=True),
        sa.Column("shifted_seconds", sa.Integer(), nullable=True),
        sa.Column("affected_count", sa.Integer(), nullable=True),
    )
    op.create_index("ix_time_freezes_shop_owner_id", "time_freezes", ["shop_owner_id"])
    op.create_index("ix_time_freezes_status", "time_freezes", ["status"])

    op.create_table(
        "admin_credit_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("batch_id", sa.String(length=32), nullable=False, unique=True),
        sa.Column("kind", sa.String(length=8), nullable=False),
        sa.Column("params_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="previewed", nullable=False),
        sa.Column("target_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("applied_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "admin_credit_batch_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.String(length=32), nullable=False),
        sa.Column("shop_owner_id", sa.Integer(), sa.ForeignKey("shop_owners.id"), nullable=False),
        sa.UniqueConstraint("batch_id", "shop_owner_id", name="uq_credit_batch_owner"),
    )
    op.create_index("ix_admin_credit_batch_items_batch_id", "admin_credit_batch_items", ["batch_id"])
    op.create_index("ix_admin_credit_batch_items_shop_owner_id", "admin_credit_batch_items", ["shop_owner_id"])


def downgrade() -> None:
    op.drop_index("ix_admin_credit_batch_items_shop_owner_id", table_name="admin_credit_batch_items")
    op.drop_index("ix_admin_credit_batch_items_batch_id", table_name="admin_credit_batch_items")
    op.drop_table("admin_credit_batch_items")
    op.drop_table("admin_credit_batches")
    op.drop_index("ix_time_freezes_status", table_name="time_freezes")
    op.drop_index("ix_time_freezes_shop_owner_id", table_name="time_freezes")
    op.drop_table("time_freezes")
    op.drop_column("orders_consultations", "restocked_at")
    op.drop_column("order_payments", "review_warned_at")
    for column in (
        "jobs_paused_groups", "jobs_paused_by", "jobs_paused_at", "jobs_paused", "review_hold_max_hours", "review_hold_min_hours",
        "payment_deadline_max_minutes", "payment_deadline_min_minutes", "wallet_cost_receipt_analysis_toman",
    ):
        op.drop_column("admin_settings", column)
