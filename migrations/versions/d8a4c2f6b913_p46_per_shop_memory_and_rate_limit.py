"""P46 · مواردِ ۳۷ و ۱۴: سه تنظیمِ per-shopِ تازه رویِ `shop_bots`

· `history_limit_messages`  ← «حافظهٔ هر گفتگو» (چند پیامِ آخر به هوشِ مصنوعی داده شود)
· `rate_limit_messages`     ← سقفِ پیامِ هر مشتری در پنجره‌یِ زمانی
· `rate_limit_seconds`      ← طولِ همان پنجره (ثانیه)

همه nullable و بدونِ `server_default` ⇒ NULL یعنی «همان پیش‌فرضِ سراسریِ `admin_settings`»؛ پس
هیچ فروشگاهِ موجودی رفتارِ تازه‌ای پیدا نمی‌کند و هیچ مهاجرتِ داده لازم نیست. ستون‌هایِ سراسری
به‌عنوانِ پیش‌فرض و guardrailِ ادمین سرِ جایشان می‌مانند (قاعدهٔ ۵ و ۷؛ چیزی حذف نمی‌شود).

`downgrade` هر سه را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8a4c2f6b913"
down_revision: Union[str, Sequence[str], None] = "c7d3a91e5b48"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = (
    "history_limit_messages",
    "rate_limit_messages",
    "rate_limit_seconds",
)


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column("shop_bots", sa.Column(column, sa.Integer(), nullable=True))


def downgrade() -> None:
    for column in reversed(NEW_COLUMNS):
        op.drop_column("shop_bots", column)
