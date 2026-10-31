"""P18 · A7: text receipt columns on payments

Revision ID: a3c6e9f2b5d8
Revises: f2a5b8d1c4e7
Create Date: 2026-10-31 14:00:00.000000

افزودنی و بدونِ حذف: رسیدِ متنیِ شارژِ اعتبارِ پلتفرم (مثلِ سمتِ فروشگاه) با شماره‌پیگیری، اثرانگشتِ SHA-256
برایِ تشخیصِ تکراری و پرچم‌ها. ردیف‌هایِ قدیمی NULL می‌مانند و رفتارِ رسیدِ عکسی دست‌نخورده است.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a3c6e9f2b5d8"
down_revision: Union[str, Sequence[str], None] = "f2a5b8d1c4e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS: tuple[tuple[str, sa.types.TypeEngine, bool], ...] = (
    ("receipt_text", sa.Text(), False),
    ("receipt_tracking_ref", sa.String(length=64), False),
    ("receipt_sha256", sa.String(length=64), True),
    ("receipt_flags", sa.String(length=64), False),
)


def upgrade() -> None:
    for name, type_, indexed in _COLUMNS:
        op.add_column("payments", sa.Column(name, type_, nullable=True))
        if indexed:
            op.create_index(f"ix_payments_{name}", "payments", [name])


def downgrade() -> None:
    for name, _type, indexed in reversed(_COLUMNS):
        if indexed:
            op.drop_index(f"ix_payments_{name}", table_name="payments")
        op.drop_column("payments", name)
