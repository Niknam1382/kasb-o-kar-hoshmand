"""پ۵۵ · موردِ ۲۳: مصرفِ هوشِ مصنوعی به‌ازایِ هر کاربر + سه اهرمِ مدیریتی.

چرا این فایل جدا است: تا پیشِ این، هیچ کسرِ اعتباری نمی‌توانست بگوید «این پول را کدامِ
مشتری خرج کرده است» — دفترِ کیف‌پول فقط `shop_owner_id` داشت. از همینِ نسخه، همان ردیفِ
کسرِ موجودی `customer_id` هم می‌گیرد (بدونِ هیچ جملهٔ اضافه، چون رویِ همان INSERT نوشته
می‌شود) و این سرویس همین ستون را می‌شمارد.

صراحتِ لازم: ردیف‌هایِ قدیمی `customer_id = NULL` می‌مانند و مسیرهایی که مشتریِ شناخته‌شده
ندارند (کامنتِ اینستاگرام، خلاصهٔ CRMِ خودِ فروشگاه‌دار، دستیارِ مدیریتی) هم NULL می‌مانند.
پس رتبه‌بندی، مصرفِ *این نسخه به بعد* را نشان می‌دهد، نه گذشته را حدس نمی‌زند.

دربارهٔ هزینهٔ مسیرِ پیام: `block_reason` وقتی هیچ‌کدام از دو ستون تنظیم نشده باشد هیچ
کوئری‌ای نمی‌زند (هر دو رویِ ردیفِ مشتریِ خوانده‌شده‌اند). سقفِ روزانه فقط وقتی عدد دارد یکِ
`SUM` محدود رویِ شاخهٔ `(customer_id, created_at)` می‌زند؛ بنابراین مسیرِ پیامِ مشتریانِ
معمولی دقیقاً همان تعدادِ جمله‌هایِ قبل را می‌زند (سقفِ `MAX_STATEMENTS_PER_MESSAGE` دست‌نخورده).
"""

from __future__ import annotations

import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Customer, WalletTransaction

RANK_PAGE_SIZE = 10
RANK_MAX_PAGE_SIZE = 50
PAUSE_WINDOW_HOURS = 24

REASON_PAUSED = "paused"
REASON_DAILY_LIMIT = "daily_limit"


def _aware(moment: datetime.datetime) -> datetime.datetime:
    if moment.tzinfo is None:
        return moment.replace(tzinfo=datetime.timezone.utc)
    return moment.astimezone(datetime.timezone.utc)


async def rank_page(
    session: AsyncSession,
    *,
    since: datetime.datetime,
    until: datetime.datetime,
    page: int = 0,
    page_size: int = RANK_PAGE_SIZE,
) -> tuple[list[tuple[int, int, int]], int]:
    """ده ردیفِ پرمصرف‌ترینِ کاربر در بازه: `(customer_id, مصرف_به_تومان, تعداد_کسر)` + شمارِ کلِ کاربران.

    پنجره `[since, until)` است (همان قاعدهٔ پ۵۲). فقط ردیف‌هایِ کسرِ منفی و دارایِ مشتری
    شمرده می‌شوند ⇒ برگشتِ اعتبار و ردیف‌هایِ بی‌صاحبِ گذشته در رتبه نمی‌آیند.
    """
    if type(page) is not int or page < 0:
        raise ValueError("شمارهٔ صفحه معتبر نیست")
    if type(page_size) is not int or not 1 <= page_size <= RANK_MAX_PAGE_SIZE:
        raise ValueError("اندازهٔ صفحه معتبر نیست")
    conditions = [
        WalletTransaction.customer_id.is_not(None),
        WalletTransaction.amount_toman < 0,
        WalletTransaction.created_at >= since,
        WalletTransaction.created_at < until,
    ]
    spent = func.coalesce(func.sum(-WalletTransaction.amount_toman), 0)
    total = int(
        (
            await session.execute(
                select(func.count(func.distinct(WalletTransaction.customer_id))).where(*conditions)
            )
        ).scalar_one()
        or 0
    )
    rows = await session.execute(
        select(WalletTransaction.customer_id, spent, func.count())
        .where(*conditions)
        .group_by(WalletTransaction.customer_id)
        .order_by(spent.desc(), WalletTransaction.customer_id.asc())
        .limit(page_size)
        .offset(page * page_size)
    )
    ranked = [(int(customer_id), int(amount), int(count)) for customer_id, amount, count in rows.all()]
    return ranked, total


