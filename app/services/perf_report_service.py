"""گزارشِ همزمانیِ مشتریان و عملکردِ ربات در بازه‌یِ زمانی (P30).

چرا: ادمین تا امروز فقط «آمار سراسری» داشت که شمارشِ کلِ تاریخچه است. برایِ تصمیمِ ظرفیت
باید دید *چه ساعتی* چند مشتری هم‌زمان فعال‌اند و کدام قابلیتِ ربات در همان بازه کار کرده.

دو بازه (درخواستِ کاربر: هر دو، با دکمهٔ انتخابِ بازه):
* `24h` — ۲۴ ساعت گذشته با دانهٔ ۱۰ دقیقه (۱۴۴ دانه)
* `7d`  — ۷ روز گذشته با دانهٔ ۶۰ دقیقه (۱۶۸ دانه)

فقط‌خواندنی است و هیچ سطری نمی‌نویسد. همزمانی = «چند مشتریِ متمایز در آن دانه پیام داده‌اند» —
نمایندهٔ سِشنِ بازِ تلگرام نیست (تلگرام آن را نمی‌دهد)، ولی همان چیزی است که بارِ واقعیِ AI و
دیتابیس را می‌سازد.

کوئری‌ها: سه aggregate (دانه‌ها، شمارشِ قابلیت‌ها، شمارشِ سفارش/مشاوره/پرداخت) + چند aggregateِ
گروهیِ دیگر (کانال‌ها، پنج شلوغ‌ترینِ فروشگاه) — بدونِ حلقهٔ per-shop، چون در ۵۰۰ فروشگاه همان
اشتباهِ P29 تکرار می‌شد.

پ۱۲۳ (خواستِ صریحِ مالکِ محصول: «درخواست در ثانیه را میانگین نشان نده»): `messages_per_minute` تنها
عددِ نرخیِ گزارش نبود که گمراه می‌کرد — هیچ‌جا نمی‌گفت بدترینِ ثانیهٔ سرور چند درخواست دیده است.
`_peak_per_second` اضافه شد: با دو پاس (سطلِ یک‌دقیقه‌ای رویِ کلِ بازه ⇒ شلوغ‌ترینِ سه دقیقه ⇒
هیستوگرامِ ثانیه‌ای فقط حولِ همان‌ها، هر طرف ۶۰ ثانیه) پیکِ *واقعی*، طولِ رَکوردِ پیوستهٔ آن و ثانیهٔ
وقوعش را می‌دهد؛ برایِ دو منبع: پیامِ مشتری و ردیف‌هایِ واقعیِ مصرفِ AI. هزینه: به‌ازایِ هر منبع یکِ
aggregateِ دقایق + حداکثرِ سه پرس‌وجویِ ثانیه‌ای رویِ پنجره‌هایِ ۳ دقیقه‌ای.
"""
from __future__ import annotations

import datetime as dt
import math
from typing import Any

from sqlalchemy import Integer, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Customer,
    ConversationMessage,
    OrderConsultation,
    OrderPayment,
    PaymentEventLog,
    ShopBot,
    WalletTransaction,
    WalletTransactionReason,
)

# کلیدِ بازه ← (ساعتِ پنجره، دانه به دقیقه)
RANGES: dict[str, tuple[int, int]] = {"24h": (24, 10), "7d": (24 * 7, 60)}
RANGE_LABELS: dict[str, str] = {"24h": "۲۴ ساعت (هر ۱۰ دقیقه)", "7d": "۷ روز (هر ساعت)"}
NOW_WINDOW_MINUTES = 5

