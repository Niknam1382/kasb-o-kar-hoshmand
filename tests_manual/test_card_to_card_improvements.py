"""
تست: بهبودهای کارت‌به‌کارت — فرمتِ کپی‌سریع (parse_mode HTML) و مدیریتِ درست‌تر
وقتی فروشگاه‌دار به‌جای عکس، متن می‌فرسته.

اجرا: python3 tests_manual/test_card_to_card_improvements.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import shop_owner_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999901


async def _seed_owner() -> None:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        await shop_owner_service.complete_registration(session, owner, "خریدار", "کارت", "09120000009", "cc@example.com", True, True)
        admin_settings = await get_admin_settings(session)
        admin_settings.platform_card_number = "6037-9977-1234-5678"
        admin_settings.platform_card_holder_name = "محمدمهدی نیک‌نام"


async def test_card_instructions_use_html_code_formatting(main_dp) -> None:
    await reset_database()
    await _seed_owner()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="💰 کیف‌پول", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data="topup_start", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(3, data="topup_amount:50000", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(4, data="skip_discount", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(5, data="payment_method:card", user_id=OWNER_TG_ID))

    last_message = session_obj.sent_messages[-1]
    assert "<code>" in last_message["text"], "باید از تگِ <code> برای کپی‌سریع استفاده بشه"
    assert "6037-9977-1234-5678" in last_message["text"]
    print("✅ test_card_instructions_use_html_code_formatting PASSED")


async def test_sending_text_instead_of_photo_gets_guided(main_dp) -> None:
    await reset_database()
    await _seed_owner()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="💰 کیف‌پول", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data="topup_start", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(3, data="topup_amount:50000", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(4, data="skip_discount", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(5, data="payment_method:card", user_id=OWNER_TG_ID))

    # به‌جای عکس، متن می‌فرسته (یه اشتباهِ رایج)
    await main_dp.feed_update(main_bot, make_message_update(6, text="پرداخت کردم!", user_id=OWNER_TG_ID))

    assert any("عکسِ رسید" in m["text"] or "عکس رسید" in m["text"] for m in session_obj.sent_messages[-1:]), (
        "باید راهنمایی بشه که عکس بفرسته، نه اینکه بی‌جواب بمونه"
    )

    # حالا عکسِ درست رو می‌فرسته و باید عادی پردازش بشه
    await main_dp.feed_update(main_bot, make_message_update(7, photo=True, user_id=OWNER_TG_ID))
    assert any("بررسی" in m["text"] or "دریافت" in m["text"] for m in session_obj.sent_messages[-1:]), (
        "بعد از عکسِ درست باید تاییدِ دریافت نشون داده بشه"
    )

    print("✅ test_sending_text_instead_of_photo_gets_guided PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_card_instructions_use_html_code_formatting(main_dp)
    await test_sending_text_instead_of_photo_gets_guided(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
