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
from typing import Any

from sqlalchemy import Integer, cast, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    ConversationMessage,
    OrderConsultation,
    OrderPayment,
    PaymentEventLog,
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
    (WalletTransactionReason.CART_EDIT, "ویرایشِ سبد با AI"),
    (WalletTransactionReason.CRM_SUMMARY, "خلاصهٔ CRM"),
    (WalletTransactionReason.OWNER_ASSISTANT, "دستیارِ مدیریتی"),
)
_BARS = "▁▂▄▆█"


def _bucket_seconds(bucket_minutes: int) -> int:
    return bucket_minutes * 60


def _series(bucket_counts: dict[int, int], *, start: dt.datetime, bucket_minutes: int, count: int) -> list[tuple[dt.datetime, int]]:
    """دانه‌هایِ خالی را با صفر پر می‌کند تا نمودارِ متنی پیوسته بماند."""
    step = dt.timedelta(minutes=bucket_minutes)
    first_bucket = _epoch_bucket(start, bucket_minutes)
    return [(start + step * index, bucket_counts.get(first_bucket + index, 0)) for index in range(count)]


def _epoch_bucket(moment: dt.datetime, bucket_minutes: int) -> int:
    return int(moment.timestamp()) // _bucket_seconds(bucket_minutes)


async def build(session: AsyncSession, range_key: str = "24h", *, now: dt.datetime | None = None) -> dict[str, Any]:
    hours, bucket_minutes = RANGES[range_key]
    utc_now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    bucket_seconds = _bucket_seconds(bucket_minutes)
    bucket_count = int(hours * 3600 // bucket_seconds)
    # پنجره به مرزِ دانه کوک می‌شود، وگرنه دانهٔ جاری بیرونِ فهرست می‌افتد و بیشینه صفر خوانده می‌شود.
    current_bucket = int(utc_now.timestamp()) // bucket_seconds
    first_bucket = current_bucket - bucket_count + 1
    since = dt.datetime.fromtimestamp(first_bucket * bucket_seconds, dt.timezone.utc)
    start = since

    bucket_expr = cast(func.floor(func.extract("epoch", ConversationMessage.created_at) / bucket_seconds), Integer).label("bucket")
    rows = await session.execute(
        select(bucket_expr, func.count(distinct(ConversationMessage.customer_id)))
        .where(ConversationMessage.created_at >= since, ConversationMessage.role == "user")
        .group_by(bucket_expr)
    )
    bucket_counts = {int(bucket): int(customers) for bucket, customers in rows.all()}

    message_rows = await session.execute(
        select(func.count(), func.count(distinct(ConversationMessage.customer_id))).where(
            ConversationMessage.created_at >= since, ConversationMessage.role == "user"
        )
    )
    messages_total, customers_total = message_rows.one()

    now_rows = await session.execute(
        select(func.count(distinct(ConversationMessage.customer_id))).where(
            ConversationMessage.created_at >= utc_now - dt.timedelta(minutes=NOW_WINDOW_MINUTES),
            ConversationMessage.role == "user",
        )
    )
    active_now = int(now_rows.scalar() or 0)

    feature_rows = await session.execute(
        select(WalletTransaction.reason, func.count())
        .where(WalletTransaction.created_at >= since, WalletTransaction.reason.in_([reason for reason, _ in FEATURE_LABELS]))
        .group_by(WalletTransaction.reason)
    )
    feature_counts = {reason: int(count) for reason, count in feature_rows.all()}

    type_rows = await session.execute(
        select(OrderConsultation.type, func.count()).where(OrderConsultation.created_at >= since).group_by(OrderConsultation.type)
    )
    order_counts = {key: 0 for key in ("order", "consultation")}
    for raw_type, count in type_rows.all():
        key = raw_type.value if hasattr(raw_type, "value") else raw_type
        if key in order_counts:
            order_counts[key] = int(count)

    paid_rows = await session.execute(
        select(func.count()).select_from(OrderPayment).where(
            OrderPayment.created_at >= since, OrderPayment.status == "paid"
        )
    )
    gateway_rows = await session.execute(
        select(func.count()).select_from(PaymentEventLog).where(PaymentEventLog.created_at >= since)
    )

    series = _series(bucket_counts, start=start, bucket_minutes=bucket_minutes, count=bucket_count)
    peak_moment, peak_value = max(series, key=lambda item: item[1], default=(None, 0))

    return {
        "range_key": range_key,
        "label": RANGE_LABELS[range_key],
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


def sparkline(series: list[tuple[dt.datetime, int]]) -> str:
    """نوارِ متنیِ کوتاه؛ بدونِ فونتِ گرافیکی و بدونِ نویسهٔ بیگانه."""
    if not series:
        return "—"
    peak = max(value for _moment, value in series)
    if peak <= 0:
        return "".join("·" for _ in series)
    return "".join(_BARS[min(4, int(value * 5 / (peak + 0.0001)))] if value else "·" for _moment, value in series)
