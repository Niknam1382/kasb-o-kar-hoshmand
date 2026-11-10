from __future__ import annotations

from aiogram import Router

from app.bots.common.error_handler import on_handler_error
from app.bots.common.middlewares import ChannelGateMiddleware, IdentityRefreshMiddleware, MenuButtonEscapeMiddleware
from app.bots.main_bot.handlers import (
    accounting,
    admin,
    admin_inactive,
    admin_time,
    assistant,
    campaigns,
    catalog_b2,
    crm,
    instagram,
    orders_manage,
    knowledge,
    moderation_reports,
    order_ops,
    panel,
    payment_ops,
    products,
    profile,
    checkout_steps,
    consult_contacts,
    shop_prefs,
    shop_settings,
    start,
)

_KNOWN_MENU_BUTTONS = {
    "🧾 مدیریتِ سفارش‌ها (جاری)",  # W5 (پنلِ فروشگاه‌دارِ فروشگاهی)
    "⏱ اعتبار و زمان",  # W5 · K1–K4 (پنلِ ادمین)
    # پنل فروشگاه‌دار
    "🔑 ثبت/ویرایش توکن ربات",  # P42 · موردِ ۱: هوشمندسازیِ بله داخلِ همین بخش است، نه دکمهٔ منو
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
    "📞 پشتیبانی",
    "👤 پروفایل من",
    # این پنج‌تا (چهارتا از دکمه‌هایِ قدیمی‌تر + «کمپین‌ها») قبلاً توی این لیست نبودن — همون باگِ
    # کلاسِ «دکمه وسطِ FSM state درست escape نمی‌شه» (مثلاً زدنِ «📝 سوال‌هایِ چک‌اوتِ سبد»
    # وسطِ «دستور هوشمندسازی»، متنِ دکمه رو به‌عنوانِ ورودی ذخیره می‌کرد).
    "📣 پیام به مشتری‌ها",
    "📣 پیام به کاربران",  # P42 · موردِ ۳۳ (همان فعلِ پنلِ مشاوره‌ای با اسمِ درست)
    "⏰ ارسال‌هایِ زمان‌بندی‌شده",  # P21-D (F2)
    "💳 پرداختِ آنلاینِ سفارش‌ها",
    "📝 سوال‌هایِ چک‌اوتِ سبد",
    "🔀 نوعِ کسب‌وکار",
    "🗂 خدمات و بسته‌ها",
    "🎯 کمپین‌ها",
    # فازِ ۴: دکمه‌هایِ تازه‌یِ پنلِ فروشگاه‌دار (بند ۴۱: بدونِ اینجا، وسطِ FSM متنِ دکمه ذخیره می‌شد).
    "🧩 سوال‌هایِ بی‌جواب",
    "📚 پرسش‌وپاسخ‌هایِ تاییدشده",
    "👥 مشتری‌ها",
    "💬 گفتگوها و کاربران",  # P18 · C2 (پنلِ مشاوره‌ای)
    "🧮 حسابداری",
    "💬 دستیارِ مدیریتی",
    "⚙️ تنظیماتِ ربات فروشگاه",
    # P49-الف: دکمهٔ «🟣 اینستاگرام» فقط با سوئیچِ ادمین در منو می‌آید، ولی اینجا باید همیشه ثبت
    # باشد وگرنه وسطِ FSMِ متنِ خوشآمد، زدنِ دکمه متنش را به‌عنوانِ ورودی ذخیره می‌کند.
    "🟣 اینستاگرام",
    # پنل ادمین
    "📢 مدیریت کانال‌های اجباری",
    "🧾 صف تایید پرداخت‌ها",
    "💰 تنظیمات قیمت و تخفیف",
    "🔑 تنظیمات کلیدها",
    "📊 آمار سراسری",
    "📈 وضعیتِ همزمانی و عملکرد",  # P30
    "📣 پیام همگانی",
    "👥 مدیریت فروشگاه‌دارها",
    "🧹 کاربرانِ غیرفعال",  # P22 · مشکلِ ۸
    "🔑 استخرِ کلیدهایِ AI",
    # این دوتا (نگهبانِ محتوا، گزارشِ ممیزی) هیچ‌وقت به این لیست اضافه نشده
    # بودن — همون باگِ کلاسِ «دکمه وسطِ FSM state درست escape نمی‌شه»؛ حین
    # افزودنِ دکمه‌ی مدیریتِ ادمین‌ها اضافه شدن.
    "🛡 نگهبانِ محتوا",
    "📜 گزارشِ ممیزی",
    "👑 مدیریتِ ادمین‌ها",
    "📤 دفترِ کیف‌پول (اکسل)",
    "🧾 لاگِ سرور",  # P48 · موردِ ۱۳ (فقط سوپرادمین)
}


