"""
تست: باگ #4 — وقتی فروشگاه‌دار وسطِ یه FSM (مثلاً منتظرِ واردکردنِ توکنِ ربات) گیر
کرده ولی روی یکی از دکمه‌های شناخته‌شده‌ی منو می‌زنه، باید state پاک بشه و دکمه
درست پردازش بشه — نه اینکه متنِ دکمه به‌عنوانِ ورودیِ همون state تفسیر بشه.

اجرا: python3 tests_manual/test_fsm_escape.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import shop_owner_service  # noqa: E402

OWNER_TG_ID = 888001


async def _seed_owner() -> None:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        await shop_owner_service.complete_registration(session, owner, "فروشنده", "تست", "09120000001", "owner2@example.com", True, True)


async def test_menu_button_escapes_stuck_token_state(main_dp) -> None:
    await reset_database()
    await _seed_owner()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    # مرحله ۱: فروشگاه‌دار وارد state ی «منتظرِ توکن ربات» می‌شه
    await main_dp.feed_update(main_bot, make_message_update(1, text="🔑 ثبت/ویرایش توکن ربات", user_id=OWNER_TG_ID))
    assert any("توکن" in m["text"] for m in session_obj.sent_messages), "درخواستِ توکن نمایش داده نشد"

    # مرحله ۲: به‌جای واردکردنِ توکن، رویِ یه دکمه‌ی دیگه‌ی منو می‌زنه (بدونِ اینکه
    # عملاً توکن رو کامل کنه) — این دقیقاً سناریوی باگِ FSM stuck هست
    before_count = len(session_obj.sent_messages)
    await main_dp.feed_update(main_bot, make_message_update(2, text="📦 محصولات", user_id=OWNER_TG_ID))
    after_messages = session_obj.sent_messages[before_count:]

    # باید بره سراغِ هندلرِ واقعیِ «محصولات» (که فروشگاه‌بات نداره، پس پیامِ
    # «فروشگاه‌بات تنظیم نشده» رو می‌بینه) — نه اینکه سعی کنه "📦 محصولات" رو
    # به‌عنوانِ توکنِ رباتِ نامعتبر پردازش کنه
    assert not any("نامعتبر" in m["text"] for m in after_messages), (
        "state نباید stuck بمونه: نباید متنِ دکمه به‌عنوانِ توکنِ نامعتبر رد بشه"
    )
    assert any("فروشگاه" in m["text"] or "بات" in m["text"] or "ربات" in m["text"] for m in after_messages), (
        "باید هندلرِ واقعیِ دکمه‌ی «محصولات» اجرا بشه"
    )

    print("✅ test_menu_button_escapes_stuck_token_state PASSED")


async def test_non_menu_text_still_treated_as_token_attempt(main_dp) -> None:
    """برای اطمینان از اینکه میدل‌ور بیش‌ازحد آزاد نیست: یه متنِ دلخواه (که دکمه‌ی
    شناخته‌شده نیست) باید همچنان طبقِ همون state (منتظرِ توکن) پردازش بشه."""
    await reset_database()
    await _seed_owner()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="🔑 ثبت/ویرایش توکن ربات", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="یه متنِ کاملاً دلخواه", user_id=OWNER_TG_ID))

    assert any("معتبر نیست" in m["text"] for m in session_obj.sent_messages[-1:]), (
        "متنِ غیرِ دکمه باید همچنان به‌عنوانِ تلاشِ نامعتبر برای توکن رد بشه (state نباید بی‌دلیل پاک بشه)"
    )
    print("✅ test_non_menu_text_still_treated_as_token_attempt PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_menu_button_escapes_stuck_token_state(main_dp)
    await test_non_menu_text_still_treated_as_token_attempt(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
