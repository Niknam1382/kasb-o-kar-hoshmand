"""پ۷۶ · ارسالِ تکرارشونده: سه ستونِ افزودنی رویِ `scheduled_broadcasts`

Revision ID: d6a9c3e5b170
Revises: c5f8b2d9e410
Create Date: 2026-11-15 12:00:00.000000

همه با `server_default` ⇒ هیچ ردیفِ موجودی رفتارِ تازه نمی‌گیرد: `repeat_kind="once"` دقیقاً همان
مسیرِ امروز است (یکِ نوبت، سپس `queued`) و `repeat_sent=0` فقط شمارِ نوبت‌ها را نگه می‌دارد.
`downgrade` همین سه ستون را برمی‌گرداند و هیچ چیزِ دیگری را لمس نمی‌کند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d6a9c3e5b170"
down_revision: Union[str, Sequence[str], None] = "c5f8b2d9e410"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("scheduled_broadcasts", sa.Column("repeat_kind", sa.String(length=12), server_default="once", nullable=False))
    op.add_column("scheduled_broadcasts", sa.Column("repeat_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("scheduled_broadcasts", sa.Column("repeat_sent", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("scheduled_broadcasts", "repeat_sent")
    op.drop_column("scheduled_broadcasts", "repeat_until")
    op.drop_column("scheduled_broadcasts", "repeat_kind")
