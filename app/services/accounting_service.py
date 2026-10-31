"""
حسابداریِ فقط‌خواندنیِ فروشگاه (فازِ ۴-ه).

⚠️ این ماژول هیچ‌چیز رو *تغییر نمی‌ده* (نه سفارش، نه تراکنشِ کیف‌پول) و هیچ جریانِ پولیِ تازه‌ای
نداره؛ فقط از داده‌یِ موجودِ سفارش‌ها گزارش می‌سازه.

تعریف‌ها (هم‌تعریف با stats_service.get_shop_daily_stats):
- «فروشِ خالص» = مجموعِ estimated_value_toman (که از اول *بعد از تخفیفه*) سفارش‌هایی که
  confirmed=True ـن و confirmed_at‌شون توی بازه‌ست — و وضعیتشون ردشده/منقضی/لغو *نیست*.
- «تخفیف» = مجموعِ discount_toman همون سفارش‌ها؛ «فروشِ ناخالص» = خالص + تخفیف.
- «میانگینِ سفارش» = خالص ÷ تعدادِ ردیف‌هایِ سفارشِ تاییدشده. (هر محصولِ یه سبد یه ردیفه؛ بندِ ۲۰.)
- پرداختِ آنلاین: سفارش‌هایی که bale_paid_at‌شون توی بازه‌ست (تعداد و جمعِ estimated_value_toman).
- وضعیت‌ها: سفارش‌هایی که created_at‌شون توی بازه‌ست، به تفکیکِ وضعیت.
- «کمپین»: فقط از روی سفارش‌هایِ *تاییدشده*؛ مصرف = تعدادِ چک‌اوت‌هایِ (cart_checkout_group_id) متمایز.

بازه‌ها بر اساسِ تقویمِ تهران (UTC+03:30، بدونِ ساعتِ تابستانی) و half-open [start, end) ـن:
امروز، ۷ روزِ اخیر (با امروز)، ۳۰ روزِ اخیر (با امروز)، و ماهِ شمسیِ جاری (بندِ ۵۶).

منطقِ خالص (بدونِ دیتابیس) جدا از بخشِ دیتابیسه تا مستقل تست بشه.
"""
from __future__ import annotations

import dataclasses
import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Campaign, OrderConsultation, OrderStatus, Product
from app.services import order_state
from app.utils.jalali import JALALI_MONTH_NAMES, TEHRAN_TZ, format_jalali_date, gregorian_to_jalali, to_tehran

# منبعِ حقیقتِ یکتا: services/order_state.py (C4)
SUCCESS_STATUS_VALUES = tuple(v for v in order_state.DISPLAY_ORDER if v in order_state.REVENUE)
RELEASED_STATUS_VALUES = tuple(v for v in order_state.DISPLAY_ORDER if v in order_state.RELEASES_RESERVATION)
# ترتیبِ نمایشِ وضعیت‌ها توی گزارش.
STATUS_ORDER = order_state.DISPLAY_ORDER

PERIOD_KEYS = ("today", "week", "month30", "jmonth")
MAX_ROWS = 20_000
TOP_PRODUCTS_LIMIT = 5
MAX_CAMPAIGN_LINES = 10
UNKNOWN_PRODUCT_NAME = "محصولِ حذف‌شده"
UNKNOWN_CAMPAIGN_NAME = "کمپینِ حذف‌شده"

_ONE_DAY = datetime.timedelta(days=1)


# =============================================================================
# منطقِ خالص (بدونِ دیتابیس)
# =============================================================================
@dataclasses.dataclass(frozen=True)
class Period:
    key: str
    label: str
    start: datetime.datetime  # UTC، شاملِ خودش
    end: datetime.datetime  # UTC، *بدونِ* خودش


