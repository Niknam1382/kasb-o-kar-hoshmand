"""p49 instagram channel (switch + accounts table)

Revision ID: c9a4e6f2b813
Revises: e1c7b4a9d260
Create Date: 2026-11-08 00:00:00.000000

P49-الف — کانالِ سوم (اینستاگرام)، فقط با APIِ رسمیِ متا. افزوندیِ خالصِ خالص:

• `admin_settings.instagram_enabled` (پیش‌فرض **خاموش** ⇒ دکمه‌یِ «🟣 اینستاگرام» در پنلِ
  فروشگاه‌دار دیده نمی‌شود و هیچ رویدادی پاسخ داده نمی‌شود؛ همان الگویِ `bale_shop_bots_enabled`)
  + `instagram_app_id` + `instagram_app_secret` + `instagram_webhook_verify_token` (دو موردِ آخر
  در کد با TypeDecoratorِ رمزنگاری‌شده خوانده می‌شوند؛ نوعِ ستون‌ها همان EncryptedToken(512) و
  EncryptedText (= Text) است تا مقدارِ خام هرگز در دیتابیس ننشیند).
• جدولِ `instagram_accounts`: یکِ ردیف به‌ازایِ هر فروشگاه (کلیدِ یکتا روی shop_bot_id)، با
  `ig_account_id` ایندکس‌شده چون وب‌هوکِ متا رویداد را فقط با همان شناسه می‌فرستد و باید به
  همین فروشگاه نگاشت شود.

هیچ ستون/جدولی در upgrade حذف نمی‌شود؛ drop فقط در downgrade است (قاعدهٔ ۴).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c9a4e6f2b813"
down_revision: Union[str, Sequence[str], None] = "e1c7b4a9d260"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("admin_settings", sa.Column("instagram_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.alter_column("admin_settings", "instagram_enabled", server_default=None)
    op.add_column("admin_settings", sa.Column("instagram_app_id", sa.String(length=64), nullable=True))
    # رمزنگاری‌شده: EncryptedToken(512) ⇒ VARCHAR(512) و EncryptedText ⇒ Text (نوعِ ستون در کد).
    op.add_column("admin_settings", sa.Column("instagram_app_secret", sa.String(length=512), nullable=True))
    op.add_column("admin_settings", sa.Column("instagram_webhook_verify_token", sa.Text(), nullable=True))

    op.create_table(
        "instagram_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_bot_id", sa.Integer(), sa.ForeignKey("shop_bots.id"), nullable=False),
        sa.Column("ig_account_id", sa.String(length=64), nullable=False),
        sa.Column("ig_username", sa.String(length=64), nullable=True),
        sa.Column("page_id", sa.String(length=64), nullable=True),
        sa.Column("access_token", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("auto_reply_dm", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("greeting_text", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shop_bot_id", name=op.f("uq_instagram_accounts_shop_bot_id")),
    )
    op.alter_column("instagram_accounts", "is_active", server_default=None)
    op.alter_column("instagram_accounts", "auto_reply_dm", server_default=None)
    op.create_index(op.f("ix_instagram_accounts_shop_bot_id"), "instagram_accounts", ["shop_bot_id"], unique=False)
    op.create_index(op.f("ix_instagram_accounts_ig_account_id"), "instagram_accounts", ["ig_account_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_instagram_accounts_ig_account_id"), table_name="instagram_accounts")
    op.drop_index(op.f("ix_instagram_accounts_shop_bot_id"), table_name="instagram_accounts")
    op.drop_table("instagram_accounts")

    op.drop_column("admin_settings", "instagram_webhook_verify_token")
    op.drop_column("admin_settings", "instagram_app_secret")
    op.drop_column("admin_settings", "instagram_app_id")
    op.drop_column("admin_settings", "instagram_enabled")
