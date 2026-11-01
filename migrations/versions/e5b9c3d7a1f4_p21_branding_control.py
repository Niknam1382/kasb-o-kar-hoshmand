"""P21 branding control: per-bot check schedule, durable alert throttle, admin interval

Revision ID: e5b9c3d7a1f4
Revises: d4a8c2e6f9b3
Create Date: 2026-11-01 16:20:00.000000

چهار ستونِ افزودنی (هیچ ستونی حذف/تغییر نمی‌کند):

- `admin_settings.branding_check_minutes` — بازرسیِ بیو از «ثابتِ ۶۰ دقیقه‌ایِ کد» به مقدارِ
  قابلِ تنظیمِ ادمین (۵ تا ۱۴۴۰ دقیقه) منتقل شد.
- `shop_bots.branding_checked_at` — «آخرین بازرسیِ همین ربات» تا فروشگاه‌دار در پنلش ببیند
  (پیش‌تر فقط یک برچسبِ سراسری در AdminSettings بود که با یک رباتِ خراب جلو نمی‌رفت).
- `shop_bots.branding_next_check_at` — نوبتِ بعدیِ *همین* ربات؛ با این، یک رباتِ توکن‌باطل
  دیگر همه‌یِ ربات‌ها را در هر لوپ دوباره وادار به درخواستِ API نمی‌کند.
- `shop_bots.branding_last_alert_at` — اخطارِ «بیوت دست‌کاری/حذف شد» تا پیش‌فرضِ ۲۴ساعته‌اش در
  حافظهٔ in-process بود و با هر ری‌استارت صفر می‌شد (و در چندپروسه دوباره اخطار می‌داد).

همه nullable/دارایِ server_default ⇒ برایِ ردیف‌هایِ موجود بی‌اثر.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5b9c3d7a1f4"
down_revision: Union[str, Sequence[str], None] = "d4a8c2e6f9b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("branding_check_minutes", sa.Integer(), server_default="60", nullable=False),
    )
    op.add_column("shop_bots", sa.Column("branding_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_bots", sa.Column("branding_next_check_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_bots", sa.Column("branding_last_alert_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "branding_last_alert_at")
    op.drop_column("shop_bots", "branding_next_check_at")
    op.drop_column("shop_bots", "branding_checked_at")
    op.drop_column("admin_settings", "branding_check_minutes")