@dataclasses.dataclass(frozen=True)
class OrderRow:
    """فقط ستون‌هایِ لازم برایِ حسابداری (بدونِ نام/تلفنِ مشتری و بدونِ متنِ آزادِ سفارش)."""

    id: int
    type: str
    status: str
    confirmed: bool
    created_at: datetime.datetime
    confirmed_at: datetime.datetime | None
    value_toman: int
    discount_toman: int
    product_id: int | None
    quantity: int
    campaign_id: int | None
    group_id: str | None
    bale_paid_at: datetime.datetime | None


@dataclasses.dataclass(frozen=True)
class ProductLine:
    name: str
    units: int
    net_toman: int


@dataclasses.dataclass(frozen=True)
class CampaignLine:
    name: str
    uses: int
    discount_toman: int
    net_toman: int


@dataclasses.dataclass(frozen=True)
class DayLine:
    day_label: str
    orders: int
    net_toman: int


@dataclasses.dataclass(frozen=True)
class PeriodSummary:
    period: Period
    net_toman: int
    discount_toman: int
    gross_toman: int
    successful_count: int
    average_order_toman: int
    status_counts: dict[str, int]
    online_paid_count: int
    online_paid_toman: int
    top_products: list[ProductLine]
    campaigns: list[CampaignLine]
    daily: list[DayLine]


@dataclasses.dataclass(frozen=True)
class AccountingReport:
    summary: PeriodSummary
    rows: list[OrderRow]  # سفارش‌هایِ مرتبط با بازه (ساخته‌شده/تاییدشده/پرداخت‌شده توی بازه)
    product_names: dict[int, str]
    campaign_names: dict[int, str]
    pending_total: int  # کلِ سفارش‌هایِ منتظرِ بررسی، فارغ از بازه
    truncated: bool  # تعدادِ ردیف‌ها از MAX_ROWS بیشتر بود (گزارش ناقصه)


def _status_value(status) -> str:
    return status.value if hasattr(status, "value") else str(status)


def _aware(moment: datetime.datetime | None) -> datetime.datetime | None:
    if moment is not None and moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment


def in_window(moment: datetime.datetime | None, period: Period) -> bool:
    moment = _aware(moment)
    return moment is not None and period.start <= moment < period.end


def tehran_day_start_utc(moment: datetime.datetime) -> datetime.datetime:
    """نیمه‌شبِ تهرانِ همون روزِ تهرانیِ moment، به‌صورتِ یه لحظه‌یِ UTC."""
    local = to_tehran(moment)
    start_local = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start_local.astimezone(datetime.timezone.utc)


def jalali_month_bounds(now: datetime.datetime) -> tuple[datetime.datetime, datetime.datetime, int, int]:
    """(ابتدایِ ماهِ شمسیِ جاری، ابتدایِ ماهِ بعد، سالِ شمسی، ماهِ شمسی) — مرزها نیمه‌شبِ تهران، به UTC.
    ابتدا = امروزِ تهران منهایِ (روزِ شمسی − ۱)؛ ابتدایِ ماهِ بعد = جلو می‌ره تا ماهِ شمسی عوض بشه
    (حداکثر ۳۲ قدم). نیازی به تبدیلِ شمسی→میلادی نیست (بندِ ۵۶)."""
    local = to_tehran(now)
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    today_start = tehran_day_start_utc(now)
    start = today_start - datetime.timedelta(days=jd - 1)
    end = start
    for _ in range(32):
        end += _ONE_DAY
        end_local = end.astimezone(TEHRAN_TZ)
        if gregorian_to_jalali(end_local.year, end_local.month, end_local.day)[1] != jm:
            break
    return start, end, jy, jm


def build_periods(now: datetime.datetime) -> dict[str, Period]:
    today_start = tehran_day_start_utc(now)
    tomorrow_start = today_start + _ONE_DAY
    month_start, month_end, jy, jm = jalali_month_bounds(now)
    return {
        "today": Period("today", "امروز", today_start, tomorrow_start),
        "week": Period("week", "۷ روزِ اخیر", today_start - 6 * _ONE_DAY, tomorrow_start),
        "month30": Period("month30", "۳۰ روزِ اخیر", today_start - 29 * _ONE_DAY, tomorrow_start),
        "jmonth": Period("jmonth", f"ماهِ جاری ({JALALI_MONTH_NAMES[jm - 1]} {jy})", month_start, month_end),
    }


