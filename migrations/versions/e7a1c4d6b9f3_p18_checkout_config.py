"""P18 · B9: per-shop checkout step configuration

Revision ID: e7a1c4d6b9f3
Revises: d6f9b3e5a8c2
Create Date: 2026-10-31 18:00:00.000000

افزودنی و بدونِ حذف: `shop_bots.checkout_config` — JSONِ متنیِ روشن/خاموش و متنِ پرسشِ پنج گامِ ثابتِ
چک‌اوت. NULL یعنی «همه‌یِ گام‌ها روشن با متنِ پیش‌فرض» ⇒ دقیقاً رفتارِ امروز، پس هیچ ردیفی نیاز به
مهاجرتِ داده ندارد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7a1c4d6b9f3"
down_revision: Union[str, Sequence[str], None] = "d6f9b3e5a8c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("checkout_config", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "checkout_config")
