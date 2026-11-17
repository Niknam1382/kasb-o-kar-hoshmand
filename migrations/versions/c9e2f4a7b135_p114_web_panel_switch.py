"""پ۱۱۴ · سوئیچِ سراسریِ «پنجرهٔ نوشتنیِ وب» رویِ `admin_settings`

Revision ID: c9e2f4a7b135
Revises: a3f7c2b5d810
Create Date: 2026-11-17 21:10:00.000000

ضرورت (خواستهٔ مستقیمِ مالکِ محصول): تا پیشِ این دکمهٔ «🌐 پنلِ وب» همیشه در پنلِ فروشگاه‌دار
می‌ماند و فقط بعد ازِ زدنِ دکمه به صاحبش گفته می‌شد که قابلیت خاموش است. مالک می‌خواست بتواند
*پیش ازِ* آماده‌سازیِ قابلیت، دکمه را از پنلِ کاربران محو کند. راهِ فنی همان الگویِ `instagram_enabled`
(پ۴۹-الف) است: یکِ سوئیچِ سراسریِ جدید + دیدنی‌بودنِ مشروط در کیبورد.

کاملاً افزودنی است: یکِ ستونِ خالی‌ناپذیر با `server_default = 'true'` (پیش‌فرضِ روشن یعنی رفتارِ
نصب‌هایِ موجود در لحظهٔ ارتقا عوض نمی‌شود؛ پنهان‌کردنِ دکمه یکِ انتخابِ ادمین است). `downgrade`
فقط همان ستون را برمی‌گرداند و هیچ داده‌ای را حذف نمی‌کند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e2f4a7b135"
down_revision: Union[str, Sequence[str], None] = "a3f7c2b5d810"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column(
            "web_panel_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "web_panel_enabled")
