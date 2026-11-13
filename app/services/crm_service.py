"""
CRMِ فروشگاه‌دار (فازِ ۴-ج): بخش‌بندیِ مشتری‌ها با قاعده (بدونِ هزینه‌یِ AI)، یادداشت و برچسب، کارتِ مشتری.

بخش‌بندی یه *افرازه*: هر مشتری دقیقاً توی یه بخشه (پس جمعِ شمارشِ بخش‌ها = تعدادِ کلِ مشتری‌ها).
محاسبه موقعِ درخواست با یه کوئریِ تجمیعی انجام می‌شه (ستونِ ذخیره‌شده‌ای نیست که کهنه بشه).

تعریف‌ها:
- «سفارشِ موفق» = وضعیتِ CONFIRMED / PROCESSING / SHIPPED / COMPLETED. (ردشده/منقضی/لغو/در انتظار
  *موفق نیستن*.)
- «فعالیت» = دیرتریِن زمانِ بینِ آخرین پیامِ مشتری و آخرین سفارشِ ثبت‌شده (با هر وضعیتی).
- loyal    وفادار      : ≥ LOYAL_MIN_ORDERS سفارشِ موفق و فعالیت ≤ ACTIVITY_WINDOW_DAYS روز پیش
- active   فعال        : ۱ تا (LOYAL_MIN_ORDERS−۱) سفارشِ موفق و فعالیت ≤ ACTIVITY_WINDOW_DAYS روز پیش
- churning در حالِ ریزش: ≥۱ سفارشِ موفق و فعالیت > ACTIVITY_WINDOW_DAYS روز پیش (شاملِ وفادارهایِ خوابیده)
- new      جدید        : بدونِ سفارشِ موفق و اولین حضور ≤ NEW_WINDOW_DAYS روز پیش
- no_purchase بدونِ خرید: بدونِ سفارشِ موفق و اولین حضور > NEW_WINDOW_DAYS روز پیش
(مرزها «کمتر یا مساوی»ـن: دقیقاً ۴۵ روز هنوز فعاله، ۴۵ روز و یک ثانیه ریزشه.)

یادداشت و برچسب فقط برایِ خودِ فروشگاه‌داره و هیچ‌وقت به پرامپتِ رباتِ مشتری داده نمی‌شه.

منطقِ خالص (بدونِ دیتابیس) جدا از بخشِ دیتابیسه تا مستقل تست بشه.
"""
from __future__ import annotations

import dataclasses
import datetime
import re

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Customer, OrderConsultation, OrderStatus, Product

SEGMENT_LOYAL = "loyal"
SEGMENT_ACTIVE = "active"
SEGMENT_NEW = "new"
SEGMENT_CHURNING = "churning"
SEGMENT_NO_PURCHASE = "no_purchase"
SEGMENT_KEYS = (SEGMENT_LOYAL, SEGMENT_ACTIVE, SEGMENT_NEW, SEGMENT_CHURNING, SEGMENT_NO_PURCHASE)

LOYAL_MIN_ORDERS = 3
ACTIVITY_WINDOW_DAYS = 45
NEW_WINDOW_DAYS = 7

SUCCESS_STATUSES = (
    OrderStatus.CONFIRMED,
    OrderStatus.PAID,
    OrderStatus.PROCESSING,
    OrderStatus.SHIPPED,
    OrderStatus.COMPLETED,
)
# ستونِ status توی دیتابیس یه String(32) ساده‌ست (نه Enum)؛ مثلِ campaign_service رشته‌ها رو به in_ می‌دیم.
SUCCESS_STATUS_VALUES = [status.value for status in SUCCESS_STATUSES]

NOTES_MAX_LEN = 1000
TAGS_MAX_COUNT = 5
TAG_MAX_LEN = 20
PAGE_SIZE = 8
MAX_CUSTOMERS_SCANNED = 50_000
RECENT_ORDERS_LIMIT = 5