# برچسبِ فارسیِ هر قابلیتِ مصرفِ AI (ترتیبِ نمایش)
FEATURE_LABELS: tuple[tuple[WalletTransactionReason, str], ...] = (
    (WalletTransactionReason.CHAT_MESSAGE, "چتِ متنی"),
    (WalletTransactionReason.PHOTO_ANALYSIS, "تحلیلِ عکس"),
    (WalletTransactionReason.VOICE_TRANSCRIPTION, "رونویسیِ صوت"),
    (WalletTransactionReason.RECEIPT_ANALYSIS, "تحلیلِ رسید"),
    (WalletTransactionReason.ORDER_DETECTION, "تشخیصِ سفارش"),
    (WalletTransactionReason.CART_EDIT, "ویرایشِ هوشمندِ سبد"),
    (WalletTransactionReason.CRM_SUMMARY, "خلاصهٔ مشتری"),
    (WalletTransactionReason.OWNER_ASSISTANT, "دستیارِ مدیریتی"),
)
_BARS = "▁▂▄▆█"

# پ۱۲۳ (درخواستِ مستقیمِ مالکِ محصول): عددِ «میانگینِ پیام در دقیقه» نمی‌تواند بگوید سرور در بدترینِ
# لحظه چقدر بار دیده است. این سه ثابت پاسِ دوم (هیستوگرامِ ثانیه‌ای) را کنترل می‌کنند.
PEAK_TOP_MINUTES = 3          # چند دقیقهٔ شلوغِ بازه با دقتِ ثانیه بازبینی می‌شود
PEAK_WINDOW_PADDING_SECONDS = 60   # هر طرفِ دقیقهٔ شلوغ، تا رَکوردِ پیوستهٔ پیک درست اندازه گرفته شود
PEAK_THRESHOLD_RATIO = 0.8    # «ثانیهٔ داغ» = ثانیه‌ای با ≥ ۸۰٪ پیک
AI_REASONS = tuple(reason for reason, _label in FEATURE_LABELS)


def _bucket_seconds(bucket_minutes: int) -> int:
    return bucket_minutes * 60


def _series(bucket_counts: dict[int, int], *, start: dt.datetime, bucket_minutes: int, count: int) -> list[tuple[dt.datetime, int]]:
    """دانه‌هایِ خالی را با صفر پر می‌کند تا نمودارِ متنی پیوسته بماند."""
    step = dt.timedelta(minutes=bucket_minutes)
    first_bucket = _epoch_bucket(start, bucket_minutes)
    remainder = (start - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)) % step
    return [
        (start + max(dt.timedelta(0), step * index - remainder), bucket_counts.get(first_bucket + index, 0))
        for index in range(count)
    ]


def _epoch_bucket(moment: dt.datetime, bucket_minutes: int) -> int:
    return (moment - dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)) // dt.timedelta(minutes=bucket_minutes)


MAX_BUCKETS = 200


def auto_grain(span_hours: float) -> int:
    if span_hours <= 2:
        return 5
    if span_hours <= 26:
        return 10
    if span_hours <= 24 * 8:
        return 60
    if span_hours <= 24 * 40:
        return 360
    if span_hours <= 24 * (MAX_BUCKETS - 1):
        return 1440
    return max(10080, math.ceil(span_hours * 60 / (MAX_BUCKETS - 1)))


def _peak_from_seconds(seconds: dict[int, int], *, candidates: set[int]) -> dict[str, Any] | None:
    """بیشینهٔ *واقعیِ* شمارِ رویداد در یکِ ثانیهٔ ساعتی (نه میانگین هیچ پنجره‌ای).

    سه عدد برمی‌گرداند که سؤالِ ادمین را جواب می‌دهد: چند تا در ثانیه (`rps`)، چند ثانیهٔ پیوسته رویِ
    همان عدد مانده (`run_seconds`) و در کدام ثانیه (`at`). `candidates` فقط ثانیه‌هایِ خودِ
    دقیقه(های)ِ شلوغ است؛ ثانیه‌هایِ همسایه فقط برایِ اندازه‌گیریِ طولِ رَکورد خوانده می‌شوند تا یکِ
    پیکِ ۹۰ ثانیه‌ای به دو تا شکسته نشود.
    """
    pool = {second: count for second, count in seconds.items() if second in candidates and count > 0}
    if not pool:
        return None
    peak_second = min(second for second in pool if pool[second] == max(pool.values()))
    rps = pool[peak_second]
    run = 1
    probe = peak_second - 1
    while seconds.get(probe) == rps:
        run += 1
        probe -= 1
    probe = peak_second + 1
    while seconds.get(probe) == rps:
        run += 1
        probe += 1
    threshold = max(1, math.ceil(rps * PEAK_THRESHOLD_RATIO))
    return {
        "rps": rps,
        "at": dt.datetime.fromtimestamp(peak_second, dt.timezone.utc),
        "run_seconds": run,
        "hot_seconds": sum(1 for count in pool.values() if count >= threshold),
        "threshold": threshold,
    }


