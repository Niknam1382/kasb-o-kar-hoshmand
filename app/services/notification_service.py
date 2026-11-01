"""صندوقِ خروجیِ اعلان‌ها (P20 · «هیچ خبرِ پرداختی گم نشود»).

مسیرهایِ اطلاع‌رسانی امروز «بهترین‌تلاش»ند: `try: await bot.send_message(...) except TelegramAPIError:
logger...`. اگر تلگرام لحظه‌ای ۵۰۳/۴۲۹ بدهد یا مشتری ربات را تازه آن‌بلاک کرده باشد، خبرِ
سفارشِ *پرداخت‌شده* برایِ همیشه گم می‌شود و هیچ‌کس نمی‌فهمد.

این سرویس همان خبر را در جدولِ `notifications` می‌گذارد و جابِ دوره‌ای با backoff دوباره
تلاش می‌کند؛ بعد از `MAX_ATTEMPTS` وضعیت `failed` می‌شود (پنهان نمی‌شود، قابلِ شمارش است).

قاعدهٔ استفاده: هیچ‌وقت «فقط» enqueue نکن — اول تلاشِ فوری، و اگر شکست خورد enqueue ⇒ کاربر در
حالتِ عادی همان لحظه پیام می‌گیرد و مسیرِ شکست تضمین می‌شود. به همین دلیل `enqueue` خطایِ
شبکه را نمی‌بلعد و هیچ استثنایی به هندلرِ caller برنمی‌گرداند.

dedupe: `dedupe_key` یکتاست، پس دوبار-فراخوانیِ همان رویداد (وب‌هوکِ تکراری، دابل‌تپ) یک صفِ
دوتایی نمی‌سازد.
"""

from __future__ import annotations

import datetime
import logging

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Notification
from app.services import platform_service

logger = logging.getLogger(__name__)

PENDING = "pending"
SENT = "sent"
FAILED = "failed"

MAX_ATTEMPTS = 6
BACKOFF_SECONDS = (30, 120, 600, 1800, 3600, 7200)
# P21-F: حلقهٔ تخلیه هر ۶۰ ثانیه اجرا می‌شود؛ ۲۰۰ در هر دور ≈ ۱۲ هزار پیام/ساعت،
# که از سقف نرخ تلگرام (~۳۰ پیام/ثانیه به‌طور کلی) پایین‌تر است و برای پخشِ زمان‌بندی‌شده لازم است.
DUE_LIMIT = 200
# P21-F: سقفِ یکِ «تلاشِ دوبارهٔ دستی» (دکمهٔ پنل). صفِ شکست‌خورده می‌تواند ده‌ها هزار ردیف
# داشته باشد؛ برگرداندنِ همه در یکِ کلیک یعنی ریزشِ ناگهانی رویِ همان کانالِ که قبلاً شکست خورده.
RETRY_BATCH_LIMIT = 1000
# P21-B (O3): مهلتِ نگهداریِ خودِ صف. `sent` بعد از ۳۰ روز بی‌فایده است؛ `failed` ۹۰ روز
# می‌ماند چون «چه خبری هرگز نرسید» برایِ تشخیصِ قطعیِ تلگرام/بله لازم است.
SENT_RETENTION_DAYS = 30
FAILED_RETENTION_DAYS = 90


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def next_attempt_at(attempts: int, now: datetime.datetime | None = None) -> datetime.datetime:
    now = now or _utcnow()
    delay = BACKOFF_SECONDS[min(max(attempts, 1) - 1, len(BACKOFF_SECONDS) - 1)]
    return now + datetime.timedelta(seconds=delay)