def build_main_router() -> Router:
    router = Router(name="main_bot")

    # P24: خطایِ هر هندلر (even KeyError/ValueError از callback_data دستکاری‌شده) باید لاگ شود و
    # یکِ بازخوردِ دیدنی بدهد؛ بی‌این هندلر، دکمه بی‌جواب می‌ماند و «هیچ کاری نمی‌کند» به‌نظر می‌رسد.
    router.errors.register(on_handler_error)

    # این باید outer_middleware باشه، نه middleware معمولی: چون aiogram قبل از
    # اینکه اصلاً handler رو بر اساسِ StateFilter انتخاب کنه، از یه مقدارِ کش‌شده
    # به اسمِ raw_state استفاده می‌کنه. middlewareِ معمولی بعد از انتخابِ handler
    # اجرا می‌شه، پس دیگه برای عوض کردنِ مسیر دیر شده. outer_middleware قبل از
    # انتخابِ handler اجرا می‌شه، پس می‌تونه واقعاً مسیر رو عوض کنه.
    router.message.outer_middleware(MenuButtonEscapeMiddleware(_KNOWN_MENU_BUTTONS))
    router.message.outer_middleware(IdentityRefreshMiddleware())
    router.callback_query.outer_middleware(IdentityRefreshMiddleware())

    gate = ChannelGateMiddleware()
    panel.router.message.middleware(gate)
    panel.router.callback_query.middleware(gate)
    order_ops.router.message.middleware(gate)
    order_ops.router.callback_query.middleware(gate)
    payment_ops.router.message.middleware(gate)
    payment_ops.router.callback_query.middleware(gate)
    products.router.message.middleware(gate)
    products.router.callback_query.middleware(gate)
    catalog_b2.router.message.middleware(gate)
    catalog_b2.router.callback_query.middleware(gate)
    campaigns.router.message.middleware(gate)
    campaigns.router.callback_query.middleware(gate)
    knowledge.router.message.middleware(gate)
    knowledge.router.callback_query.middleware(gate)
    accounting.router.message.middleware(gate)
    accounting.router.callback_query.middleware(gate)
    crm.router.message.middleware(gate)
    crm.router.callback_query.middleware(gate)
    assistant.router.message.middleware(gate)
    instagram.router.message.middleware(gate)
    instagram.router.callback_query.middleware(gate)
    shop_settings.router.message.middleware(gate)
    shop_settings.router.callback_query.middleware(gate)
    shop_prefs.router.message.middleware(gate)
    checkout_steps.router.message.middleware(gate)
    shop_prefs.router.callback_query.middleware(gate)
    checkout_steps.router.callback_query.middleware(gate)
    consult_contacts.router.message.middleware(gate)
    consult_contacts.router.callback_query.middleware(gate)
    profile.router.message.middleware(gate)
    profile.router.callback_query.middleware(gate)

    router.include_router(admin.router)
    router.include_router(admin.super_router)
    router.include_router(admin_inactive.router)  # P22 · مشکلِ ۸ (دستهٔ غیرفعال‌ها + حذفِ حساب؛ دامنه‌دار)
    router.include_router(admin_time.super_router)  # K3/K4: سوپرادمین اول؛ بعدش روترِ عمومی «غیرسوپر ⇒ پیامِ مودبانه»
    router.include_router(admin_time.router)
    router.include_router(profile.router)
    router.include_router(panel.router)
    router.include_router(order_ops.router)
    router.include_router(payment_ops.router)
    router.include_router(catalog_b2.router)
    router.include_router(products.router)
    router.include_router(campaigns.router)
    router.include_router(knowledge.router)
    router.include_router(accounting.router)
    router.include_router(crm.router)
    router.include_router(orders_manage.router)  # W5: «🧾 مدیریتِ سفارش‌ها (جاری)»
    router.include_router(assistant.router)
    router.include_router(shop_settings.router)
    router.include_router(shop_prefs.router)  # P18 · A5: مهلت‌ها و حافظه‌یِ per-shop
    router.include_router(checkout_steps.router)  # P18 · B9: گام‌هایِ پیش‌فرضِ چک‌اوت
    router.include_router(consult_contacts.router)  # P18 · C2: گفتگوها و کاربرانِ مشاوره
    router.include_router(moderation_reports.router)  # P43 · مواردِ ۱۰/۳۰/۳۱: گزارشِ نگهبانِ محتوا
    router.include_router(instagram.router)  # P49-الف: صفحهٔ «🟣 اینستاگرامِ» فروشگاه‌دار
    router.include_router(start.router)
    return router
