"""
تست: سوییچ‌های اضطراری/کنترلیِ پلتفرم (بخشِ ۲ مسترپرامپت).

اجرا: python3 tests_manual/test_kill_switches.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.database.models import ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

NEW_USER_ID = 999901
EXISTING_OWNER_TG_ID = 999902
SHOP_BOT_TG_ID = 999903
ADMIN_TG_ID = 12345


async def test_registration_closed_blocks_new_user_only(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(EXISTING_OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.allow_new_registrations = False

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="/start", user_id=NEW_USER_ID))
    assert any("بسته" in m["text"] for m in session_obj.sent_messages), "پیامِ بستنِ ثبت‌نام برای کاربرِ تازه دیده نشد"
    assert not any("بنویس" in m["text"] for m in session_obj.sent_messages), "نباید سوالِ نام (ASK_FIRST_NAME) پرسیده بشه"

    async with session_scope() as session:
        result = await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == NEW_USER_ID))
        assert result.scalar_one_or_none() is None, "نباید ردیفی برای کاربرِ تازه ساخته بشه"

    session_obj.sent_messages.clear()
    await main_dp.feed_update(main_bot, make_message_update(2, text="/start", user_id=EXISTING_OWNER_TG_ID))
    assert not any("بسته" in m["text"] for m in session_obj.sent_messages), "کاربرِ موجود نباید پیامِ بستنِ ثبت‌نام رو ببینه"

    print("✅ test_registration_closed_blocks_new_user_only PASSED")


async def test_wallet_topups_disabled_blocks_topup_start(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(EXISTING_OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.allow_wallet_topups = False

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="topup_start", user_id=EXISTING_OWNER_TG_ID))
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    assert not any("مبلغ" in m.get("text", "") for m in session_obj.sent_messages), "نباید صفحه‌ی انتخابِ مبلغ نشون داده بشه"

    print("✅ test_wallet_topups_disabled_blocks_topup_start PASSED")


async def test_maintenance_mode_blocks_customer_messages(shop_dp) -> None:
    await reset_database()
    await seed_usable_shop(EXISTING_OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.maintenance_mode = True

    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    session_obj: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="سلام", user_id=555111))

    assert any("تعمیر" in m["text"] or "به‌روزرسانی" in m["text"] for m in session_obj.sent_messages), "پیامِ حالتِ تعمیر دیده نشد"

    print("✅ test_maintenance_mode_blocks_customer_messages PASSED")


async def test_admin_toggle_handlers(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(EXISTING_OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.allow_new_registrations is True
        assert admin_settings.allow_wallet_topups is True
        assert admin_settings.maintenance_mode is False

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_toggle_registrations", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data="admin_toggle_topups", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(3, data="admin_toggle_maintenance", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.allow_new_registrations is False
        assert admin_settings.allow_wallet_topups is False
        assert admin_settings.maintenance_mode is True

    print("✅ test_admin_toggle_handlers PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_registration_closed_blocks_new_user_only(main_dp)
    await test_wallet_topups_disabled_blocks_topup_start(main_dp)
    await test_maintenance_mode_blocks_customer_messages(shop_dp)
    await test_admin_toggle_handlers(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
