"""PHASE 5A: admin-configurable minimum wallet recharge

Revision ID: d7a2c5e9f3b8
Revises: c2e5a8b1d4f7
Create Date: 2026-11-01 18:00:00.000000

افزودنی و بدونِ حذف:
* `admin_settings.min_topup_amount_toman` (پیش‌فرض ۵۰٬۰۰۰ تومان) — کمترینِ مبلغِ «شارژِ کیف‌پول».

`server_default` دارد ⇒ ردیف‌هایِ موجود عددِ درست را می‌گیرند و هیچ مهاجرتِ داده‌ای لازم نیست.
مصرف‌کننده: `payment_service.ensure_recharge_amount_allowed` (سمتِ سرور، قبلِ هر ساختِ ردیفِ پرداخت).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a2c5e9f3b8"
down_revision: Union[str, Sequence[str], None] = "c2e5a8b1d4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("min_topup_amount_toman", sa.Integer(), nullable=False, server_default="50000"),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "min_topup_amount_toman")