def is_successful(row: OrderRow, period: Period) -> bool:
    return row.confirmed and row.status not in RELEASED_STATUS_VALUES and in_window(row.confirmed_at, period)


def _rounded_average(total: int, count: int) -> int:
    return (2 * total + count) // (2 * count) if count else 0


def summarize_period(
    rows: list[OrderRow],
    period: Period,
    product_names: dict[int, str],
    campaign_names: dict[int, str],
    top_products_limit: int | None = TOP_PRODUCTS_LIMIT,
    campaigns_limit: int | None = MAX_CAMPAIGN_LINES,
) -> PeriodSummary:
    success = [row for row in rows if is_successful(row, period)]
    net = sum(row.value_toman for row in success)
    discount = sum(row.discount_toman for row in success)

    counts: dict[str, int] = {}
    for row in rows:
        if in_window(row.created_at, period):
            counts[row.status] = counts.get(row.status, 0) + 1
    ordered_counts = {status: counts[status] for status in STATUS_ORDER if status in counts}
    ordered_counts.update({status: count for status, count in counts.items() if status not in ordered_counts})

    paid = [row for row in rows if in_window(row.bale_paid_at, period)]

    product_totals: dict[int, list[int]] = {}
    for row in success:
        if row.product_id is not None:
            totals = product_totals.setdefault(row.product_id, [0, 0])
            totals[0] += max(1, row.quantity)
            totals[1] += row.value_toman
    top_products = [
        ProductLine(product_names.get(pid, UNKNOWN_PRODUCT_NAME), units, value) for pid, (units, value) in product_totals.items()
    ]
    top_products.sort(key=lambda line: (-line.net_toman, -line.units, line.name))

    campaign_totals: dict[int, dict] = {}
    for row in success:
        if row.campaign_id is not None:
            entry = campaign_totals.setdefault(row.campaign_id, {"groups": set(), "discount": 0, "net": 0})
            entry["groups"].add(row.group_id or f"row:{row.id}")
            entry["discount"] += row.discount_toman
            entry["net"] += row.value_toman
    campaigns = [
        CampaignLine(campaign_names.get(cid, UNKNOWN_CAMPAIGN_NAME), len(entry["groups"]), entry["discount"], entry["net"])
        for cid, entry in campaign_totals.items()
    ]
    campaigns.sort(key=lambda line: (-line.discount_toman, -line.uses, line.name))

    daily: list[DayLine] = []
    day_start = period.start
    while day_start < period.end:
        day_end = min(day_start + _ONE_DAY, period.end)
        day_rows = [
            row for row in success if row.confirmed_at is not None and day_start <= _aware(row.confirmed_at) < day_end
        ]
        daily.append(DayLine(format_jalali_date(day_start), len(day_rows), sum(row.value_toman for row in day_rows)))
        day_start = day_end

    return PeriodSummary(
        period=period,
        net_toman=net,
        discount_toman=discount,
        gross_toman=net + discount,
        successful_count=len(success),
        average_order_toman=_rounded_average(net, len(success)),
        status_counts=ordered_counts,
        online_paid_count=len(paid),
        online_paid_toman=sum(row.value_toman for row in paid),
        top_products=top_products if top_products_limit is None else top_products[:top_products_limit],
        campaigns=campaigns if campaigns_limit is None else campaigns[:campaigns_limit],
        daily=daily,
    )


