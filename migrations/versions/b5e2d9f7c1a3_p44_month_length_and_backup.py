"""P44 · موردِ ۵۱: طولِ ماهِ انتخابیِ ادمین + بکاپِ خودکارِ دیتابیس

همه‌چیز افزوندی است (هیچ ستون/جدولی حذف نمی‌شود و هیچ دادهٔ کهنه‌ای بازنویسی نمی‌شود):

۱) `admin_settings.month_length_days` (پیش‌فرض ۰): ۰ یعنی «ماهِ تقویمی» — همان رفتاری که
   تا امروز وجود داشت، پس داده‌هایِ موجود هیچ تغییرِ معنایی نمی‌کنند. ۳۰ یا ۳۱ یعنی
   روزشمارِ دقیق (۳۱ = ۳۱ × ۲۴ ساعت کامل). فقط لحظهٔ ساختنِ شارژ/اشتراکِ تازه را اثر می‌گذارد.
۲) `admin_settings.nightly_backup_enabled` (پیش‌فرض خاموش): جابِ شبانه، تازه‌ترین فایلِ بکاپِ
   ساخته‌شده را یک‌بار برایِ ادمین‌ها می‌فرستد و قدیمی‌ها را پاک می‌کند. خاموش یعنی همان
   وضعیتِ قبل — با پیش‌فرضِ نصب، نه فایلی فرستاده می‌شود و نه فایلی از دیسک می‌رود.
۳) `admin_settings.backup_retention_days` (پیش‌فرض ۷): نگه‌داشتنِ فایل‌هایی که نامشان الگوی
   `kasbokar-YYYYMMDD-HHMMSS.dump` است؛ هر چیزِ دیگری در پوشه دست نمی‌خورد.
۴) `admin_settings.backup_last_sent_at`: زمانِ آخرین ارسالی — همان فایل دو بار فرستاده نمی‌شود.

`downgrade` هر چهار را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b5e2d9f7c1a3"
down_revision: Union[str, Sequence[str], None] = "f3a6c81b0d74"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("month_length_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "admin_settings",
        sa.Column("nightly_backup_enabled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "admin_settings",
        sa.Column("backup_retention_days", sa.Integer(), nullable=False, server_default="7"),
    )
    op.add_column(
        "admin_settings",
        sa.Column("backup_last_sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("admin_settings", "backup_last_sent_at")
    op.drop_column("admin_settings", "backup_retention_days")
    op.drop_column("admin_settings", "nightly_backup_enabled")
    op.drop_column("admin_settings", "month_length_days")
