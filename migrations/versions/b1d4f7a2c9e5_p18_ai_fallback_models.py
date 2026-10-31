"""P18 · A4: per-key fallback model chains in the AI pool

Revision ID: b1d4f7a2c9e5
Revises: a9c3e6b8d1f5
Create Date: 2026-11-01 14:00:00.000000

افزودنی و بدونِ حذف:
* `ai_api_key_pool.fallback_models` — فهرستِ ترتیبیِ مدل‌هایِ پشتیبانِ *همان کلید* (ویرگول یا خطِ جدید).
  رشته‌یِ خالی یعنی «پشتیبانی ندارم» ⇒ رفتارِ امروز دست‌نخورده می‌ماند.

`capability` یک String(32) است، پس مقدارِ تازه‌یِ `stt` بدونِ مایگریشن قابلِ ذخیره است.
ستونِ `api_key` هم فقط در مدل به `EncryptedToken` تبدیل شده (نوعِ ستون در دیتابیس همان Text است؛
خودِ TypeDecorator هنگامِ خواندن مقدارِ رمزنگاری‌نشده‌یِ قدیمی را می‌پذیرد) ⇒ مایگریشنِ لازم نیست.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b1d4f7a2c9e5"
down_revision: Union[str, Sequence[str], None] = "a9c3e6b8d1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_api_key_pool", sa.Column("fallback_models", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("ai_api_key_pool", "fallback_models")