async def _peak_per_second(
    session: AsyncSession, source: str, since: dt.datetime, until: dt.datetime
) -> dict[str, Any] | None:
    """دو پاس: سطلِ یک‌دقیقه‌ای رویِ کلِ بازه ⇒ شلوغ‌ترینِ دقیقه‌ها؛ بعدِ هیستوگرامِ ثانیه‌ای فقط حولِ همان‌ها.

    چرا این شکل: هیستوگرامِ ثانیه‌ای رویِ یکِ بازهٔ هفتگی تا ۶۰۴٬۸۰۰ سطر برمی‌گرداند، پس اول با یکِ
    aggregateِ ارزان «کجا شلوغ بوده» پیدا می‌شود و فقط همان چند دقیقه با دقتِ ثانیه خوانده می‌شود.
    `source = "messages"` ⇒ پیامِ مشتری (نقشهٔ راهِ بار؛ هر پیام معمولاً یکِ فراخوانِ AI می‌سازد)
    `source = "ai_requests"` ⇒ شمارِ واقعیِ مصرفِ AI از دفترِ کیف‌پول.
    """
    if source == "messages":
        moment, table, clauses = ConversationMessage.created_at, ConversationMessage, (ConversationMessage.role == "user",)
    elif source == "ai_requests":
        moment, table, clauses = WalletTransaction.created_at, WalletTransaction, (WalletTransaction.reason.in_(list(AI_REASONS)),)
    else:  # pragma: no cover — دفاع در برابرِ فراخوانِ اشتباه
        raise ValueError(f"منبعِ ناشناخته برایِ پیک: {source}")

    minute_expr = cast(func.floor(func.extract("epoch", moment) / 60), Integer).label("m")
    busy = select(minute_expr, func.count()).select_from(table).where(moment >= since, moment < until, *clauses)
    rows = (await session.execute(busy.group_by(minute_expr).order_by(func.count().desc()).limit(PEAK_TOP_MINUTES))).all()
    if not rows:
        return None

    busy_minutes = {int(minute_index) for minute_index, _count in rows}
    candidates = {
        second
        for minute_index in busy_minutes
        for second in range(minute_index * 60, minute_index * 60 + 60)
    }
    seconds: dict[int, int] = {}
    for minute_index in sorted(busy_minutes):
        low = dt.datetime.fromtimestamp(minute_index * 60 - PEAK_WINDOW_PADDING_SECONDS, dt.timezone.utc)
        high = dt.datetime.fromtimestamp(minute_index * 60 + 60 + PEAK_WINDOW_PADDING_SECONDS, dt.timezone.utc)
        second_expr = cast(func.floor(func.extract("epoch", moment)), Integer).label("s")
        span = select(second_expr, func.count()).select_from(table).where(moment >= low, moment < high, *clauses)
        for second_index, second_count in (await session.execute(span.group_by(second_expr))).all():
            seconds[int(second_index)] = int(second_count)
    return _peak_from_seconds(seconds, candidates=candidates)


