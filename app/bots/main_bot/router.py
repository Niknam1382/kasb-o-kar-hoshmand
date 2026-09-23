from __future__ import annotations

from aiogram import Router

from app.bots.common.middlewares import ChannelGateMiddleware, MenuButtonEscapeMiddleware
from app.bots.main_bot.handlers import admin, panel, products, start

_KNOWN_MENU_BUTTONS = {
    # پنل فروشگاه‌دار
    "🔑 ثبت/ویرایش توکن ربات",
    "📦 محصولات",
    "🧠 دستور هوشمندسازی",
    "📢 کانال دانش‌افزایی",
    "👀 پیش‌نمایش ربات",
    "📊 آمار",
    "💰 کیف‌پول",
    "🎁 کد معرف",
    "🧾 تاریخچه‌ی پرداخت",
    "📤 خروجی اکسل",
    "✏️ ویرایش اطلاعات",
    "👤 پروفایل من",
    # پنل ادمین
    "📢 مدیریت کانال‌های اجباری",
    "🧾 صف تایید پرداخت‌ها",
    "💰 تنظیمات قیمت و تخفیف",
    "🔑 تنظیمات کلیدها",
    "📊 آمار سراسری",
    "📣 پیام همگانی",
    "👥 مدیریت فروشگاه‌دارها",
    "🔑 استخرِ کلیدهایِ AI",
    # این دوتا (نگهبانِ محتوا، گزارشِ ممیزی) هیچ‌وقت به این لیست اضافه نشده
    # بودن — همون باگِ کلاسِ «دکمه وسطِ FSM state درست escape نمی‌شه»؛ حین
    # افزودنِ دکمه‌ی مدیریتِ ادمین‌ها اضافه شدن.
    "🛡 نگهبانِ محتوا",
    "📜 گزارشِ ممیزی",
    "👑 مدیریتِ ادمین‌ها",
}


def build_main_router() -> Router:
    router = Router(name="main_bot")

    # این باید outer_middleware باشه، نه middleware معمولی: چون aiogram قبل از
    # اینکه اصلاً handler رو بر اساسِ StateFilter انتخاب کنه، از یه مقدارِ کش‌شده
    # به اسمِ raw_state استفاده می‌کنه. middlewareِ معمولی بعد از انتخابِ handler
    # اجرا می‌شه، پس دیگه برای عوض کردنِ مسیر دیر شده. outer_middleware قبل از
    # انتخابِ handler اجرا می‌شه، پس می‌تونه واقعاً مسیر رو عوض کنه.
    router.message.outer_middleware(MenuButtonEscapeMiddleware(_KNOWN_MENU_BUTTONS))

    gate = ChannelGateMiddleware()
    panel.router.message.middleware(gate)
    panel.router.callback_query.middleware(gate)
    products.router.message.middleware(gate)
    products.router.callback_query.middleware(gate)

    router.include_router(admin.router)
    router.include_router(admin.super_router)
    router.include_router(panel.router)
    router.include_router(products.router)
    router.include_router(start.router)
    return router
