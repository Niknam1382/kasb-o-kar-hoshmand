"""P21 pricing: voice per minute, receipt per token, commission receivables

Revision ID: a7d2e5f9c3b6
Revises: f6c1d4e8b2a5
Create Date: 2026-11-01 17:40:00.000000

سه افزودنی، هیچ حذف/تغییری:

1. `admin_settings.wallet_cost_voice_per_minute_toman` (پیش‌فرض ۰ ⇒ خاموش) — قیمتِ ثابتِ
   «هر صوت ۳۰۰ تومان» باعث می‌شد ویسِ ۶۰ ثانیه‌ای ~۱۰ برابر زیرِ هزینهٔ تمام‌شده حساب شود.
   با این ستون، هزینه `max(کفِ فعلی, دقیقه_گردِبالا × نرخ)` می‌شود ⇒ هیچ‌کس ارزان‌تر از
   امروز پرداخت نمی‌کند، ولی ویسِ بلند درست قیمت‌گذاری می‌شود.
2. `admin_settings.wallet_cost_receipt_per_1k_tokens` (پیش‌فرض ۰ ⇒ همان نرخِ ثابت) — تحلیلِ
   رسید هم توکن‌محور می‌شود، همان‌طور که چتِ معمولی توکن‌محور است.
3. جدولِ `commission_receivables` — امروز اگر فروشگاه اعتبار نداشته باشد، تسویهٔ کمیسیون
   رد می‌شود و **هیچ بدهی‌ای ثبت نمی‌شود**؛ پلتفرم درآمدِ از‌دست‌رفته را هرگز نمی‌بیند.
   همه‌یِ ستون‌ها برایِ ردیف‌هایِ موجود بی‌معنی‌اند (جدول تازه) ⇒ هیچ داده‌ای دست‌نخورده.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7d2e5f9c3b6"
down_revision: Union[str, Sequence[str], None] = "f6c1d4e8b2a5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "admin_settings",
        sa.Column("wallet_cost_voice_per_minute_toman", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "admin_settings",
        sa.Column("wallet_cost_receipt_per_1k_tokens", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "commission_receivables",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_owner_id", sa.Integer(), nullable=False),
        sa.Column("group_key", sa.String(length=64), nullable=False),
        sa.Column("amount_toman", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=12), server_default="open", nullable=False),
        sa.Column("note", sa.String(length=180), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("settled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["shop_owner_id"], ["shop_owners.id"], name=op.f("fk_commission_receivables_shop_owner_id_shop_owners")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_commission_receivables")),
        sa.UniqueConstraint("group_key", "shop_owner_id", name="uq_commission_receivables_group_owner"),
    )
    op.create_index(op.f("ix_commission_receivables_shop_owner_id"), "commission_receivables", ["shop_owner_id"], unique=False)
    op.create_index(op.f("ix_commission_receivables_status"), "commission_receivables", ["status"], unique=False)


def downgrade() -> None:
    op.drop_table("commission_receivables")
    op.drop_column("admin_settings", "wallet_cost_receipt_per_1k_tokens")
    op.drop_column("admin_settings", "wallet_cost_voice_per_minute_toman")
