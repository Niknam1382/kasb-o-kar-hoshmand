"""P18 · B4: customers.is_blocked

Revision ID: c5e8a2d4f7b1
Revises: b4d7f1a3c6e9
Create Date: 2026-10-31 16:00:00.000000

افزودنی و بدونِ حذف: پرچمِ بلاک‌بودنِ مشتری. پیش‌فرض false ⇒ همه‌یِ ردیف‌هایِ موجود دقیقاً مثلِ قبل
کار می‌کنند. گفتگوها پاک نمی‌شوند؛ فقط رفتارِ رباتِ فروشگاه نسبت به آن مشتری عوض می‌شود.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5e8a2d4f7b1"
down_revision: Union[str, Sequence[str], None] = "b4d7f1a3c6e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("customers", "is_blocked")