async def enqueue(
    session: AsyncSession,
    chat_id: int,
    text: str,
    *,
    platform: str = platform_service.TELEGRAM,
    shop_bot_id: int | None = None,
    owner_id: int | None = None,
    label: str | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """یک اعلانِ در‌انتظارِ ارسال می‌سازد. False ⇒ از قبل در صف است (dedupe) یا نوشتن ممکن نبود."""
    if not text or not str(text).strip():
        return False
    row = Notification(
        chat_id=int(chat_id),
        text=str(text)[:6000],
        platform=platform,
        shop_bot_id=shop_bot_id,
        owner_id=owner_id,
        label=(label or "")[:64] or None,
        dedupe_key=dedupe_key[:64] if dedupe_key else None,
        status=PENDING,
        next_attempt_at=_utcnow(),
    )
    try:
        # savepoint (نه rollbackِ کلِ تراکنش): اگر همین خبر از قبل در صف باشد، فقط همین درج
        # لغو می‌شود و نوشته‌هایِ قبلیِ همان هندلر (مثلاً تغییرِ وضعیتِ سفارش) سالم می‌ماند.
        async with session.begin_nested():
            session.add(row)
    except IntegrityError:
        logger.info("اعلانِ تکراری در صف رها شد (dedupe=%s)", dedupe_key)
        return False
    return True


async def send_due(session: AsyncSession, bot_manager, main_bot, limit: int = DUE_LIMIT, now: datetime.datetime | None = None) -> dict[str, int]:
    """یک دورِ تلاشِ دوباره. برگمی‌گرداند {sent, retrying, failed}. هیچ استثنایی به بیرون نمی‌رود.

    رباتِ هر صف از پلتفرمِ خودش انتخاب می‌شود (`customer_bot`)؛ فرستادنِ شناسهٔ بله‌ای از
    رباتِ تلگرام می‌تواند به آدمِ غریبه‌ای برسد که همان عدد را دارد.
    """
    now = now or _utcnow()
    result = await session.execute(
        select(Notification)
        .where(Notification.status == PENDING, Notification.next_attempt_at <= now)
        .order_by(Notification.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    rows = list(result.scalars().all())
    summary = {"sent": 0, "retrying": 0, "failed": 0}
    for row in rows:
        bot = main_bot if row.shop_bot_id is None else bot_manager.customer_bot(row.shop_bot_id, row.platform)
        if bot is None:
            _defer(row, "رباتِ این مشتری در این سرویس فعال نیست", now)
            summary["retrying"] += 1
            continue
        try:
            await bot.send_message(row.chat_id, row.text)
        except Exception as exc:  # noqa: BLE001 — هر خطایِ شبکه/دسترسی یعنی «الان نه»، نه «هیچ‌وقت»
            _defer(row, str(exc), now)  # تنها جایِ افزایشِ attempts (قبلاً دو بار زیاد می‌شد)
            if row.attempts >= MAX_ATTEMPTS:
                row.status = FAILED
                summary["failed"] += 1
                logger.warning(
                    "اعلانِ %s (id=%s) بعد از %s تلاش بی‌نتیجه ماند؛ در پنلِ ادمین قابلِ مشاهده است.",
                    row.label, row.id, row.attempts,
                )
            else:
                summary["retrying"] += 1
            continue
        row.status = SENT
        row.sent_at = _utcnow()
        row.last_error = None
        summary["sent"] += 1
    await session.flush()
    return summary


def _defer(row: Notification, error: str, now: datetime.datetime) -> None:
    row.attempts = int(row.attempts or 0) + 1
    row.last_error = (error or "")[:200]
    row.next_attempt_at = next_attempt_at(row.attempts, now)


async def stats(session: AsyncSession) -> dict[str, int]:
    """شمارشِ صف برایِ پنلِ ادمین: {pending, failed, sent}."""
    rows = await session.execute(select(Notification.status, func.count()).group_by(Notification.status))
    counts = {status: int(count) for status, count in rows.all()}
    return {"pending": counts.get(PENDING, 0), "failed": counts.get(FAILED, 0), "sent": counts.get(SENT, 0)}


async def next_attempt_time(session: AsyncSession) -> datetime.datetime | None:
    """زمانِ نزدیک‌ترین تلاشِ باقی‌مانده (None ⇒ چیزی در صف نیست)."""
    value = (
        await session.execute(select(func.min(Notification.next_attempt_at)).where(Notification.status == PENDING))
    ).scalar_one_or_none()
    return value


async def recent_failed(session: AsyncSession, limit: int = 3) -> list[Notification]:
    result = await session.execute(
        select(Notification).where(Notification.status == FAILED).order_by(Notification.id.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def retry_failed(session: AsyncSession, limit: int = RETRY_BATCH_LIMIT) -> int:
    """شکست‌خورده‌ها را با backoffِ تازه به صف برمی‌گرداند؛ تاریخچه پاک نمی‌شود.

    سقفِ تلاش یعنی صفِ «failed» خودش دیگر حرکت نمی‌کند، پس این دکمه تنها راهِ ارسالِ دوباره
    است. `dedupe_key` دست نمی‌خورد ⇒ اگر رویدادِ همان خبر دوباره enqueue شود باز هم تکراری نمی‌شود.
    P21-F: `last_error` دیگر پاک نمی‌شود (همان یادداشتِ «چرا نرسید» تنها شاهدِ یکِ ارسالِ شکست‌خورده
    است و وعدهٔ پنل هم «پاک نشدنِ تاریخچه» بود) و به‌جایِ کلِ صف، فقط `limit` ردیفِ تازه‌تر
    برگردانده می‌شود ⇒ یکِ دابل‌تپِ تصادفی صفِ چندصد هزار تایی را ناگهان به تلگرام برنمی‌گرداند.
    """
    now = _utcnow()
    newest = (
        select(Notification.id)
        .where(Notification.status == FAILED)
        .order_by(Notification.id.desc())
        .limit(limit)
        .scalar_subquery()
    )
    result = await session.execute(
        update(Notification)
        .where(Notification.id.in_(newest), Notification.status == FAILED)
        .values(status=PENDING, attempts=0, next_attempt_at=now)
    )
    await session.flush()
    return int(result.rowcount or 0)


async def prune_aged(
    session: AsyncSession,
    *,
    sent_days: int = SENT_RETENTION_DAYS,
    failed_days: int = FAILED_RETENTION_DAYS,
    now: datetime.datetime | None = None,
) -> int:
    """ردیف‌هایِ کهنهٔ صف را پاک می‌کند. بدونِ این، جدولِ تازه‌یِ P20 تا ابد رشد می‌کرد.

    دو مهلتِ جدا عمدی است: `sent` دیگر هیچ ارزشی ندارد (خبر رفته و در دفترِ سفارش هم ثبت شده)
    ولی `failed` سابقهٔ «چه خبری به مشتری نرسید» است و برایِ تشخیصِ قطعیِ تلگرام/بله لازم است،
    پس ۹۰ روز می‌ماند. `pending` هرگز پاک نمی‌شود — آن بدهیِ ارسال است، نه تاریخچه.
    """
    now = now or _utcnow()
    removed = 0
    for status, days in ((SENT, sent_days), (FAILED, failed_days)):
        if days <= 0:
            continue
        result = await session.execute(
            delete(Notification).where(
                Notification.status == status,
                Notification.created_at < now - datetime.timedelta(days=days),
            )
        )
        removed += int(result.rowcount or 0)
    await session.flush()
    return removed
