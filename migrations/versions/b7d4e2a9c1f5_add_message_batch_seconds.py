"""add shop_bots.message_batch_seconds

Revision ID: b7d4e2a9c1f5
Revises: a6f3d9e1b7c4
Create Date: 2026-10-08 00:00:00.000000

فازِ ۶-الف: مدتِ تجمیعِ پیام‌هایِ مشتری (ثانیه) به‌ازایِ هر فروشگاه. ستونِ جدید nullable ـه (null = پیش‌فرضِ
سیستم)، پس ردیف‌هایِ قدیمی دست‌نخورده می‌مونن و رفتارِ قبلی حفظ می‌شه.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e2a9c1f5"
down_revision: Union[str, Sequence[str], None] = "a6f3d9e1b7c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("message_batch_seconds", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "message_batch_seconds")