_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CHAR_TABLE = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ـ": None})
_TAG_SPLIT_RE = re.compile(r"[,\u060c;\u061b\n]+")
_SPACES_RE = re.compile(r"\s+")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class CrmError(ValueError):
    """خطایِ اعتبارسنجی؛ code یه شناسه‌یِ ماشینیه: note_too_long، tag_too_long، too_many_tags، not_found."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


# =============================================================================
# منطقِ خالص (بدونِ دیتابیس)
# =============================================================================
def _aware(moment: datetime.datetime | None) -> datetime.datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment


def latest_activity(last_message_at: datetime.datetime | None, last_order_at: datetime.datetime | None) -> datetime.datetime | None:
    candidates = [moment for moment in (_aware(last_message_at), _aware(last_order_at)) if moment is not None]
    return max(candidates) if candidates else None


def classify(
    successful_orders: int,
    last_activity: datetime.datetime | None,
    first_seen_at: datetime.datetime | None,
    now: datetime.datetime,
) -> str:
    """تابعِ خالصِ طبقه‌بندی؛ دقیقاً یکی از SEGMENT_KEYS رو برمی‌گردونه."""
    now = _aware(now)
    last_activity = _aware(last_activity)
    first_seen_at = _aware(first_seen_at)
    if successful_orders >= 1:
        recent = last_activity is not None and (now - last_activity) <= datetime.timedelta(days=ACTIVITY_WINDOW_DAYS)
        if not recent:
            return SEGMENT_CHURNING
        return SEGMENT_LOYAL if successful_orders >= LOYAL_MIN_ORDERS else SEGMENT_ACTIVE
    if first_seen_at is not None and (now - first_seen_at) <= datetime.timedelta(days=NEW_WINDOW_DAYS):
        return SEGMENT_NEW
    return SEGMENT_NO_PURCHASE


@dataclasses.dataclass(frozen=True)
class CustomerStat:
    customer_id: int
    telegram_id: int
    first_name: str | None
    username: str | None
    first_seen_at: datetime.datetime | None
    last_message_at: datetime.datetime | None
    success_count: int
    net_toman: int
    last_order_at: datetime.datetime | None
    last_activity: datetime.datetime | None
    segment: str


def make_stat(
    customer_id: int,
    telegram_id: int,
    first_name: str | None,
    username: str | None,
    first_seen_at: datetime.datetime | None,
    last_message_at: datetime.datetime | None,
    success_count: int,
    net_toman: int,
    last_order_at: datetime.datetime | None,
    now: datetime.datetime,
) -> CustomerStat:
    activity = latest_activity(last_message_at, last_order_at)
    return CustomerStat(
        customer_id=customer_id,
        telegram_id=telegram_id,
        first_name=first_name,
        username=username,
        first_seen_at=_aware(first_seen_at),
        last_message_at=_aware(last_message_at),
        success_count=int(success_count or 0),
        net_toman=int(net_toman or 0),
        last_order_at=_aware(last_order_at),
        last_activity=activity,
        segment=classify(int(success_count or 0), activity, first_seen_at, now),
    )


_EPOCH = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)


def partition(stats: list[CustomerStat]) -> dict[str, list[CustomerStat]]:
    """هر مشتری دقیقاً توی یه بخش؛ داخلِ هر بخش به ترتیبِ آخرین فعالیت (تازه‌تر اول) و بعد شناسه."""
    buckets: dict[str, list[CustomerStat]] = {key: [] for key in SEGMENT_KEYS}
    for stat in stats:
        buckets[stat.segment].append(stat)
    for members in buckets.values():
        members.sort(key=lambda stat: (-(stat.last_activity or _EPOCH).timestamp(), stat.customer_id))
    return buckets


def segment_counts(stats: list[CustomerStat]) -> dict[str, int]:
    counts = {key: 0 for key in SEGMENT_KEYS}
    for stat in stats:
        counts[stat.segment] += 1
    return counts


def paginate(members: list[CustomerStat], page: int, page_size: int = PAGE_SIZE) -> tuple[list[CustomerStat], int, int]:
    """(ردیف‌هایِ صفحه، صفحه‌یِ واقعی بعد از clamp، تعدادِ کلِ صفحه‌ها)."""
    total_pages = max(1, (len(members) + page_size - 1) // page_size)
    page = min(max(0, page), total_pages - 1)
    return members[page * page_size : (page + 1) * page_size], page, total_pages


def validate_note(raw: str | None) -> str | None:
    """یادداشتِ آزاد: کاراکترهایِ کنترلی حذف، فاصله‌هایِ ابتدا/انتها بریده، خطِ جدید حفظ می‌شه.
    خالی → None (پاک‌کردن). بلندتر از NOTES_MAX_LEN → CrmError('note_too_long') (بریده نمی‌شه تا
    فروشگاه‌دار بی‌صدا چیزی از دست نده)."""
    cleaned = _CONTROL_RE.sub("", raw or "").strip()
    if not cleaned:
        return None
    if len(cleaned) > NOTES_MAX_LEN:
        raise CrmError("note_too_long")
    return cleaned


def normalize_tag(raw: str | None) -> str:
    folded = (raw or "").translate(_DIGIT_TABLE).translate(_CHAR_TABLE).casefold()
    folded = _CONTROL_RE.sub("", folded).strip().lstrip("#").strip()
    return _SPACES_RE.sub(" ", folded)


def parse_tags(raw: str | None) -> list[str]:
    """«vip, پرمصرف، #تهران» → ['vip', 'پرمصرف', 'تهران']. جداکننده‌ها: «,» «،» «;» «؛» و خطِ جدید.
    تکراری‌ها (بعد از نرمال‌سازی) یکی می‌شن؛ خالی‌ها رد. بیش از TAGS_MAX_COUNT برچسب یا برچسبِ
    بلندتر از TAG_MAX_LEN → خطا (بریده نمی‌شه)."""
    tags: list[str] = []
    for part in _TAG_SPLIT_RE.split(raw or ""):
        tag = normalize_tag(part)
        if not tag:
            continue
        if len(tag) > TAG_MAX_LEN:
            raise CrmError("tag_too_long")
        if tag not in tags:
            tags.append(tag)
    if len(tags) > TAGS_MAX_COUNT:
        raise CrmError("too_many_tags")
    return tags


def split_stored_tags(stored: str | None) -> list[str]:
    return [tag for tag in (stored or "").split(",") if tag]


# =============================================================================
# بخشِ دیتابیس (کوئریِ تجمیعی؛ فقط SELECT مگر set_notes/set_tags)
# =============================================================================
def _stats_query(shop_bot_id: int, *, exclude_blocked: bool = False):
    orders_agg = (
        select(
            OrderConsultation.customer_id.label("customer_id"),
            func.sum(case((OrderConsultation.status.in_(SUCCESS_STATUS_VALUES), 1), else_=0)).label("success_count"),
            func.sum(
                case(
                    (OrderConsultation.status.in_(SUCCESS_STATUS_VALUES), func.coalesce(OrderConsultation.estimated_value_toman, 0)),
                    else_=0,
                )
            ).label("net_toman"),
            func.max(OrderConsultation.created_at).label("last_order_at"),
        )
        .where(OrderConsultation.shop_bot_id == shop_bot_id)
        .group_by(OrderConsultation.customer_id)
        .subquery()
    )
    query = (
        select(
            Customer.id,
            Customer.telegram_id,
            Customer.first_name,
            Customer.username,
            Customer.first_seen_at,
            Customer.last_message_at,
            orders_agg.c.success_count,
            orders_agg.c.net_toman,
            orders_agg.c.last_order_at,
        )
        .outerjoin(orders_agg, orders_agg.c.customer_id == Customer.id)
        .where(Customer.shop_bot_id == shop_bot_id)
    )
    if exclude_blocked:
        # پ۶۶: «پیام به بخش» هرگز به مخاطبِ بلاک‌شده نمی‌رود؛ فهرستِ CRM و کارتِ مشتری برعکس،
        # بلاک‌شده‌ها را هم نشان می‌دهند (وگرنه فروشگاه‌دار فراموش می‌کند بلاکش کرده است).
        query = query.where(Customer.is_blocked.is_(False))
    return query


async def load_stats(
    session: AsyncSession,
    shop_bot_id: int,
    now: datetime.datetime | None = None,
    customer_id: int | None = None,
    *,
    exclude_blocked: bool = False,
) -> tuple[list[CustomerStat], bool]:
    """آمارِ مشتری‌هایِ *همین فروشگاه* (یا فقط یه مشتری). خروجی: (آمارها، آیا به سقفِ اسکن خورد).

    `exclude_blocked=True` (پ۶۶) مخاطبِ بلاک‌شده را از شمارش بیرون می‌گذارد؛ فقط برایِ «پیام به
    بخش» استفاده می‌شود، نه فهرستِ CRM.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    query = _stats_query(shop_bot_id, exclude_blocked=exclude_blocked)
    if customer_id is not None:
        query = query.where(Customer.id == customer_id)
    result = await session.execute(query.order_by(Customer.id).limit(MAX_CUSTOMERS_SCANNED + 1))
    fetched = result.all()
    truncated = len(fetched) > MAX_CUSTOMERS_SCANNED
    stats = [make_stat(*row, now=now) for row in fetched[:MAX_CUSTOMERS_SCANNED]]
    return stats, truncated


