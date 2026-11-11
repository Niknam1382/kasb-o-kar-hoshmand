"""گزارشِ همزمانیِ مشتریان و عملکردِ ربات در بازه‌یِ زمانی (P30).

چرا: ادمین تا امروز فقط «آمار سراسری» داشت که شمارشِ کلِ تاریخچه است. برایِ تصمیمِ ظرفیت
باید دید *چه ساعتی* چند مشتری هم‌زمان فعال‌اند و کدام قابلیتِ ربات در همان بازه کار کرده.

دو بازه (درخواستِ کاربر: هر دو، با دکمهٔ انتخابِ بازه):
* `24h` — ۲۴ ساعت گذشته با دانهٔ ۱۰ دقیقه (۱۴۴ دانه)
* `7d`  — ۷ روز گذشته با دانهٔ ۶۰ دقیقه (۱۶۸ دانه)

فقط‌خواندنی است و هیچ سطری نمی‌نویسد. همزمانی = «چند مشتریِ متمایز در آن دانه پیام داده‌اند» —
نمایندهٔ سِشنِ بازِ تلگرام نیست (تلگرام آن را نمی‌دهد)، ولی همان چیزی است که بارِ واقعیِ AI و
دیتابیس را می‌سازد.

کوئری‌ها: سه aggregate (دانه‌ها، شمارشِ قابلیت‌ها، شمارشِ سفارش/مشاوره/پرداخت) — بدونِ حلقهٔ
per-shop، چون در ۵۰۰ فروشگاه همان اشتباهِ P29 تکرار می‌شد.
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
