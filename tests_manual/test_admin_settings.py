"""
تست: منویِ تنظیماتِ ادمین — ذخیره‌ی فیلدهای متنی (کلیدهای API)، فیلدهای عددی
(محدودیت‌ها)، و فیلدهای متنیِ قابل‌خالی‌کردن (پرامپتِ سراسری - قابلیتِ #4، لینکِ
کانالِ معرف - قابلیتِ #1).

اجرا: python3 tests_manual/test_admin_settings.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345


async def test_save_text_field_ai_api_key(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_setting_edit:ai_api_key", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="sk-test-1234567890", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.ai_api_key == "sk-test-1234567890"

    print("✅ test_save_text_field_ai_api_key PASSED")


async def test_save_int_field_knowledge_limit(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_setting_edit:knowledge_items_limit", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="25", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.knowledge_items_limit == 25

    print("✅ test_save_int_field_knowledge_limit PASSED")


async def test_invalid_int_field_rejected(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_setting_edit:knowledge_items_limit", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="منفیه: -5", user_id=ADMIN_TG_ID))

    assert any("نامعتبر" in m["text"] or "عدد" in m["text"] for m in session_obj.sent_messages[-1:])
    print("✅ test_invalid_int_field_rejected PASSED")


async def test_nullable_field_global_prompt_set_and_cleared(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    # مرحله ۱: تنظیمِ پرامپتِ سراسری (قابلیتِ #4)
    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_setting_edit:global_ai_system_prompt", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="همیشه مودب و کوتاه جواب بده.", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.global_ai_system_prompt == "همیشه مودب و کوتاه جواب بده."

    # مرحله ۲: پاک کردنش با فرستادنِ «خالی»
    await main_dp.feed_update(admin_bot, make_callback_update(3, data="admin_setting_edit:global_ai_system_prompt", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(4, text="خالی", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.global_ai_system_prompt is None, "با فرستادنِ «خالی» باید مقدار None بشه، نه رشته‌ی «خالی»"

    print("✅ test_nullable_field_global_prompt_set_and_cleared PASSED")


async def test_reference_channel_link_setting(main_dp) -> None:
    """قابلیتِ #1: لینکِ کانالِ ارجاعی که در متنِ پیشنهادِ آزمایشی استفاده می‌شه."""
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_setting_edit:reference_channel_link", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="https://t.me/kasbokar_channel", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.reference_channel_link == "https://t.me/kasbokar_channel"

    print("✅ test_reference_channel_link_setting PASSED")


async def test_wallet_pricing_fields_are_editable(main_dp) -> None:
    """اطمینان از اینکه فیلدهای قیمت‌گذاریِ کیف‌پول (که این‌جلسه به منوی تنظیمات
    اضافه شدن) واقعاً از طریقِ همون فلوی عمومیِ ویرایشِ تنظیمات قابل‌تغییرن."""
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    fields_and_values = [
        ("wallet_cost_per_1k_tokens_toman", "80"),
        ("wallet_cost_photo_analysis_toman", "650"),
        ("wallet_trial_credit_toman", "75000"),
        ("wallet_low_balance_warning_toman", "30000"),
    ]
    for i, (field, value) in enumerate(fields_and_values):
        await main_dp.feed_update(admin_bot, make_callback_update(i * 2 + 1, data=f"admin_setting_edit:{field}", user_id=ADMIN_TG_ID))
        await main_dp.feed_update(admin_bot, make_message_update(i * 2 + 2, text=value, user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.wallet_cost_per_1k_tokens_toman == 80
        assert admin_settings.wallet_cost_photo_analysis_toman == 650
        assert admin_settings.wallet_trial_credit_toman == 75_000
        assert admin_settings.wallet_low_balance_warning_toman == 30_000

    print("✅ test_wallet_pricing_fields_are_editable PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_save_text_field_ai_api_key(main_dp)
    await test_save_int_field_knowledge_limit(main_dp)
    await test_invalid_int_field_rejected(main_dp)
    await test_nullable_field_global_prompt_set_and_cleared(main_dp)
    await test_reference_channel_link_setting(main_dp)
    await test_wallet_pricing_fields_are_editable(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
