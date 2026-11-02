"""P22: ردگیریِ «آخرین دیدارِ» فروشگاه‌دار و وضعیتِ حذفِ حساب

Revision ID: d7a2c5b8e1f3
Revises: c9f4a7e2b5d8
Create Date: 2026-11-02 02:40:00.000000

سه ستونِ افزودنی رویِ `shop_owners` (هیچ ستونی حذف نمی‌شود):

- `last_seen_at`: آخرین باری که فروشگاه‌دار با رباتِ اصلی کار کرده. هر پیام/دکمه این را
  عوض می‌کند، ولی نوشتنِ آن در میانه‌بند (تِروتل) است تا به‌ازایِ هر کلیک یک UPDATE رویِ
  جدولِ اصلیِ فروشگاه‌دارها نرویم. بدونِ این ستون «چه کسی یک ماه است سراغِ ربات نیامده»
  قابلِ پاسخ دادن نبود.
- `is_deleted` + `deleted_at`: حذفِ نرم. حسابِ پاک‌شده (با تمامِ سفارش‌ها و دفترِ مالیِ آن)
  نباید از دیتابیس برود تا زنجیرهٔ ممیزی، کمیسیون‌هایِ وصول‌نشده و تاریخچهٔ پرداخت بسوزد؛
  عوضش از فهرست‌ها، آمار و ورودِ کاربر بیرون می‌ماند و `deleted_at` زمانِ تصمیم را نگه می‌دارد.

پُرکردنِ اولیه (backfill): برایِ فروشگاه‌دارهایِ موجود، `last_seen_at` از آخرینِ رویدادِ
واقعی‌شان (تراکنشِ کیف‌پول / پیامِ مشتریِ فروشگاه / سفارش) ساخته می‌شود؛ جایی که هیچ
رویدادی نیست NULL می‌ماند و در پنل «بدونِ سابقه» نشان داده می‌شود — نه «غیرفعال»، چون
نبودِ داده نباید حکمِ حذف بگیرد.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d7a2c5b8e1f3"
down_revision: Union[str, Sequence[str], None] = "c9f4a7e2b5d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL = """
UPDATE shop_owners o
SET last_seen_at = src.last_seen
FROM (
    SELECT owner_id, MAX(at) AS last_seen
    FROM (
        SELECT w.shop_owner_id AS owner_id, w.created_at AS at
        FROM wallet_transactions w
        UNION ALL
        SELECT b.shop_owner_id, c.last_message_at
        FROM shop_bots b JOIN customers c ON c.shop_bot_id = b.id
        UNION ALL
        SELECT b.shop_owner_id, s.created_at
        FROM shop_bots b JOIN orders_consultations s ON s.shop_bot_id = b.id
    ) events
    WHERE at IS NOT NULL
    GROUP BY owner_id
) src
WHERE o.id = src.owner_id AND o.last_seen_at IS NULL
"""


def upgrade() -> None:
    op.add_column("shop_owners", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("shop_owners", sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("shop_owners", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_shop_owners_last_seen_at", "shop_owners", ["last_seen_at"])
    op.create_index("ix_shop_owners_is_deleted", "shop_owners", ["is_deleted"])
    op.execute(sa.text(_BACKFILL))


def downgrade() -> None:
    op.drop_index("ix_shop_owners_is_deleted", table_name="shop_owners")
    op.drop_index("ix_shop_owners_last_seen_at", table_name="shop_owners")
    op.drop_column("shop_owners", "deleted_at")
    op.drop_column("shop_owners", "is_deleted")
    op.drop_column("shop_owners", "last_seen_at")
