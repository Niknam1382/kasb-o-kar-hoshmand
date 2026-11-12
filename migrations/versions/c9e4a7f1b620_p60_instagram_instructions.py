"""پ۶۰ · خواستهٔ مالکِ محصول: متنِ هوشمندسازیِ اینستاگرام برایِ هر فروشگاه + متنِ سراسریِ ادمین

· `instagram_accounts.instructions`            ← دستورِ اختصاصیِ خودِ فروشگاه برایِ دایرکت/کامنت
· `admin_settings.instagram_platform_instructions` ← متنِ پیش‌فرضِ سراسری که اگر فروشگاه چیزی
  ننویست همان اجرا می‌شود، و اگر نوشت، کنارِ متنِ خودش می‌نشیند (همان الگویِ بیوگرافی).

هر دو ستون nullable و افزودنی‌اند و `server_default=""` دارند ⇒ هیچ ردیفِ موجودی رفتارِ تازه
نمی‌گیرد (متنِ خالی یعنی «فقط تنظیماتِ قبلی»)، هیچ ستون یا جدولی حذف نمی‌شود، و `downgrade`
فقط همین دو افزوده را به ترتیبِ معکوس برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9e4a7f1b620"
down_revision: Union[str, Sequence[str], None] = "b7d3e8a2c451"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instagram_accounts",
        sa.Column("instructions", sa.Text(), nullable=True, server_default="", comment="دستورِ اختصاصیِ اینستاگرامِ فروشگاه"),
    )
    op.add_column(
        "admin_settings",
        sa.Column("instagram_platform_instructions", sa.Text(), nullable=True, server_default="", comment="متنِ سراسریِ هوشمندسازیِ اینستاگرام"),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "instagram_platform_instructions")
    op.drop_column("instagram_accounts", "instructions")
