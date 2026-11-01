"""PHASE 5E: auditable wallet ledger columns

Revision ID: e8b3d6f1a4c9
Revises: d7a2c5e9f3b8
Create Date: 2026-11-01 19:30:00.000000

همه‌چیز افزودنی است و هیچ ستون/ردیفی حذف نمی‌شود:
* `currency` (پیش‌فرض TOMAN) و `status` (پیش‌فرض settled) با server_default ⇒ ردیف‌هایِ قدیمی
  مقدارِ درست می‌گیرند و نیازی به backfill نیست.
* `payment_id` / `order_id` ⇒ ارجاعِ مستقیم به رویدادِ مالی (تا پیشِ این فقط رشتهٔ آزادِ
  `reference` بود).
* `idempotency_key` با قیدِ یکتا (NULLهایِ چندمجاز در Postgres ⇒ ردیف‌هایِ قدیمی اذیت نمی‌شوند)
  تا یک رویدادِ تکراری (callbackِ دوباره‌ارسال‌شده، اجرایِ دوبارهٔ جاب) دو بار دفتر نزند.

نکته: ستونِ `shop_owner_id` ایندکس دارد و جمعِ زدنِ به‌ازایِ هر فروشگاه با همان ایندکس انجام می‌شود؛
ایندکسِ تازه‌ای برایِ همسنجی لازم نیست (کوئری رویِ همان کلیدِ خارجی گروه‌بندی می‌کند).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e8b3d6f1a4c9"
down_revision: Union[str, Sequence[str], None] = "d7a2c5e9f3b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("wallet_transactions", sa.Column("currency", sa.String(length=8), nullable=False, server_default="TOMAN"))
    op.add_column("wallet_transactions", sa.Column("status", sa.String(length=16), nullable=False, server_default="settled"))
    op.add_column("wallet_transactions", sa.Column("payment_id", sa.Integer(), nullable=True))
    op.add_column("wallet_transactions", sa.Column("order_id", sa.Integer(), nullable=True))
    op.add_column("wallet_transactions", sa.Column("idempotency_key", sa.String(length=64), nullable=True))
    op.create_unique_constraint("uq_wallet_tx_idempotency", "wallet_transactions", ["idempotency_key"])
    op.create_foreign_key(
        "fk_wallet_tx_payment", "wallet_transactions", "payments", ["payment_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_wallet_tx_order", "wallet_transactions", "orders_consultations", ["order_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_wallet_tx_order", "wallet_transactions", type_="foreignkey")
    op.drop_constraint("fk_wallet_tx_payment", "wallet_transactions", type_="foreignkey")
    op.drop_constraint("uq_wallet_tx_idempotency", "wallet_transactions", type_="unique")
    for name in ("idempotency_key", "order_id", "payment_id", "status", "currency"):
        op.drop_column("wallet_transactions", name)
