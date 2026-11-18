"""پ۱۲۰ · مرچنت‌آیدی زرین‌پالِ پلتفرم از VARCHAR(64) به TEXT (تا رمزنگاریِ `EncryptedText` جا شود)

Revision ID: d7b3f0a4c8e2
Revises: c9e2f4a7b135
Create Date: 2026-11-18 01:40:00.000000

ضرورت (یافتهٔ ۵ِ بازرسی، آخرین قلمِ بازِ آن): `admin_settings.zarinpal_merchant_id` تنها
هم‌خانوادهٔ رازها در این جدول بود که *خام* در دیتابیس می‌خوابید (`ai_api_key`،
`bale_bot_token` و … همه `EncryptedText`‌اند) ⇒ هر `pg_dump` یا هر بازخوانیِ پشتیبان، شناسهٔ
درگاهِ پلتفرم را با خودش می‌برد.

فقط عرضِ ستون آزاد می‌شود: متنِ Fernetِ یکِ شناسهٔ ۳۶ نویسه‌ای ≈۱۴۰ نویسه است و در VARCHAR(64)
نمی‌گنجد. رمزنگاریِ خودِ مقدار در ORM انجام می‌شود و نوعِ `EncryptedText` همان `Text` است؛
مقادیرِ قدیمیِ خام هم خوانده می‌شوند و یکِ پاسِ بوت‌آپ (`admin_settings_service.reencrypt_merchant_id`)
آن‌ها را رمز می‌کند — به همان دلیلی که رازهایِ وب‌هوک در مایگریشن رمز نمی‌شوند: `ENCRYPTION_KEY`
فقط در خودِ ربات در دسترس است، نه در ابزارِ مایگریشن.

کاملاً افزودنی است: هیچ ستونی حذف/تنگ نمی‌شود و هیچ داده‌ای از بین نمی‌رود (TEXT ⊃ VARCHAR).
`downgrade` عمداً no-op است: برگرداندنِ ستون به VARCHAR(64) رویِ ردیفِ رمزنگاری‌شده (≈۱۴۰ نویسه)
خطایِ «ارزش خیلی بلند است» می‌سازد و یکِ ارتقایِ بی‌خطر را به مسیرِ یک‌طرفه تبدیل می‌کرد؛
عرضِ بازِ ستون به‌تنهایی هیچ رفتاری را عوض نمی‌کند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7b3f0a4c8e2"
down_revision: Union[str, Sequence[str], None] = "c9e2f4a7b135"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "admin_settings",
        "zarinpal_merchant_id",
        existing_type=sa.String(length=64),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    # no-op — توضیحِ بالا: تنگ‌کردنِ ستون رویِ دادهٔ رمزنگاری‌شده، ارتقا را یک‌طرفه می‌کند.
    pass
