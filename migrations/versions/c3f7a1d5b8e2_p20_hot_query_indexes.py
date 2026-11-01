"""P20 performance: composite indexes for the hottest queries

Revision ID: c3f7a1d5b8e2
Revises: b2e6f9c1d4a8
Create Date: 2026-11-01 13:20:00.000000

پنج ایندکسِ مرکب برایِ کوئری‌هایی که در *هر پیامِ مشتری* یا *هر وب‌هوکِ پرداخت* اجرا می‌شوند.
قبلاً فقط ستونِ تک‌مقداری ایندکس داشت ⇒ Postگرس ردیف‌هایِ همانِ فروشگاه را بیرون می‌کشید و بعد
مرتب/فیلتر می‌کرد (با رشدِ جدول، همان کوئری خطی می‌شود):

* `conversation_messages(customer_id, created_at)` — حافظه‌یِ مکالمه؛ «تازه‌ترین N پیام»
  حالا در همان ایندکس read می‌شود (بدونِ sort). داغ‌ترینِ کوئریِ کلِ برنامه.
* `wallet_charges(shop_owner_id, expires_at) WHERE NOT is_expired AND remaining_toman > 0`
  — کسرِ FIFO; با ایندکسِ *جزئی* فقط بسته‌هایِ زنده داخلش‌اند ⇒ کوچک و دقیق.
* `orders_consultations(shop_bot_id, status, created_at)` — فهرست/پنلِ سفارش‌هایِ ادمین و
  جابِ انقضا (هر دو «سفارش‌هایِ همین فروشگاه با این وضعیت، تازه‌ترین اول»).
* `payments(status, reserved_until) WHERE status = 'pending'` — صفِ تاییدِ ادمین + انقضایِ
  پرداختِ رهاشده؛ فقط ردیف‌هایِ باز ایندکس می‌شوند (با رشدِ تاریخچه، ایندکس درشت نمی‌شود).
* `products(shop_bot_id, is_active)` — فهرستِ محصولاتِ مشتری و پرامپتِ AI در هر پیام.

نکتهٔ استقرار: ایندکس معمولی (نه CONCURRENTLY) چون مایگریشن داخلِ یک تراکنش اجرا می‌شود؛
برایِ دیتابیسِ زندهٔ بزرگ، CREATE INDEX CONCURRENTLY را جدا و بیرونِ مایگریشن اجرا کن.
هیچ داده‌ای تغییر نمی‌کند و هیچ ایندکسی حذف نمی‌شود.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c3f7a1d5b8e2"
down_revision: Union[str, Sequence[str], None] = "b2e6f9c1d4a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_INDEXES = (
    ("ix_conversation_messages_customer_created", "conversation_messages", ["customer_id", "created_at"], None),
    (
        "ix_wallet_charges_owner_live_expires",
        "wallet_charges",
        ["shop_owner_id", "expires_at"],
        "is_expired = false AND remaining_toman > 0",
    ),
    ("ix_orders_consultations_shop_status_created", "orders_consultations", ["shop_bot_id", "status", "created_at"], None),
    ("ix_payments_pending_reserved", "payments", ["status", "reserved_until"], "status = 'pending'"),
    ("ix_products_shop_active", "products", ["shop_bot_id", "is_active"], None),
)


def upgrade() -> None:
    for name, table, columns, where in NEW_INDEXES:
        op.create_index(name, table, columns, unique=False, postgresql_where=sa.text(where) if where else None)


def downgrade() -> None:
    for name, table, _columns, _where in reversed(NEW_INDEXES):
        op.drop_index(name, table_name=table)
