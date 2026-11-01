"""P19: each shop can connect its own Bale bot (smart on Bale, same wallet costs)

Revision ID: a1d5e9f3b7c2
Revises: f9c4a7d2b5e8
Create Date: 2026-11-01 23:30:00.000000

همه‌یِ تغییرات افزودنی‌اند و هیچ ستون/ردیفی حذف نمی‌شود:

* `admin_settings.bale_shop_bots_enabled` (پیش‌فرض false) ⇒ تا رونمایی نشده نه دکمه‌یِ ثبتِ توکن
  در پنلِ فروشگاه‌دار دیده می‌شود و نه هیچ اتصالِ بله‌ای شروع می‌شود.
* `shop_bots.bale_encrypted_token` (String(512)، همان نوعِ رمزنگاریِ توکنِ تلگرام چون کنترلِ کاملِ
  ربات را می‌دهد)، `bale_bot_id` (یکتا؛ برایِ اینکه آپدیتِ رسیده از بله به همین فروشگاه نگاشت شود)،
  `bale_bot_username` (نمایش/لینک) و `bale_bot_enabled` (سوییچِ خودِ فروشگاه‌دار بدونِ حذفِ توکن).
* `customers.platform` — شناسه‌یِ عددیِ کاربر فقط داخلِ *یک* سرویسِ پیام‌رسان یکتاست؛ دو آدمِ غریبه
  (یکی تلگرام، یکی بله) می‌تونن عددِ یکسان داشته باشن و اگر پلتفرم بخشی از کلید نباشه یک سبد،
  یک تاریخچه‌یِ گفتگو و یک «بلاک» مشترک می‌گیرند. کلیدِ یکتا از (shop_bot_id, telegram_id) به
  (shop_bot_id, telegram_id, platform) تبدیل می‌شود؛ ردیف‌هایِ موجود همه platform='telegram' می‌گیرند
  ⇒ هیچ هویتِ امروز جابه‌جا نمی‌شود.

pre-existing rows همه با server_default مقدارِ خنثی می‌گیرند ⇒ رفتارِ امروز دست‌نخورده.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1d5e9f3b7c2"
down_revision: Union[str, Sequence[str], None] = "f9c4a7d2b5e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings", sa.Column("bale_shop_bots_enabled", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("shop_bots", sa.Column("bale_encrypted_token", sa.String(length=512), nullable=True))
    op.add_column("shop_bots", sa.Column("bale_bot_id", sa.BigInteger(), nullable=True))
    op.create_unique_constraint(op.f("uq_shop_bots_bale_bot_id"), "shop_bots", ["bale_bot_id"])
    op.add_column("shop_bots", sa.Column("bale_bot_username", sa.String(length=64), nullable=True))
    op.add_column("shop_bots", sa.Column("bale_bot_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.add_column("customers", sa.Column("platform", sa.String(length=16), nullable=False, server_default="telegram"))
    op.drop_constraint(op.f("uq_customers_shop_bot_id"), "customers", type_="unique")
    op.create_unique_constraint(
        op.f("uq_customers_shop_bot_id_platform"), "customers", ["shop_bot_id", "telegram_id", "platform"]
    )


def downgrade() -> None:
    op.drop_constraint(op.f("uq_customers_shop_bot_id_platform"), "customers", type_="unique")
    op.create_unique_constraint(op.f("uq_customers_shop_bot_id"), "customers", ["shop_bot_id", "telegram_id"])
    op.drop_column("customers", "platform")
    op.drop_constraint(op.f("uq_shop_bots_bale_bot_id"), "shop_bots", type_="unique")
    op.drop_column("shop_bots", "bale_bot_enabled")
    op.drop_column("shop_bots", "bale_bot_username")
    op.drop_column("shop_bots", "bale_bot_id")
    op.drop_column("shop_bots", "bale_encrypted_token")
    op.drop_column("admin_settings", "bale_shop_bots_enabled")
