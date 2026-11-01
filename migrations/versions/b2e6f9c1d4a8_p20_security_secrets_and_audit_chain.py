"""P20 security: encrypted per-shop webhook secrets + audit hash chain

Revision ID: b2e6f9c1d4a8
Revises: a1d5e9f3b7c2
Create Date: 2026-11-01 12:10:00.000000

هیچ چیزی حذف یا کوتاه نمی‌شود؛ هر دو تغییر افزودنی/پهن‌کننده‌اند:

* `shop_bots.webhook_secret_token` از `String(64)` به `String(512)` پهن می‌شود تا همان ستون
  بتواند رمزِ Fernet را نگه دارد (مدل به `EncryptedToken(512)` عوض شده). مقادیرِ موجودِ
  ۴۳نویسه‌ای دست‌نخورده می‌مانند و `EncryptedToken` خواندنِ آن‌ها را هم می‌پذیرد؛ یک پاسِ
  بازنویسی در بوت‌آپ (`shop_bot_service.reencrypt_secrets`) هر ردیفِ خام را یک‌بار دوباره
  می‌نویسد تا رمزنگار شود ⇒ بلاکرِ امنیتیِ B2 (دسترسی به DB = ساختنِ آپدیتِ جعلی برایِ هر
  رباتِ فروشگاهی در حالتِ webhook) بسته می‌شود.
* `audit_log_entries.prev_hash` و `row_hash` (هر دو nullable): هر ردیفِ جدید، هشِ ردیفِ قبلی و
  هشِ خودش را نگه می‌دارد ⇒ حذف یا تغییرِ یک رویدادِ قدیمیِ ممیزی، زنجیره را می‌شکند.
  ردیف‌هایِ پیش ازِ P20 NULL می‌مانند و بازبینی از اولین ردیفِ هش‌دار شروع می‌شود
  (`scripts/verify_audit_chain.py`).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2e6f9c1d4a8"
down_revision: Union[str, Sequence[str], None] = "a1d5e9f3b7c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "shop_bots",
        "webhook_secret_token",
        existing_type=sa.String(length=64),
        type_=sa.String(length=512),
        existing_nullable=False,
    )
    op.add_column("audit_log_entries", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_log_entries", sa.Column("row_hash", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_audit_log_entries_row_hash"), "audit_log_entries", ["row_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_log_entries_row_hash"), table_name="audit_log_entries")
    op.drop_column("audit_log_entries", "row_hash")
    op.drop_column("audit_log_entries", "prev_hash")
    op.alter_column(
        "shop_bots",
        "webhook_secret_token",
        existing_type=sa.String(length=512),
        type_=sa.String(length=64),
        existing_nullable=False,
    )
