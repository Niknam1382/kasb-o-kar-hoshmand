"""P18 · A3: SMS switch, sender/template from the panel, and per-number OTP metadata

Revision ID: f8b2d8e1a4c7
Revises: e7a1c4d6b9f3
Create Date: 2026-11-01 10:00:00.000000

افزودنی و بدونِ حذف:
* `admin_settings.sms_enabled/sms_sender_number/sms_otp_template` — سرویسِ پیامک صریح روشن/خاموش
  می‌شود (خاموش = همان مسیرِ بدونِ پیامکِ امروز) و فرستنده/قالب از پنلِ ادمین خوانده می‌شود.
  پیش‌فرض `sms_enabled=false` ⇒ رفتارِ فعلیِ همه‌یِ نصب‌ها دست‌نخورده می‌ماند.
* `otp_codes.phone_number/sent_at/provider_status` — سقفِ ارسالِ ساعتی «به‌ازایِ هر شماره» و
  ردپایِ ارسال (برایِ برآوردِ حجم/هزینه) به این ستون‌ها نیاز دارد؛ ردیف‌هایِ قدیمی NULL می‌مانند.

نوعِ ستونِ کلیدها (sms_api_key/ai_api_key/ai_fallback_api_key) عوض نشده — فقط TypeDecorator در مدل
به `EncryptedText` تغییر کرد (همان Text در دیتابیس)، پس مهاجرتِ داده لازم نیست.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f8b2d8e1a4c7"
down_revision: Union[str, Sequence[str], None] = "e7a1c4d6b9f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("admin_settings", sa.Column("sms_sender_number", sa.String(length=32), nullable=True))
    op.add_column("admin_settings", sa.Column("sms_otp_template", sa.String(length=64), nullable=True))
    op.add_column("otp_codes", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column("otp_codes", sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("otp_codes", sa.Column("provider_status", sa.String(length=32), nullable=True))


def downgrade() -> None:
    for table, name in (
        ("otp_codes", "provider_status"),
        ("otp_codes", "sent_at"),
        ("otp_codes", "phone_number"),
        ("admin_settings", "sms_otp_template"),
        ("admin_settings", "sms_sender_number"),
        ("admin_settings", "sms_enabled"),
    ):
        op.drop_column(table, name)
