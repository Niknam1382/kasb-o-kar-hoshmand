"""P33-B: نشانهٔ ثبتِ سبد — ایدبمپوتنتیِ گذارِ سبد←سفارش رویِ دیتابیس

Revision ID: b7d4e2a9c3f6
Revises: f2a6c8d3b9e5
Create Date: 2026-11-04 12:40:00.000000

دابل‌تپِ «🧾 نهایی‌کردن» تا امروز فقط با اتمیک‌بودنِ xandaniِ `MemoryStorage` مهار می‌شد
(`checkout.py`: state.clear() قبل از هر I/O). با نگهدارندهٔ دیتابیسی/Redis-محورِ FSM — یا با
دو پروسه — آن مهار از کار می‌افتد و دو سفارش ساخته می‌شد (MEASURED: test_checkout_c3 زیرِ
FSM_STORAGE=postgres). این ستون همان مهار را رویِ خودِ دیتابیس می‌گذارد.

افزودنی و بدونِ حذف؛ nullable با server_default NULL ⇒ ردیف‌هایِ موجود دست‌نخورده.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e2a9c3f6"
down_revision: Union[str, Sequence[str], None] = "f2a6c8d3b9e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("carts", sa.Column("submit_token", sa.String(length=64), nullable=True, server_default=sa.null()))


def downgrade() -> None:
    op.drop_column("carts", "submit_token")
