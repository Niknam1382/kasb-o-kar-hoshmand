"""P21-E: دامنه‌یِ فروشگاه‌هایِ ادمینِ عملیاتی

Revision ID: c9f4a7e2b5d8
Revises: b8e3f6a1d4c7
Create Date: 2026-11-01 19:20:00.000000

یک ستونِ افزودنی: `admin_roles.allowed_owner_ids` (متنِ کاماجدا از شناسهٔ فروشگاه‌دارها؛
NULL ⇒ بدونِ محدودیت، یعنی همان رفتارِ امروز).

چرا: امروز «ادمینِ عملیاتی» یا هیچ‌کاره است یا رویِ *همهٔ* فروشگاه‌هاقدرتمند. برایِ یکِ تیمِ
پشتیبانیِ چندنفره که فقط مشتری‌هایِ خودش را می‌بیند، حدِ میانی لازم است — وگرنه باید
سوپرادمینشان کرد (خطرناک‌تر) یا هیچ‌کاری داد (بی‌فایده).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9f4a7e2b5d8"
down_revision: Union[str, Sequence[str], None] = "b8e3f6a1d4c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_roles", sa.Column("allowed_owner_ids", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_roles", "allowed_owner_ids")
