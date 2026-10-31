"""
نمایشِ تاریخِ شمسی و ساعتِ تهران (فقط برایِ *نمایش* — ورودیِ تاریخ از کاربر
گرفته نمی‌شه، پس هیچ پارسِ تاریخِ شمسی‌ای اینجا نیست).

دیتابیس همه‌جا UTC نگه می‌داره؛ این ماژول فقط موقعِ نشون‌دادنِ تاریخِ کمپین به
فروشگاه‌دار/مشتری، اون رو به تاریخِ شمسی و ساعتِ تهران تبدیل می‌کنه.
"""
from __future__ import annotations

import datetime

# ایران از ۱۴۰۱ (۲۰۲۲) ساعتِ تابستانی نداره؛ تهران همیشه UTC+03:30 ـه.
TEHRAN_TZ = datetime.timezone(datetime.timedelta(hours=3, minutes=30))

JALALI_MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)

_DAYS_BEFORE_GREGORIAN_MONTH = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیلِ تاریخِ میلادی به شمسی (الگوریتمِ دوره‌ایِ ۳۳ساله؛ برایِ قرنِ جاری با
    تقویمِ رسمی یکیه — ۱ فروردینِ ۱۴۰۵ = ۲۰۲۶-۰۳-۲۱ و ۳۰ اسفندِ ۱۴۰۳ = ۲۰۲۵-۰۳-۲۰)."""
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621

    gy2 = gy + 1 if gm > 2 else gy
    days = (
        365 * gy
        + (gy2 + 3) // 4
        - (gy2 + 99) // 100
        + (gy2 + 399) // 400
        - 80
        + gd
        + _DAYS_BEFORE_GREGORIAN_MONTH[gm - 1]
    )
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365

    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd


def to_tehran(moment: datetime.datetime) -> datetime.datetime:
    """هر datetime ـی رو به ساعتِ تهران تبدیل می‌کنه (naive ها UTC فرض می‌شن)."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=datetime.timezone.utc)
    return moment.astimezone(TEHRAN_TZ)


def format_jalali_date(moment: datetime.datetime) -> str:
    """مثلاً «17 مهر 1405»."""
    local = to_tehran(moment)
    jy, jm, jd = gregorian_to_jalali(local.year, local.month, local.day)
    return f"{jd} {JALALI_MONTH_NAMES[jm - 1]} {jy}"


def format_jalali_datetime(moment: datetime.datetime) -> str:
    """مثلاً «17 مهر 1405، ساعت 17:35» (به وقتِ تهران)."""
    local = to_tehran(moment)
    return f"{format_jalali_date(moment)}، ساعت {local.hour:02d}:{local.minute:02d}"
