"""«🧾 مدیریتِ سفارش‌هایِ جاری» (W5): فهرستِ مرتب‌شده‌یِ گروه‌هایِ سفارشِ باز برایِ فروشگاه‌دار — تا اعلان‌هایِ سفارش
در چتِ شلوغ گم نشن. منطقِ گروه‌بندی/اولویت/صفحه‌بندی خالص است (قابلِ تستِ بدونِ DB)؛ فقط `load_current_groups` به DB می‌رسه.

«جاری» = سفارشی که هنوز به نتیجه‌یِ نهایی نرسیده و فروشگاه‌دار یا باید تصمیم بگیره/پیش ببره یا منتظرِ مشتریه
(بدونِ «منتظرِ تاییدِ مشتری» که هنوز سفارشِ واقعی نیست). فقط نوعِ ORDER (نه مشاوره)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import OrderConsultation, OrderStatus, OrderType
from app.services import order_state

PAGE_SIZE = 5
MAX_ROWS = 600

# اولویتِ نمایش (کمتر = بالاتر): اول چیزهایی که تصمیمِ فروشگاه‌دار می‌خوان، بعد پیشرفتِ سفارش، آخر منتظرِ مشتری
PRIORITY: dict[str, int] = {
    order_state.RECEIPT_SUBMITTED: 0,
    order_state.PENDING: 1,
    order_state.REFUND_PENDING: 2,
    order_state.PAID: 3,
    order_state.CONFIRMED: 3,
    order_state.PROCESSING: 4,
    order_state.SHIPPED: 5,
    order_state.AWAITING_PAYMENT: 6,
}
CURRENT_STATUSES: tuple[str, ...] = tuple(PRIORITY)
# «نیازمندِ اقدامِ فروشگاه‌دار»
NEEDS_ACTION: frozenset[str] = frozenset(
    {order_state.RECEIPT_SUBMITTED, order_state.PENDING, order_state.REFUND_PENDING, order_state.PAID, order_state.CONFIRMED}
)

FILTER_ALL = "all"
FILTER_ACTION = "act"
FILTERS = (FILTER_ALL, FILTER_ACTION)


def group_key_of(row: OrderConsultation) -> str:
    return row.cart_checkout_group_id or f"o{row.id}"


def group_status(rows: list[OrderConsultation]) -> str:
    """وضعیتِ نماینده‌یِ گروه: اگه ردیف‌ها یکی نباشن، همونی که اولویتِ بالاتر (تصمیم‌خواه‌تر) داره."""
    values = [order_state.value_of(r.status) for r in rows]
    return min(values, key=lambda v: PRIORITY.get(v, 99))


def group_rows(rows: list[OrderConsultation]) -> list[list[OrderConsultation]]:
    """ردیف‌ها (هر ترتیبی) → گروه‌ها؛ هر گروه بر اساسِ id مرتب. ترتیبِ خروجی: اولویتِ وضعیت، بعد جدیدترین."""
    buckets: dict[str, list[OrderConsultation]] = {}
    for row in rows:
        buckets.setdefault(group_key_of(row), []).append(row)
    groups = [sorted(g, key=lambda r: r.id) for g in buckets.values()]
    groups.sort(key=lambda g: (PRIORITY.get(group_status(g), 99), -max(r.id for r in g)))
    return groups


def apply_filter(groups: list[list[OrderConsultation]], flt: str) -> list[list[OrderConsultation]]:
    if flt == FILTER_ACTION:
        return [g for g in groups if group_status(g) in NEEDS_ACTION]
    return groups


def status_counts(groups: list[list[OrderConsultation]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for g in groups:
        status = group_status(g)
        counts[status] = counts.get(status, 0) + 1
    return counts


def paginate(items: list, page: int, size: int = PAGE_SIZE) -> tuple[list, int, int]:
    """(آیتم‌هایِ صفحه, شماره‌یِ صفحه‌یِ معتبر (۱-مبنا), تعدادِ کلِ صفحه‌ها). صفحه‌یِ خارج از محدوده clamp می‌شه."""
    total_pages = max(1, -(-len(items) // size))
    page = max(1, min(int(page), total_pages))
    start = (page - 1) * size
    return items[start : start + size], page, total_pages


def parse_list_callback(data: str | None) -> tuple[str, int] | None:
    """«om_l:act:2» → ('act', 2)؛ هر چیزِ نامعتبر/جعلی → None."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "om_l" or parts[1] not in FILTERS:
        return None
    raw = parts[2]
    if not (raw.isascii() and raw.isdecimal()) or len(raw) > 4:
        return None
    return parts[1], int(raw)


def is_current_group(rows: list[OrderConsultation]) -> bool:
    return bool(rows) and any(order_state.value_of(r.status) in PRIORITY for r in rows)


async def load_current_groups(session: AsyncSession, shop_bot_id: int) -> list[list[OrderConsultation]]:
    """گروه‌هایِ جاریِ همین فروشگاه (حداکثر MAX_ROWS ردیفِ تازه‌تر). گروهی که حتی یک ردیفِ جاری دارد کامل می‌آید."""
    result = await session.execute(
        select(OrderConsultation)
        .where(
            OrderConsultation.shop_bot_id == shop_bot_id,
            OrderConsultation.type == OrderType.ORDER,
            OrderConsultation.status.in_([OrderStatus(s) for s in CURRENT_STATUSES]),
        )
        .order_by(OrderConsultation.id.desc())
        .limit(MAX_ROWS)
    )
    current = list(result.scalars().all())
    group_ids = {r.cart_checkout_group_id for r in current if r.cart_checkout_group_id}
    if group_ids:  # ردیف‌هایِ هم‌گروهِ غیرجاری (مثلاً یک قلمِ ردشده) هم کنارِ گروه نشون داده می‌شن
        extra = await session.execute(
            select(OrderConsultation).where(
                OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.cart_checkout_group_id.in_(group_ids)
            )
        )
        known = {r.id for r in current}
        current += [r for r in extra.scalars().all() if r.id not in known]
    return group_rows(current)