async def search_customers(
    session: AsyncSession,
    shop_bot_id: int,
    term: str,
    *,
    page: int = 0,
    page_size: int = PAGE_SIZE,
) -> tuple[list[Customer], int]:
    """پ۵۶ · موردِ ۴۱: جست‌وجویِ مشتری‌هایِ *همین فروشگاه* با نام/نام‌کاربری/تلفن/شناسهٔ تلگرام.

    `shop_bot_id` همیشه در WHERE می‌ماند، پس جست‌وجو هیچ‌وقت از فروشگاهِ صاحبِ حساب بیرون
    نمی‌زند. عبارتِ خالی یا بی‌نتیجه ⇒ فهرستِ خالی و شمارِ صفر (نه «همه»). ترتیبِ نمایش مثلِ
    کارتِ مشتری است: تازه‌ترین فعالیت، بعد شناسه. صفحه‌بندی با LIMIT/OFFSET و یکِ شمارِ جدا.
    """
    if type(page) is not int or page < 0:
        raise ValueError("شمارهٔ صفحه معتبر نیست")
    if type(page_size) is not int or not 1 <= page_size <= 50:
        raise ValueError("اندازهٔ صفحه معتبر نیست")
    from app.services import search_service

    conditions = [Customer.shop_bot_id == shop_bot_id, *search_service.filter_conditions(
        term,
        name_columns=(Customer.first_name, Customer.last_name),
        username_column=Customer.username,
        phone_column=Customer.phone_number,
        telegram_column=Customer.telegram_id,
    )]
    total = int((await session.execute(select(func.count()).select_from(Customer).where(*conditions))).scalar_one() or 0)
    rows = await session.execute(
        select(Customer)
        .where(*conditions)
        .order_by(func.coalesce(Customer.last_message_at, Customer.first_seen_at).desc(), Customer.id.desc())
        .limit(page_size)
        .offset(page * page_size)
    )
    return list(rows.scalars().all()), total


