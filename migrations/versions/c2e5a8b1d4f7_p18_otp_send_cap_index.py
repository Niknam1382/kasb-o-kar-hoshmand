"""P18 · د: index for the per-phone SMS send cap

Revision ID: c2e5a8b1d4f7
Revises: b1d4f7a2c9e5
Create Date: 2026-11-01 16:00:00.000000

سقفِ ارسالِ ساعتی (A3) به‌ازایِ هر شماره با `SELECT count(*) FROM otp_codes WHERE phone_number=? AND
purpose=? AND sent_at>=?` چک می‌شود. بدونِ ایندکس، هر درخواستِ OTP یک پیمایشِ کاملِ جدول است.
ایندکسِ غیریکتا و افزودنی ⇒ هیچ داده‌ای تغییر نمی‌کند و هیچ قفلی رویِ نوشتن نمی‌گذارد.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "c2e5a8b1d4f7"
down_revision: Union[str, Sequence[str], None] = "b1d4f7a2c9e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_otp_codes_phone_purpose_sent", "otp_codes", ["phone_number", "purpose", "sent_at"])


def downgrade() -> None:
    op.drop_index("ix_otp_codes_phone_purpose_sent", table_name="otp_codes")
