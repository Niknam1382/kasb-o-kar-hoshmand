"""پ۷۲ · ایجنتِ سرور راند ۲: آستانه‌هایِ تنظیم‌شدنیِ عیب‌یاب

· `admin_settings.doctor_thresholds` ← JSONِ کوچکِ «تفاوت با پیش‌فرض»؛ خالی یعنی همان عددِ پ۶۲

ستون nullable و افزودنی است ⇒ هیچ ردیفِ موجودی مقدارِ تازه یا رفتارِ تازه نمی‌گیرد و پیش‌فرض‌ها
همچنان در `server_doctor.THRESHOLD_SPECS` قفل‌اند (تستِ پ۶۲ نشکست). `downgrade` فقط همین را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f2c5b9a1d340"
down_revision: Union[str, Sequence[str], None] = "e1b7c9d4a205"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("doctor_thresholds", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("admin_settings", "doctor_thresholds")
