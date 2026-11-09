"""کار با تاریخِ تقویمی (P22).

«ماه» در این محصول دو جا معنا دارد: مدتِ شارژِ کیف‌پول و مدتِ اشتراک. تا P22 اشتراک ماهِ
تقویمی بود ولی کیف‌پول `۳۰ × N` روز؛ یعنی «یکِ ماهِ» اعتبار در ماهِ ۳۱ روزه دو روز زودتر
می‌رسید و پیامِ انقضا با اشتراکِ همان فروشگاه نمی‌خواند. قاعدهٔ واحد اینجاست.
"""

from __future__ import annotations

import datetime

from dateutil.relativedelta import relativedelta


def add_months(moment: datetime.datetime, months: int) -> datetime.datetime:
    """`months` ماهِ تقویمی اضافه می‌کند و روزِ سرِ ماه را clamp می‌کند.

    ۳۱ فروردین + ۱ ماه ⇒ ۲۹/۳۰خرداد نه خطا؛ ۱۲ ماه از ۲۹ اسفندِ سالِ کبیسه ⇒ ۲۸ اسفند.
    منطقهٔ زمانیِ ورودی دست نمی‌خورد (aware می‌ماند)، چون جابِ انقضا رویِ UTC کار می‌کند.
    """
    return moment + relativedelta(months=int(months))


def add_validity_months(moment: datetime.datetime, months: int, month_length_days: int = 0) -> datetime.datetime:
    """P44 · موردِ ۵۱: «ماه» یا تقویمی است یا روزشمارِ دقیق — با عددِ پنلِ ادمین انتخاب می‌شود.

    `month_length_days` صفر (پیش‌فرض) ⇒ همان `add_months`ِ تقویمی، پس هیچ رفتارِ قبلی عوض نمی‌شود.
    ۳۰ یا ۳۱ ⇒ دقیقاً `months × day` روزِ ۲۴ ساعته (درخواستِ صریحِ مالکِ محصول: «۳۱ روز یعنی ۳۱
    تا ۲۴ ساعت کامل»). این تابع فقط در لحظهٔ **ساختنِ** شارژ/اشتراک صدا زده می‌شود؛ ردیف‌هایِ
    قدیمی انقضایِ ذخیره‌شدهٔ خودشان را نگه می‌دارند.
    """
    days = int(month_length_days or 0)
    if days <= 0:
        return add_months(moment, months)
    return moment + datetime.timedelta(days=days * int(months))