async def build(
    session: AsyncSession,
    range_key: str = "24h",
    *,
    now: dt.datetime | None = None,
    since: dt.datetime | None = None,
    until: dt.datetime | None = None,
) -> dict[str, Any]:
    utc_now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    custom = since is not None
    window_until = min((until or utc_now).astimezone(dt.timezone.utc), utc_now)
    if since is not None:
        since = since.astimezone(dt.timezone.utc)
        if since >= window_until:
            raise ValueError("زمانِ پایان باید پس از شروع و شروع پیش از اکنون باشد.")
        hours = (window_until - since).total_seconds() / 3600.0
        bucket_minutes = auto_grain(hours)
        bucket_seconds = _bucket_seconds(bucket_minutes)
        first_bucket = _epoch_bucket(since, bucket_minutes)
        last_bucket = _epoch_bucket(window_until - dt.timedelta(microseconds=1), bucket_minutes)
        bucket_count = last_bucket - first_bucket + 1
    else:
        hours, bucket_minutes = RANGES[range_key]
        bucket_seconds = _bucket_seconds(bucket_minutes)
        bucket_count = int(hours * 3600 // bucket_seconds)
        current_bucket = _epoch_bucket(window_until, bucket_minutes)
        first_bucket = current_bucket - bucket_count + 1
        since = dt.datetime.fromtimestamp(first_bucket * bucket_seconds, dt.timezone.utc)

    bucket_expr = cast(func.floor(func.extract("epoch", ConversationMessage.created_at) / bucket_seconds), Integer).label("bucket")
    rows = await session.execute(
        select(bucket_expr, func.count(distinct(ConversationMessage.customer_id)))
        .where(ConversationMessage.created_at >= since, ConversationMessage.created_at < window_until,
            ConversationMessage.role == "user")
        .group_by(bucket_expr)
    )
    bucket_counts = {int(bucket): int(customers) for bucket, customers in rows.all()}

    message_rows = await session.execute(
        select(func.count(), func.count(distinct(ConversationMessage.customer_id))).where(
            ConversationMessage.created_at >= since, ConversationMessage.created_at < window_until,
            ConversationMessage.role == "user"
        )
    )
    messages_total, customers_total = message_rows.one()

    now_rows = await session.execute(
        select(func.count(distinct(ConversationMessage.customer_id))).where(
            ConversationMessage.created_at >= utc_now - dt.timedelta(minutes=NOW_WINDOW_MINUTES),
            ConversationMessage.created_at < utc_now,
            ConversationMessage.role == "user",
        )
    )
    active_now = int(now_rows.scalar() or 0)

    feature_rows = await session.execute(
        select(WalletTransaction.reason, func.count())
        .where(
            WalletTransaction.created_at >= since, WalletTransaction.created_at < window_until,
            WalletTransaction.reason.in_([reason for reason, _ in FEATURE_LABELS]),
        )
        .group_by(WalletTransaction.reason)
    )
    feature_counts = {reason: int(count) for reason, count in feature_rows.all()}

    type_rows = await session.execute(
        select(OrderConsultation.type, func.count()).where(
            OrderConsultation.created_at >= since, OrderConsultation.created_at < window_until,
        ).group_by(OrderConsultation.type)
    )
    order_counts = {key: 0 for key in ("order", "consultation")}
    for raw_type, count in type_rows.all():
        key = raw_type.value if hasattr(raw_type, "value") else raw_type
        if key in order_counts:
            order_counts[key] = int(count)

    paid_rows = await session.execute(
        select(func.count()).select_from(OrderPayment).where(
            OrderPayment.created_at >= since, OrderPayment.created_at < window_until,
            OrderPayment.status == "paid"
        )
    )
    gateway_rows = await session.execute(
        select(func.count()).select_from(PaymentEventLog).where(
            PaymentEventLog.created_at >= since, PaymentEventLog.created_at < window_until,
        )
    )

    channels_rows = await session.execute(
        select(Customer.platform, func.count(distinct(ConversationMessage.customer_id)), func.count())
        .select_from(ConversationMessage)
        .join(Customer, Customer.id == ConversationMessage.customer_id)
        .where(
            ConversationMessage.created_at >= since,
            ConversationMessage.created_at < window_until,
            ConversationMessage.role == "user",
        )
        .group_by(Customer.platform)
    )
    channels = [
        (str(platform), int(customers), int(messages)) for platform, customers, messages in channels_rows.all()
    ]
    channels.sort(key=lambda item: (-item[2], item[0]))

    top_rows = await session.execute(
        select(ShopBot.bot_username, func.count(distinct(ConversationMessage.customer_id)), func.count())
        .select_from(ConversationMessage)
        .join(Customer, Customer.id == ConversationMessage.customer_id)
        .join(ShopBot, ShopBot.id == Customer.shop_bot_id)
        .where(
            ConversationMessage.created_at >= since,
            ConversationMessage.created_at < window_until,
            ConversationMessage.role == "user",
        )
        .group_by(ShopBot.id, ShopBot.bot_username)
        .order_by(func.count().desc(), ShopBot.id)
        .limit(5)
    )
    top_shops = [(str(username), int(customers), int(messages)) for username, customers, messages in top_rows.all()]

    series = _series(bucket_counts, start=since, bucket_minutes=bucket_minutes, count=bucket_count)
    peak_moment, peak_value = max(series, key=lambda item: item[1], default=(None, 0))
    if peak_value == 0:
        peak_moment = None
    span_seconds = max(1.0, (window_until - since).total_seconds())
    messages_per_minute = (int(messages_total or 0) / span_seconds) * 60.0

    peak_messages = await _peak_per_second(session, "messages", since, window_until)
    peak_ai = await _peak_per_second(session, "ai_requests", since, window_until)

    return {
        "range_key": range_key,
        "label": build_range_label(since, window_until) if custom else RANGE_LABELS.get(range_key, RANGE_LABELS["24h"]),
        "custom_range": custom,
        "since": since,
        "until": window_until,
        "span_hours": round(span_seconds / 3600.0, 1),
        "messages_per_minute": messages_per_minute,
        "channels": channels,
        "top_shops": top_shops,
        "bucket_minutes": bucket_minutes,
        "series": series,
        "peak_moment": peak_moment,
        "peak_customers": peak_value,
        "peak_messages_per_second": peak_messages,
        "peak_ai_requests_per_second": peak_ai,
        "active_now": active_now,
        "messages": int(messages_total or 0),
        "customers": int(customers_total or 0),
        "orders": order_counts["order"],
        "consultations": order_counts["consultation"],
        "payments_paid": int(paid_rows.scalar() or 0),
        "gateway_events": int(gateway_rows.scalar() or 0),
        "features": [(label, feature_counts.get(reason, 0)) for reason, label in FEATURE_LABELS],
    }


def build_range_label(since: dt.datetime, until: dt.datetime) -> str:
    from app.utils.jalali import format_jalali_datetime

    return f"{format_jalali_datetime(since)} تا {format_jalali_datetime(until)}"


def ai_concurrency_estimate(messages_per_minute: float, latency_seconds: float = 5.0) -> int:
    if messages_per_minute <= 0 or latency_seconds <= 0:
        return 0
    return math.ceil(messages_per_minute * latency_seconds / 60)


def sparkline(series: list[tuple[dt.datetime, int]]) -> str:
    """نوارِ متنیِ کوتاه؛ بدونِ فونتِ گرافیکی و بدونِ نویسهٔ بیگانه."""
    if not series:
        return "—"
    peak = max(value for _moment, value in series)
    if peak <= 0:
        return "".join("·" for _ in series)
    return "".join(_BARS[min(4, int(value * 5 / (peak + 0.0001)))] if value else "·" for _moment, value in series)
