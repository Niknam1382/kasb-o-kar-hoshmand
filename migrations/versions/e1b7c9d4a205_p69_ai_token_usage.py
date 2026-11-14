"""پ۶۹ · موردِ ۳۶: ثبتِ توکن‌هایِ واقعیِ هر فراخوانیِ AI برایِ برآوردِ هزینهٔ تمام‌شده

· `wallet_transactions.ai_total_tokens` ← همان کسر، حالا می‌گوید چند توکن مصرف شد
· `ix_wallet_transactions_ai_tokens` ← گروه‌کردنِ بازه‌دارِ فراخوانی‌هایِ دارایِ توکن

ستون nullable و افزودنی است ⇒ هیچ ردیفِ موجودی مقدارِ تازه‌ای نمی‌گیرد و هیچ رفتارِ نوشتنی عوض
نمی‌شود: ردیف‌هایِ قدیمی و کسرهایِ بی‌AI (شارژ، کمیسیون، اصلاحِ ادمین) و مسیرهایِ بی‌usage
(تبدیلِ صوت) `NULL` می‌مانند. صفحهٔ برآورد عمداً می‌گوید «Coverage: X/Y» تا عددِ ساختگی از
گذشته ساخته نشود. `downgrade` فقط همین دو افزوده را به ترتیبِ معکوس برمی‌گرداند.

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1b7c9d4a205"
down_revision: Union[str, Sequence[str], None] = "d3a8c1f5b742"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "wallet_transactions",
        sa.Column("ai_total_tokens", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_wallet_transactions_ai_tokens",
        "wallet_transactions",
        ["created_at", "reason"],
        postgresql_where=sa.text("ai_total_tokens IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_wallet_transactions_ai_tokens", table_name="wallet_transactions")
    op.drop_column("wallet_transactions", "ai_total_tokens")
