"""P49 · ب: دو سوییچِ کامنت رویِ `instagram_accounts`

· `auto_reply_comments`   ← پاسخِ عمومی زیرِ کامنت (APIِ رسمیِ کامنت‌ها)
· `private_reply_enabled` ← «پاسخِ خصوصی» به کامنت‌کننده (متا: یکِ پیام، تا ۷ روز)

هر دو `server_default="true"` تا با افزودنِ ستون، هیچ اتصالِ موجودی بی‌پاسخ نماند؛ مالکِ محصول
صریحاً خواست کامنت‌ها در همین نسخه باشند. درِ اصلیِ کانال همچنان سوییچِ سراسریِ ادمین
(`admin_settings.instagram_enabled`) است، پس این دو ستون بدونِ روشن‌بودنِ آن هیچ اثری ندارند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f4a8c1d7b206"
down_revision: Union[str, Sequence[str], None] = "c9a4e6f2b813"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = ("auto_reply_comments", "private_reply_enabled")


def upgrade() -> None:
    for column in NEW_COLUMNS:
        op.add_column("instagram_accounts", sa.Column(column, sa.Boolean(), server_default="true", nullable=False))


def downgrade() -> None:
    for column in reversed(NEW_COLUMNS):
        op.drop_column("instagram_accounts", column)
