"""P21 branding: store the bio we actually applied

Revision ID: f6c1d4e8b2a5
Revises: e5b9c3d7a1f4
Create Date: 2026-11-01 16:55:00.000000

یک ستونِ افزودنی: `shop_bots.branding_applied_bio` — همان رشته‌ای که آخرین بار با موفقیت رویِ
ربات نوشتیم.

چرا لازم است: تا حالا «بیویِ فعلی ≠ چیزی که باید باشد» یعنی دست‌کاری. ولی وقتی خودِ ادمین
متنِ پلتفرم را عوض می‌کند یا خودِ فروشگاه‌دار متنش را ویرایش می‌کند، بیویِ کهنه هم «نامطابق»
است ⇒ هر ربات به‌اشتباه تخلف شمرده و به فروشگاه‌دار اخطارِ «بیوت دستکاری شد» می‌رفت (مثبتِ
کاذبِ واقعیِ همین تست). با داشتنِ متنِ اعمال‌شده می‌توان تفکیک کرد:

- برابرِ انتظار ⇒ سالم
- برابرِ همان چیزی که خودمان نوشتیم ولی انتظار عوض شده ⇒ بازنویسیِ عادی
- خالی ⇒ حذف شده (تخلف)
- هر چیزِ دیگر ⇒ دستکاری (تخلف)

برایِ ردیف‌هایِ موجود None است ⇒ اولین بازنویسی «حذف» حساب نمی‌شود، همان‌طور که باید.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f6c1d4e8b2a5"
down_revision: Union[str, Sequence[str], None] = "e5b9c3d7a1f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("shop_bots", sa.Column("branding_applied_bio", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "branding_applied_bio")
