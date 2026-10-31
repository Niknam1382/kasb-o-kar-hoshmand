"""identity and support columns (P1-S1)

Revision ID: c1a5e0d7b3f2
Revises: b7d4e2a9c1f5
Create Date: 2026-10-23 00:00:00.000000

فازِ ۱ · P1-S1 (هویت): مودِ کسب‌وکار روی خودِ فروشگاه‌دار (A3)، یوزرنیمِ فروشگاه‌دار و نامِ‌خانوادگی/شماره‌یِ
مشتری برایِ نمایشِ هویتِ متنی (H2)، دو شناسه‌یِ پشتیبانی (D2) و تنظیماتِ پشتیبانیِ فروشگاه (D1).
همه‌ی ستون‌ها nullable‌اند یا server_default دارن؛ ردیف‌هایِ قدیمی دست‌نخورده می‌مونن.
مهاجرتِ داده: فروشگاه‌دارهایِ دارایِ ربات، مودِ فعلیِ رباتشون رو به ShopOwner.business_mode می‌گیرن.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1a5e0d7b3f2"
down_revision: Union[str, Sequence[str], None] = "b7d4e2a9c1f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- shop_owners
    op.add_column("shop_owners", sa.Column("business_mode", sa.String(length=32), nullable=False, server_default="sales"))
    op.add_column("shop_owners", sa.Column("username", sa.String(length=64), nullable=True))
    op.execute(
        "UPDATE shop_owners SET business_mode = ("
        "SELECT shop_bots.tenant_mode FROM shop_bots WHERE shop_bots.shop_owner_id = shop_owners.id) "
        "WHERE EXISTS (SELECT 1 FROM shop_bots WHERE shop_bots.shop_owner_id = shop_owners.id)"
    )

    # --- customers
    op.add_column("customers", sa.Column("last_name", sa.String(length=255), nullable=True))
    op.add_column("customers", sa.Column("phone_number", sa.String(length=20), nullable=True))
    op.add_column("customers", sa.Column("phone_via_contact", sa.Boolean(), nullable=False, server_default=sa.false()))

    # --- admin_settings (D2: پشتیبانیِ پلتفرم؛ فقط به فروشگاه‌دارها نمایش داده می‌شه)
    op.add_column("admin_settings", sa.Column("platform_support_username", sa.String(length=64), nullable=True))
    op.add_column("admin_settings", sa.Column("platform_support_phone", sa.String(length=20), nullable=True))
    op.add_column("admin_settings", sa.Column("platform_support_text", sa.Text(), nullable=True))

    # --- shop_bots (D1/D2: پشتیبانیِ فروشگاه؛ فقط به مشتری‌ها نمایش داده می‌شه)
    op.add_column("shop_bots", sa.Column("support_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("shop_bots", sa.Column("support_mode", sa.String(length=16), nullable=False, server_default="direct"))
    op.add_column("shop_bots", sa.Column("support_contact_username", sa.String(length=64), nullable=True))
    op.add_column("shop_bots", sa.Column("support_contact_phone", sa.String(length=20), nullable=True))
    op.add_column("shop_bots", sa.Column("support_contact_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("shop_bots", "support_contact_text")
    op.drop_column("shop_bots", "support_contact_phone")
    op.drop_column("shop_bots", "support_contact_username")
    op.drop_column("shop_bots", "support_mode")
    op.drop_column("shop_bots", "support_enabled")
    op.drop_column("admin_settings", "platform_support_text")
    op.drop_column("admin_settings", "platform_support_phone")
    op.drop_column("admin_settings", "platform_support_username")
    op.drop_column("customers", "phone_via_contact")
    op.drop_column("customers", "phone_number")
    op.drop_column("customers", "last_name")
    op.drop_column("shop_owners", "username")
    op.drop_column("shop_owners", "business_mode")
