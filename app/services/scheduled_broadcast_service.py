"""P21-D (F2): پیامِ مشتری‌ها با زمانِ تعیین‌شده، سوار بر صندوقِ اعلان‌ها.

فروشگاه‌دار امروز فقط «همین الان» می‌تواند پیام همگانی بفرستد. با این سرویس می‌گوید «امشب ساعت
۲۱» و جابِ دوره‌ای سرِ وقت، برایِ هر گیرنده یک ردیفِ `notifications` می‌سازد؛ ارسالِ واقعی،
backoff و «شکستِ بلندگومد» همان‌جا انجام می‌شود ⇒ پیامِ زمان‌بندی‌شده هم گم نمی‌شود.

ایدِمپوتنسی: `dedupe_key = bcast:{id}:{chat_id}:{platform}` ⇒ اگر دو نسخهٔ اپ یا دو دورِ جاب
هم‌زمان همان ردیف را ببینند، هر گیرنده یکِ پیام می‌گیرد (نه دو تا).
"""

from __future__ import annotations

import datetime
import logging
import re

from aiogram import Bot
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ScheduledBroadcast, ShopBot
from app.services import customer_service, notification_service
from app.utils.jalali import TEHRAN_TZ
from app.utils.text_limits import TELEGRAM_TEXT_LIMIT, clip

logger = logging.getLogger(__name__)

PENDING = "pending"
QUEUED = "queued"
CANCELLED = "cancelled"
FAILED = "failed"

MIN_LEAD_MINUTES = 5  # «۵ دقیقهٔ دیگر» مجاز است، «همین الان» نه (برایِ همان «همین الان» مسیرِ فوری هست)
MAX_LEAD_DAYS = 60
MAX_ACTIVE_PER_SHOP = 5
DUE_LIMIT = 20

# پ۷۶ · خواستهٔ مالک (موردِ ۱۷): «ارسالِ چندروزه/هفتگی». «once» همان رفتارِ امروز است؛ ردیف‌هایِ
# موجود همه once می‌مانند (server_default) و هیچ پیامی دوبار فرستاده نمی‌شود.
REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKLY = "weekly"
REPEAT_KINDS = (REPEAT_ONCE, REPEAT_DAILY, REPEAT_WEEKLY)
REPEAT_MAX_OCCURRENCES = 60  # سقفِ ایمنی: حتی با «بی‌پایان»، بیشتر از این نوبت در یکِ ردیف صف نمی‌شود
STEP_DAYS = {REPEAT_DAILY: 1, REPEAT_WEEKLY: 7}
_TIME_PATTERN = re.compile(r"^(\d{1,2})[:.](\d{2})$")
_PLUS_PATTERN = re.compile(r"^\+\s*(\d{1,4})(m|h|d|د|س|ر)$", re.IGNORECASE)
_UNIT_TO_SECONDS = {"m": 60, "h": 3600, "d": 86400}


def _to_utc(moment: datetime.datetime) -> datetime.datetime:
    return moment.astimezone(datetime.timezone.utc) if moment.tzinfo else moment.replace(tzinfo=datetime.timezone.utc)


def _local(now: datetime.datetime) -> datetime.datetime:
    return now.astimezone(TEHRAN_TZ) if now.tzinfo else datetime.datetime.fromtimestamp(now.timestamp(), TEHRAN_TZ)


