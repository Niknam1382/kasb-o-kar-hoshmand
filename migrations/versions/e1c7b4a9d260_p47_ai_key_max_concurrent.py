"""P47 · استخرِ ۱۰ کلیدِ AI: سقفِ همزمانیِ هرِ کلید در همان پنل

ستونِ تازه‌یِ `ai_api_key_pool.max_concurrent` (Integer، nullable) ⇒ NULL یعنی «سهمِ مساوی از
سقفِ پلتفرم»؛ پس هیچ کلیدِ ثبت‌شده‌ای رفتارِ تازه‌ای پیدا نمی‌کند و هیچ مهاجرتِ داده لازم نیست.
سقفِ پلتفرم مثلِ قبل `AI_MAX_CONCURRENT_CALLS` است و چیزی از جدولِ کلیدها حذف نمی‌شود.

`downgrade` همان یک ستون را برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1c7b4a9d260"
down_revision: Union[str, Sequence[str], None] = "d8a4c2f6b913"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ai_api_key_pool", sa.Column("max_concurrent", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_api_key_pool", "max_concurrent")
