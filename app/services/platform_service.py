"""پلتفرمِ پیام‌رسانیِ یک رویداد — شناسه‌یِ عددیِ کاربر فقط داخلِ *یک* سرویس یکتاست.

فروشگاه‌ها می‌تونن هم‌زمان روی تلگرام، بله و اینستاگرام باشند (P49-الف). اگر کد موقعِ
خواندنِ «این آپدیت مالِ چه
فروشی/مشتری‌ای است» نفهمد از کدام سرویس آمده، دو آدمِ غریبه (یک تلگرامی و یک بله‌ای با عددِ
یکسان) به هم وصل می‌شن: سبد، تاریخچه‌یِ گفتگو و حتی بلاک مشترک. پس هر جایی که از
`bot` نتیجه می‌گیریم، پلتفرم هم از همان `bot` خوانده می‌شه.

علامت روی خودِ شیءِ Bot نشسته (`build_bot` در bale_bot_service؛ برایِ اینستاگرام
`bot.instagram_platform` در تست‌ها و شیءِ فرستنده‌یِ instagram_service) تا به رشته‌یِ آدرسِ داخلیِ
aiogram یا مقدارِ BALE_API_BASE در `.env` وابسته نباشیم.
"""

from __future__ import annotations

from aiogram import Bot

TELEGRAM = "telegram"
BALE = "bale"
# P49-الف: کانالِ سوم. رشته‌یِ «instagram» در ستونِ Customer.platform نوشته می‌شود ⇒ همان
# قاعدهٔ بالا: مشتریِ اینستاگرام با یکِ عددِ هم‌شکلِ مشتریِ تلگرام نباید یکِ ردیف بگیرد.
INSTAGRAM = "instagram"


def platform_of(bot: Bot | None) -> str:
    if getattr(bot, "instagram_platform", False):
        return INSTAGRAM
    return BALE if getattr(bot, "bale_platform", False) else TELEGRAM


def is_bale(bot: Bot | None) -> bool:
    return platform_of(bot) == BALE




def of_event(event) -> str:
    """پلتفرمِ یک Message/CallbackQuery — روی هر دو `.bot` هست، پس تک‌خطیِ همین کافی است."""
    return platform_of(getattr(event, "bot", None))