async def get_owned_customer(session: AsyncSession, customer_id: int | None, shop_bot_id: int) -> Customer | None:
    """customer_id از callback_data میاد (قابلِ دستکاری) → مالکیت همیشه چک می‌شه."""
    if customer_id is None:
        return None
    result = await session.execute(select(Customer).where(Customer.id == customer_id, Customer.shop_bot_id == shop_bot_id))
    return result.scalar_one_or_none()


@dataclasses.dataclass(frozen=True)
class OrderBrief:
    status: str
    type: str
    product_name: str | None
    quantity: int | None
    value_toman: int
    discount_toman: int
    created_at: datetime.datetime


async def recent_orders(session: AsyncSession, shop_bot_id: int, customer_id: int, limit: int = RECENT_ORDERS_LIMIT) -> list[OrderBrief]:
    result = await session.execute(
        select(
            OrderConsultation.status,
            OrderConsultation.type,
            Product.name,
            OrderConsultation.quantity,
            OrderConsultation.estimated_value_toman,
            OrderConsultation.discount_toman,
            OrderConsultation.created_at,
        )
        .outerjoin(Product, OrderConsultation.product_id == Product.id)
        .where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.customer_id == customer_id)
        .order_by(OrderConsultation.id.desc())
        .limit(limit)
    )
    return [
        OrderBrief(
            status=status.value if hasattr(status, "value") else str(status),
            type=order_type.value if hasattr(order_type, "value") else str(order_type),
            product_name=product_name,
            quantity=quantity,
            value_toman=int(value or 0),
            discount_toman=int(discount or 0),
            created_at=created_at,
        )
        for status, order_type, product_name, quantity, value, discount, created_at in result.all()
    ]


async def set_notes(session: AsyncSession, customer: Customer, raw: str | None) -> str | None:
    note = validate_note(raw)
    customer.crm_notes = note
    await session.flush()
    return note


async def set_tags(session: AsyncSession, customer: Customer, raw: str | None) -> list[str]:
    tags = parse_tags(raw)
    customer.crm_tags = ",".join(tags) if tags else None
    await session.flush()
    return tags


async def set_blocked(session: AsyncSession, customer: Customer, blocked: bool) -> bool:
    """B4: بلاک/رفعِ بلاک. وضعیتِ مقصد صریح پاس داده می‌شود (نه تلگلِ کور) ⇒ دابل‌تپ بی‌اثر است."""
    customer.is_blocked = bool(blocked)
    await session.flush()
    return customer.is_blocked
