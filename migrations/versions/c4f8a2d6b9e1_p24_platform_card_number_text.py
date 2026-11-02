"""P24: رمزنگاریِ شمارهٔ کارتِ پلتفرم (فقط عریض‌کردنِ ستون)

Revision ID: c4f8a2d6b9e1
Revises: b3e7d1a9c4f6
Create Date: 2026-11-02 13:20:00.000000

`platform_card_number` از P18 در مدل `EncryptedText` شدنی بود، ولی ستونِ دیتابیس `VARCHAR(32)`
است و متنِ رمزنگاری‌شدهٔ Fernet بلندتر از ۳۲ نویسه است. این مایگریشن **فقط نوع را به TEXT
می‌رساند** (در PostgreSQL افزایشِ عرضِ varchar/text بازنویسیِ جدول نیست و داده را از بین نمی‌برد).

چرا مهاجرتِ داده لازم نیست: `EncryptedToken.process_result_value` مقدارِ رمزنگاری‌نشدهٔ قدیمی را
هم می‌خواند (فالنک) و با اولین نوشتن، رمز می‌شود. یعنی:
- ردیف‌هایِ کهنه دست‌نخورده می‌مانند و هنوز خوانده می‌شوند؛
- از اولین ویرایشِ ادمین، نسخهٔ داخلِ دیتابیس فقط CipherText است؛
- `.env.example` و `docs/admin-guide.md` بالاخره به آنچه واقعاً اتفاق می‌افتد اشاره می‌کنند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a2d6b9e1"
down_revision: Union[str, Sequence[str], None] = "b3e7d1a9c4f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("admin_settings", "platform_card_number", type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # برگشت به VARCHAR(32): مقدارِ رمزنگاری‌شده در آن جا نمی‌شود، برایِ همین در حالتِ
    # رمزنگاری‌شده این downgrade عملاً باید با «پاک‌کردنِ مقدارِ ستون» همراه باشد؛ اینجا
    # فقط نوع برگردانده می‌شود و خودِ داده دست نمی‌خورد (اگر مقداری بلندتر بماند،
    # PG آن را رد می‌کند، نه اینکه خراب شود).
    op.alter_column("admin_settings", "platform_card_number", type_=sa.String(length=32), existing_nullable=True)