async def spend_since(session: AsyncSession, customer_id: int, since: datetime.datetime) -> int:
    """جمعِ مصرفِ این کاربر از `since` تا اکنون (تومان، بدونِ احتسابِ برگشت‌ها)."""
    value = (
        await session.execute(
            select(func.coalesce(func.sum(-WalletTransaction.amount_toman), 0)).where(
                WalletTransaction.customer_id == customer_id,
                WalletTransaction.amount_toman < 0,
                WalletTransaction.created_at >= since,
            )
        )
    ).scalar_one()
    return int(value or 0)


async def spend_and_calls(
    session: AsyncSession, customer_id: int, since: datetime.datetime, until: datetime.datetime
) -> tuple[int, int]:
    """مصرف و تعدادِ کسرِ یکِ کاربر در پنجرهٔ `[since, until)` — برایِ کارتِ جزئیات."""
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(-WalletTransaction.amount_toman), 0),
                func.count(),
            ).where(
                WalletTransaction.customer_id == customer_id,
                WalletTransaction.amount_toman < 0,
                WalletTransaction.created_at >= since,
                WalletTransaction.created_at < until,
            )
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)


async def block_reason(
    session: AsyncSession, customer: Customer | None, *, now: datetime.datetime | None = None
) -> str | None:
    """دلیلِ توقفِ پاسخِ خودکار برایِ این کاربر، یا None اگر آزاد است.

    ترتیبِ چک عمدی است: اولِ توقف (رایگان، چون رویِ همان ردیفِ خوانده‌شده است) و بعدِ سقفِ
    روزانه (که فقط با عددِ تنظیم‌شده یکِ کوئری می‌زند).
    """
    if customer is None:
        return None
    moment = _aware(now or datetime.datetime.now(datetime.timezone.utc))
    paused_until = customer.ai_paused_until
    if paused_until is not None and _aware(paused_until) > moment:
        return REASON_PAUSED
    limit = customer.ai_daily_limit_toman
    if limit is None or limit <= 0:
        return None
    spent = await spend_since(session, customer.id, moment - datetime.timedelta(hours=PAUSE_WINDOW_HOURS))
    return REASON_DAILY_LIMIT if spent >= limit else None


async def set_daily_limit(session: AsyncSession, customer: Customer, amount_toman: int | None) -> int | None:
    """سقفِ مصرف در ۲۴ ساعتِ گذشته؛ `None` یعنی بازگشت به «بدونِ سقف» (همان حالتِ امروز)."""
    if amount_toman is not None and (type(amount_toman) is not int or amount_toman <= 0):
        raise ValueError("سقف باید عددِ مثبتِ تومان باشد")
    customer.ai_daily_limit_toman = amount_toman
    await session.flush()
    return amount_toman


async def set_paused(session: AsyncSession, customer: Customer, hours: int | None) -> datetime.datetime | None:
    """توقفِ پاسخِ خودکار برایِ `hours` ساعت؛ `None` یعنی همین حالا آزاد شود."""
    if hours is not None and (type(hours) is not int or not 1 <= hours <= 24 * 30):
        raise ValueError("مدتِ توقف معتبر نیست")
    if hours is None:
        customer.ai_paused_until = None
        await session.flush()
        return None
    until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=hours)
    customer.ai_paused_until = until
    await session.flush()
    return until
