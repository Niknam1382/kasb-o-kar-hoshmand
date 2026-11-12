"""پ۶۳ · خواستهٔ مالکِ محصول (۲۰۲۶-۱۱-۱۲): «پنلِ ویژهٔ مدیریتیِ اینستاگرام در پنلِ خودِ کاربر».

· `instagram_accounts.muted_until` ← خاموش‌سازیِ *زمان‌دارِ* کانال (۱/۶/۲۴ ساعت یا ۳ روز)، بدونِ
  قطعِ اتصال و بدونِ دست‌کاریِ توکن. NULL یعنی «روشن» ⇒ هیچ اکانتِ موجودی رفتارِ تازه نمی‌گیرد.

افزوندیِ یکِ ستونِ nullable است: هیچ ستون/جدولی حذف نمی‌شود، ردیفِ موجودی مقدارِ معنادارِ تازه
نمی‌گیرد، و `downgrade` فقط همین ستون را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d3a8c1f5b742"
down_revision: Union[str, Sequence[str], None] = "c9e4a7f1b620"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "instagram_accounts",
        sa.Column("muted_until", sa.DateTime(timezone=True), nullable=True, comment="خاموشِ پاسخ‌گویی تا این زمان (NULL ⇒ روشن)"),
    )


def downgrade() -> None:
    op.drop_column("instagram_accounts", "muted_until")
