"""
تست: گزارشِ شبانه (فازِ ۳، دومین زیربخش) — عمداً جدا از گزارشِ دوره‌ای/هفتگیِ
از‌قبل‌موجود (send_due_reports / periodic_report_frequency_days، که یه خلاصه‌ی
تجمعیِ سلامتِ کلی هر N روزه). این یکی هر روز سرِ یه ساعتِ مشخص (به‌وقتِ UTC)
فقط عددهایِ «امروز» رو می‌فرسته.

پوشش:
۱. قبل از رسیدنِ ساعتِ تنظیم‌شده: گزارش فرستاده نمی‌شه.
۲. بعدِ رسیدنِ ساعت: گزارش فرستاده می‌شه و شاملِ تعدادِ درستِ سفارش‌هایِ
   امروزه.
۳. چک‌کردنِ دوباره‌یِ همون روز (شبیه‌سازیِ تیکِ ۳۰-دقیقه‌ایِ بعدیِ زمان‌بند):
   دوباره فرستاده نمی‌شه.
۴. سوییچِ nightly_report_enabled=False: اصلاً هیچ‌چیزی فرستاده نمی‌شه.
۵. مسیرِ پنلِ ادمین: روشن/خاموش‌کردنِ سوییچ + تنظیمِ ساعت (با ردِّ عددِ
   خارج‌از‌بازه‌ی ۰ تا ۲۳).

نکته: به‌جایِ mock‌کردنِ ساعتِ واقعی، send_due_nightly_reports یه پارامترِ
اختیاریِ now می‌گیره (فقط برای تست — در اجرایِ واقعی همیشه None پاس داده
می‌شه) تا این تست‌ها به ساعتِ واقعیِ اجرا وابسته نباشن.

اجرا: python3 tests_manual/test_nightly_report.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import OrderType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import customer_service, order_service, report_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999801
SHOP_BOT_TG_ID = 999802
CUSTOMER_TG_ID = 999803

_NOON_UTC = datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc)


async def test_not_sent_before_configured_hour(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.nightly_report_hour_utc = 18  # بعدازظهرِ «الان»ِ تستی (۱۲) هنوز نرسیده

    async with session_scope() as session:
        await report_service.send_due_nightly_reports(session, main_bot, now=_NOON_UTC)

    assert len(main_bot.session.sent_messages) == 0, "قبل از رسیدنِ ساعتِ تنظیم‌شده نباید چیزی فرستاده بشه"
    print("✅ test_not_sent_before_configured_hour PASSED")


async def test_sent_once_when_due_then_not_duplicated_same_day(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.nightly_report_hour_utc = 0  # همیشه رسیده (ساعتِ واقعیِ الان همیشه >= صفره)

        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "سفارشِ امروز", 150_000)

    # نکته‌ی مهم (باگی که همینجا بود): created_atِ سفارشِ بالا از ساعتِ واقعیِ
    # سیستم میاد، نه از _NOON_UTCِ ثابتِ بالای فایل. برایِ اینکه پنجره‌ی «امروز»
    # واقعاً همون سفارش رو در بر بگیره، now رو همینجا و تازه می‌گیریم — نه یه
    # تاریخِ ثابتِ فرضی که هیچ ربطی به created_atِ واقعیِ ردیفِ بالا نداره.
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        await report_service.send_due_nightly_reports(session, main_bot, now=now)

    assert len(main_bot.session.sent_messages) == 1, f"دقیقاً یه گزارش باید فرستاده بشه؛ فرستاده‌شده: {len(main_bot.session.sent_messages)}"
    report_text = main_bot.session.sent_messages[0]["text"]
    assert "سفارش‌های جدید: ۱" in report_text, f"باید تعدادِ ۱ سفارشِ امروز رو نشون بده؛ متنِ گزارش: {report_text!r}"

    # شبیه‌سازیِ تیکِ ۳۰-دقیقه‌ایِ بعدیِ *همان روز*. چرا clamp لازم است: اگر ساعتِ واقعی به پایانِ
    # روزِ UTC نزدیک باشد، `now + ۳۰دقیقه` به روزِ بعد می‌افتد، «امروز» عوض می‌شود و گزارش دوباره
    # فرستاده می‌شود ⇒ این تست فقط در ۳۰ دقیقهٔ آخرِ شبِ UTC می‌شکست (نقصِ خودِ تست، نه کد).
    day_end = datetime.datetime.combine(now.date(), datetime.time(23, 59, 59), tzinfo=datetime.timezone.utc)
    later = min(now + datetime.timedelta(minutes=30), day_end)
    async with session_scope() as session:
        await report_service.send_due_nightly_reports(session, main_bot, now=later)

    assert len(main_bot.session.sent_messages) == 1, "توی همون روز نباید دوباره فرستاده بشه"
    print("✅ test_sent_once_when_due_then_not_duplicated_same_day PASSED")


async def test_disabled_toggle_prevents_sending(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.nightly_report_enabled = False
        admin_settings.nightly_report_hour_utc = 0

    async with session_scope() as session:
        await report_service.send_due_nightly_reports(session, main_bot, now=_NOON_UTC)

    assert len(main_bot.session.sent_messages) == 0, "وقتی خاموشه، نباید هیچ گزارشی فرستاده بشه"
    print("✅ test_disabled_toggle_prevents_sending PASSED")


async def test_admin_panel_toggle_and_hour_setting(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.nightly_report_enabled is True, "پیش‌فرض باید روشن باشه"

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_toggle_nightly_report", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.nightly_report_enabled is False, "بعدِ زدنِ دکمه باید خاموش بشه"

    await main_dp.feed_update(admin_bot, make_callback_update(2, data="admin_setting_edit:nightly_report_hour_utc", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="25", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.nightly_report_hour_utc == 18, "عددِ خارج‌از‌بازه (۲۵) نباید ذخیره بشه؛ باید همون پیش‌فرض بمونه"

    await main_dp.feed_update(admin_bot, make_callback_update(4, data="admin_setting_edit:nightly_report_hour_utc", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(5, text="0", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.nightly_report_hour_utc == 0, "صفر (نیمه‌شبِ UTC) باید عددِ معتبری باشه"

    print("✅ test_admin_panel_toggle_and_hour_setting PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_not_sent_before_configured_hour(main_bot)
    await test_sent_once_when_due_then_not_duplicated_same_day(main_bot)
    await test_disabled_toggle_prevents_sending(main_bot)
    await test_admin_panel_toggle_and_hour_setting(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