def parse_when(raw: str | None, now: datetime.datetime | None = None) -> datetime.datetime | None:
    """«۲۱:۳۰» · «فردا ۹:۳۰» · «امروز ۲۱:۰۰» · «+۳h» / «+۴۵m» / «+۲د».

    ساعت‌ها به وقتِ تهران خوانده می‌شوند (مخاطبِ این محصول ایرانی است). اگر ساعتِ گفته‌شده
    گذشته باشد، همان ساعت در روزِ بعد معنایی دارد — نه ردِ پیام.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    value = (raw or "").strip().replace("،", " ").replace("\u200c", " ")
    value = " ".join(value.split())
    if not value:
        return None

    plus = _PLUS_PATTERN.match(value)
    if plus:
        unit = {"د": "m", "س": "h", "ر": "d"}.get(plus.group(2).lower(), plus.group(2).lower())
        return _to_utc(_local(now) + datetime.timedelta(seconds=int(plus.group(1)) * _UNIT_TO_SECONDS[unit]))

    parts = value.split()
    clock = parts[-1]
    match = _TIME_PATTERN.match(clock)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None

    local_now = _local(now)
    day = local_now.date()
    if len(parts) == 2:
        if parts[0] == "فردا":
            day = day + datetime.timedelta(days=1)
        elif parts[0] != "امروز":
            return None
    candidate = datetime.datetime.combine(day, datetime.time(hour, minute), tzinfo=TEHRAN_TZ)
    if candidate <= local_now:
        candidate = candidate + datetime.timedelta(days=1)
    return _to_utc(candidate)


def occurrence(day_offset: int, hour: int, minute: int = 0, now: datetime.datetime | None = None) -> datetime.datetime | None:
    """پ۷۶ · زمانِ «چند روز بعد، ساعتِ مشخص» به وقتِ تهران ⇒ UTC.

    ویزاردِ تازه به‌جایِ حدس‌زدنِ رشته، این را صدا می‌زند: «امروز ۱۸» اگر گذشته باشد *امروز*
    برنمی‌گردد (اعتبارسنجیِ `validate_when` ردش می‌کند و فروشگاه‌دار روزِ دیگری انتخاب می‌کند).
    """
    if not 0 <= day_offset <= MAX_LEAD_DAYS or not 0 <= hour <= 23 or not 0 <= minute <= 59:
        return None
    moment = now or datetime.datetime.now(datetime.timezone.utc)
    local = _local(moment) + datetime.timedelta(days=day_offset)
    return _to_utc(datetime.datetime(local.year, local.month, local.day, hour, minute, tzinfo=TEHRAN_TZ))


def validate_when(scheduled_at: datetime.datetime | None, now: datetime.datetime | None = None) -> tuple[bool, str]:
    """(مجاز؟، دلیلِ فارسیِ رد). مرزها عمدي‌اند: «همین الان» یعنی مسیرِ فوری، و ۶۰ روز یعنی صفِ نامعقول."""
    if scheduled_at is None:
        return False, "format"
    now = now or datetime.datetime.now(datetime.timezone.utc)
    lead = (scheduled_at - now).total_seconds() / 60
    if lead < MIN_LEAD_MINUTES:
        return False, "too_soon"
    if lead > MAX_LEAD_DAYS * 24 * 60:
        return False, "too_far"
    return True, ""


async def active_count(session: AsyncSession, shop_bot_id: int) -> int:
    value = await session.execute(
        select(func.count())
        .select_from(ScheduledBroadcast)
        .where(ScheduledBroadcast.shop_bot_id == shop_bot_id, ScheduledBroadcast.status == PENDING)
    )
    return int(value.scalar_one() or 0)


MAX_ACTIVE_REACHED = "max_active"
TOO_MANY = "too_many"


async def schedule(
    session: AsyncSession,
    *,
    shop_bot: ShopBot,
    owner_id: int,
    text: str,
    scheduled_at: datetime.datetime,
    recipient_ids: list[int] | None = None,
    repeat_kind: str = REPEAT_ONCE,
    repeat_until: datetime.datetime | None = None,
) -> ScheduledBroadcast | str:
    """یکِ ارسالِ زمان‌بندی‌شده می‌سازد؛ ScheduledBroadcast ⇒ موفق، رشته ⇒ کدِ خطا.

    `recipient_ids` گیرنده‌هایِ یک بخشِ CRM است؛ None ⇒ همه‌یِ مشتریانِ فروشگاه. اگر فهرستِ
    بخشِ انتخابی *در زمانِ ارسال* دیگر وجود نداشته باشد، آن گیرنده ساده رد می‌شود (نه پیامِ
    سرِ‌اینه به آدمِ دیگر).
    """
    body = (text or "").strip()
    if not body or len(body) > TELEGRAM_TEXT_LIMIT:
        return "empty"
    if await active_count(session, shop_bot.id) >= MAX_ACTIVE_PER_SHOP:
        return MAX_ACTIVE_REACHED
    kind = repeat_kind if repeat_kind in REPEAT_KINDS else REPEAT_ONCE
    row = ScheduledBroadcast(
        shop_bot_id=shop_bot.id,
        owner_id=owner_id,
        text=clip(body, TELEGRAM_TEXT_LIMIT),
        recipient_ids=None if not recipient_ids else ",".join(str(int(pk)) for pk in recipient_ids),
        scheduled_at=scheduled_at,
        status=PENDING,
        repeat_kind=kind,
        repeat_until=None if kind == REPEAT_ONCE else (_to_utc(repeat_until) if repeat_until else None),
    )
    session.add(row)
    await session.flush()
    return row


async def upcoming(session: AsyncSession, shop_bot_id: int, limit: int = 5) -> list[ScheduledBroadcast]:
    result = await session.execute(
        select(ScheduledBroadcast)
        .where(ScheduledBroadcast.shop_bot_id == shop_bot_id, ScheduledBroadcast.status == PENDING)
        .order_by(ScheduledBroadcast.scheduled_at)
        .limit(limit)
    )
    return list(result.scalars().all())


async def cancel(session: AsyncSession, *, shop_bot_id: int, broadcast_id: int) -> bool:
    """لغو فقط توسطِ صاحبِ همان ربات؛ ردیفِ queued شده دیگر قابلِ لغو نیست (پیام رفته)."""
    row = (
        await session.execute(
            select(ScheduledBroadcast).where(
                ScheduledBroadcast.id == broadcast_id,
                ScheduledBroadcast.shop_bot_id == shop_bot_id,
                ScheduledBroadcast.status == PENDING,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = CANCELLED
    row.note = "لغو توسطِ فروشگاه‌دار"
    await session.flush()
    return True


def _recipient_ids(row: ScheduledBroadcast) -> list[int]:
    if not row.recipient_ids:
        return []
    return [int(part) for part in row.recipient_ids.split(",") if part.strip().isdigit()]


async def recipients_for(session: AsyncSession, row: ScheduledBroadcast) -> list[tuple[int, str]]:
    """گیرنده‌هایِ همین ردیف (بخشِ CRM یا همه) — با پلتفرمِ هر گیرنده."""
    ids = _recipient_ids(row)
    if ids:
        return await customer_service.recipients_by_ids(session, row.shop_bot_id, ids)
    return await customer_service.recipients_by_shop_bot(session, row.shop_bot_id)


async def queue_due(session: AsyncSession, main_bot: Bot | None = None, limit: int = DUE_LIMIT, now: datetime.datetime | None = None) -> dict[str, int]:
    """رسید به زمانش ⇒ هر گیرنده یک ردیف در صندوقِ اعلان. برگمی‌گرداند {scheduled, queued, empty}.

    گیرنده‌ها با پلتفرمِ خودشان می‌روند (یکِ عددِ یکسان در تلگرام و بله دو آدمِ متفاوت است) و
    خودِ ارسال/تلاشِ دوباره را `notification_service` انجام می‌دهد — این تابع فقط «صف می‌کند».
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rows = list(
        (
            await session.execute(
                select(ScheduledBroadcast)
                .where(ScheduledBroadcast.status == PENDING, ScheduledBroadcast.scheduled_at <= now)
                .order_by(ScheduledBroadcast.scheduled_at)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
        )
        .scalars()
        .all()
    )
    summary = {"scheduled": 0, "queued": 0, "empty": 0}
    for row in rows:
        recipients = await recipients_for(session, row)
        if not recipients:
            row.status = FAILED
            row.note = "هیچ گیرنده‌ای برایِ این ارسال باقی نمانده بود"
            summary["empty"] += 1
            continue
        queued = 0
        # پ۷۶: نوبتِ جاری در dedupe_key می‌آید تا نوبتِ بعدیِ یکِ ارسالِ هفتگی «تکراری» حساب نشود.
        # برایِ once همان کلیدِ قبلی است ⇒ هیچ ردیفِ موجودی رفتارِ تازه‌ای نمی‌بیند.
        turn = int(row.repeat_sent or 0)
        for chat_id, platform in recipients:
            key = f"bcast:{row.id}:{chat_id}:{platform}" if row.repeat_kind == REPEAT_ONCE else f"bcast:{row.id}:{turn}:{chat_id}:{platform}"
            added = await notification_service.enqueue(
                session,
                chat_id,
                row.text,
                platform=platform,
                shop_bot_id=row.shop_bot_id,
                label=f"scheduled-broadcast:{row.id}",
                dedupe_key=key[:64],
            )
            queued += 1 if added else 0
        row.repeat_sent = turn + 1
        nxt = next_occurrence(row, now)
        if nxt is None:
            row.status = QUEUED
        else:
            row.status = PENDING
            row.scheduled_at = nxt
        row.queued_count = queued
        row.sent_at = now
        summary["queued"] += queued
        summary["scheduled"] += 1
        logger.info("پخشِ زمان‌بندی‌شدهٔ %s در صف قرار گرفت: %s گیرنده (از %s).", row.id, queued, len(recipients))
    if rows:
        await session.flush()
    return summary


def next_occurrence(row: ScheduledBroadcast, now: datetime.datetime) -> datetime.datetime | None:
    """زمانِ نوبتِ بعدیِ یکِ ارسالِ تکرارشونده، یا None اگر تمام شده باشد.

    پایان یعنی: یک‌بارمصرف، یا رسیدن به `repeat_until`، یا خوردن به سقفِ ایمنیِ
    REPEAT_MAX_OCCURRENCES. زمان از «نوبتِ قبلی + گام» حساب می‌شود (نه از `now`) تا اگر جاب
    چند ساعت با تأخیر افتاد، ساعتِ انتخابیِ فروشگاه‌دار رویِ هم نرود؛ اگر آن زمان به‌دلیلِ
    تأخیرِ طولانی در گذشته ماند، از `now` جلو می‌افتد (پیامِ دیرهنگام بهتر از بی‌پیام نیست،
    پس همان نوبت در نزدیک‌ترین لحظهٔ آینده صف می‌شود).
    """
    kind = getattr(row, "repeat_kind", REPEAT_ONCE) or REPEAT_ONCE
    if kind not in STEP_DAYS:
        return None
    if int(getattr(row, "repeat_sent", 0) or 0) >= REPEAT_MAX_OCCURRENCES:
        return None
    step = datetime.timedelta(days=STEP_DAYS[kind])
    base = _to_utc(row.scheduled_at) + step
    candidate = base if base > now else now + step
    until = getattr(row, "repeat_until", None)
    if until is not None and candidate > _to_utc(until):
        return None
    return candidate
