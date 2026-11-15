"""پ۷۹ · جمعِ شمارنده‌ها بینِ پروسه‌ها: جدولِ تازهٔ `runtime_counter_snapshots`

Revision ID: f8c3a1d6b240
Revises: e7b2d4c8a910
Create Date: 2026-11-15 18:40:00.000000

ضرورت: شمارنده‌هایِ عملیاتی (`observability.count`) در حافظهٔ هرِ پروسه می‌مانند، ولی عیب‌یابِ سرور و
پنلِ ظرفیت در پروسهٔ core خوانده می‌شوند ⇒ در استقرارِ چند‌worker عددِ «رویدادِ نامعتبرِ ردشده» و
«ردِ برداشتِ کیف‌پول» فقط سهمِ یکِ پروسه بود. این جدولِ افزودنی هرِ پروسه را به یکِ ردیفِ دوره‌ای
می‌رساند تا جمعِ آن‌ها در زمانِ خواندن ممکن شود. هیچ جدول/ستونی حذف نمی‌شود.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8c3a1d6b240"
down_revision: Union[str, Sequence[str], None] = "e7b2d4c8a910"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "runtime_counter_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("process_key", sa.String(length=96), nullable=False),
        sa.Column("hostname", sa.String(length=64), server_default="", nullable=False),
        sa.Column("counters", sa.Text(), server_default="{}", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_runtime_counter_snapshots"),
        sa.UniqueConstraint("process_key", name="uq_runtime_counter_snapshots_process_key"),
    )


def downgrade() -> None:
    op.drop_table("runtime_counter_snapshots")