# =============================================================================
# بخشِ دیتابیس (فقط SELECT)
# =============================================================================
async def fetch_rows(
    session: AsyncSession, shop_bot_id: int, start: datetime.datetime, end: datetime.datetime, limit: int = MAX_ROWS
) -> tuple[list[OrderRow], bool]:
    """سفارش‌هایِ *همین فروشگاه* که ساخته‌شدن/تایید شدن/پرداختِ آنلاین شدنشون توی [start, end) بوده.
    خروجی: (ردیف‌ها به ترتیبِ شناسه، آیا به سقفِ limit خورد و ناقصه)."""
    columns = (
        OrderConsultation.id,
        OrderConsultation.type,
        OrderConsultation.status,
        OrderConsultation.confirmed,
        OrderConsultation.created_at,
        OrderConsultation.confirmed_at,
        OrderConsultation.estimated_value_toman,
        OrderConsultation.discount_toman,
        OrderConsultation.product_id,
        OrderConsultation.quantity,
        OrderConsultation.campaign_id,
        OrderConsultation.cart_checkout_group_id,
        OrderConsultation.bale_paid_at,
    )
    result = await session.execute(
        select(*columns)
        .where(
            OrderConsultation.shop_bot_id == shop_bot_id,
            or_(
                OrderConsultation.created_at.between(start, end - datetime.timedelta(microseconds=1)),
                OrderConsultation.confirmed_at.between(start, end - datetime.timedelta(microseconds=1)),
                OrderConsultation.bale_paid_at.between(start, end - datetime.timedelta(microseconds=1)),
            ),
        )
        .order_by(OrderConsultation.id)
        .limit(limit + 1)
    )
    fetched = result.all()
    truncated = len(fetched) > limit
    rows = [
        OrderRow(
            id=row[0],
            type=_status_value(row[1]),
            status=_status_value(row[2]),
            confirmed=bool(row[3]),
            created_at=_aware(row[4]),
            confirmed_at=_aware(row[5]),
            value_toman=int(row[6] or 0),
            discount_toman=int(row[7] or 0),
            product_id=row[8],
            quantity=int(row[9] or 1),
            campaign_id=row[10],
            group_id=row[11],
            bale_paid_at=_aware(row[12]),
        )
        for row in fetched[:limit]
    ]
    return rows, truncated


async def count_pending_total(session: AsyncSession, shop_bot_id: int) -> int:
    result = await session.execute(
        select(func.count())
        .select_from(OrderConsultation)
        .where(OrderConsultation.shop_bot_id == shop_bot_id, OrderConsultation.status == OrderStatus.PENDING)
    )
    return int(result.scalar_one())


async def _load_names(session: AsyncSession, shop_bot_id: int, rows: list[OrderRow]) -> tuple[dict[int, str], dict[int, str]]:
    product_ids = {row.product_id for row in rows if row.product_id is not None}
    campaign_ids = {row.campaign_id for row in rows if row.campaign_id is not None}
    product_names: dict[int, str] = {}
    campaign_names: dict[int, str] = {}
    if product_ids:
        result = await session.execute(
            select(Product.id, Product.name).where(Product.shop_bot_id == shop_bot_id, Product.id.in_(product_ids))
        )
        product_names = {pid: name for pid, name in result.all()}
    if campaign_ids:
        result = await session.execute(
            select(Campaign.id, Campaign.name).where(Campaign.shop_bot_id == shop_bot_id, Campaign.id.in_(campaign_ids))
        )
        campaign_names = {cid: name for cid, name in result.all()}
    return product_names, campaign_names


async def build_report(
    session: AsyncSession, shop_bot_id: int, period_key: str = "today", now: datetime.datetime | None = None
) -> AccountingReport:
    """گزارشِ یه بازه. period_key نامعتبر → امروز. now فقط برایِ تست قابلِ تزریقه."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    periods = build_periods(now)
    period = periods.get(period_key) or periods["today"]
    rows, truncated = await fetch_rows(session, shop_bot_id, period.start, period.end)
    product_names, campaign_names = await _load_names(session, shop_bot_id, rows)
    summary = summarize_period(rows, period, product_names, campaign_names)
    pending_total = await count_pending_total(session, shop_bot_id)
    return AccountingReport(
        summary=summary,
        rows=rows,
        product_names=product_names,
        campaign_names=campaign_names,
        pending_total=pending_total,
        truncated=truncated,
    )
