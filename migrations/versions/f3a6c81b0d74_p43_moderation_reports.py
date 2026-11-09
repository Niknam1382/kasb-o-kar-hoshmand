"""P43 · موردِ ۳۰/۳۱/۱۰: شاکلهٔ گزارشِ نگهبانِ محتوا + قانونِ per-shop

سه چیز افزوده می‌شود (هیچ ستون/جدولی حذف نمی‌شود):

۱) جدولِ تازهٔ `moderation_reports`: هر باری که پیامِ مشتری به قانونی می‌خورد، یکِ گزارش
   ثبت می‌شود (فروشگاه، مشتری، قانونِ در لحظه، دامنهٔ قانون، متنِ دیدنیِ کوتاه، وضعیتِ
   «بازبینی‌شده»). تا پیشِ این فقط یکِ ردیفِ ممیزی وجود داشت که هیچ پیوندی به گفتگو نداشت،
   به همین دلیلِ فروشگاه‌دار «دکمه‌ای برایِ دیدنِ چت» نداشت (موردِ ۱۰).
۲) ستونِ `moderation_rules.shop_bot_id` (nullable): NULL یعنی قانونِ سراسریِ پلتفرم؛ مقدار
   یعنی قانونِ خودِ فروشگاه. بدونِ این، گزارشِ قانونِ سراسری باید به ادمین هم برود و گزارشِ
   قانونِ خودِ فروشگاه فقط به همان صاحبِ کسب‌وکار (موردِ ۳۰).
۳) ایندکسِ خواندنیِ صفحهٔ گزارش‌ها (`shop_bot_id, reviewed, created_at`).

`downgrade` هر سه را تمیز برمی‌گرداند.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a6c81b0d74"
down_revision: Union[str, Sequence[str], None] = "d4e7b1c8a902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "moderation_rules",
        sa.Column("shop_bot_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_moderation_rules_shop_bot_id",
        "moderation_rules",
        "shop_bots",
        ["shop_bot_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_moderation_rules_shop_bot_id", "moderation_rules", ["shop_bot_id"], unique=False)

    op.create_table(
        "moderation_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_bot_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("pattern", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("reviewed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["shop_bot_id"], ["shop_bots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rule_id"], ["moderation_rules.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_moderation_reports_shop_bot_id", "moderation_reports", ["shop_bot_id"], unique=False)
    op.create_index("ix_moderation_reports_customer_id", "moderation_reports", ["customer_id"], unique=False)
    op.create_index("ix_moderation_reports_rule_id", "moderation_reports", ["rule_id"], unique=False)
    op.create_index(
        "ix_moderation_reports_shop_reviewed_created",
        "moderation_reports",
        ["shop_bot_id", "reviewed", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_moderation_reports_shop_reviewed_created", table_name="moderation_reports")
    op.drop_index("ix_moderation_reports_rule_id", table_name="moderation_reports")
    op.drop_index("ix_moderation_reports_customer_id", table_name="moderation_reports")
    op.drop_index("ix_moderation_reports_shop_bot_id", table_name="moderation_reports")
    op.drop_table("moderation_reports")
    op.drop_index("ix_moderation_rules_shop_bot_id", table_name="moderation_rules")
    op.drop_constraint("fk_moderation_rules_shop_bot_id", "moderation_rules", type_="foreignkey")
    op.drop_column("moderation_rules", "shop_bot_id")
