"""
تست: مدیریتِ فروشگاه‌دارها توسط ادمین (تعلیق/رفعِ تعلیق) + قابلیتِ #7 (اعطای
اشتراکِ هدیه توسط ادمین).

نکته: کاربرِ ادمین در این تست‌ها آیدیِ ۱۲۳۴۵ داره، که باید با متغیرِ محیطیِ
ADMIN_TELEGRAM_IDS هنگامِ اجرا مچ بشه.

اجرا: python3 tests_manual/test_admin_owner_management.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.models import ShopBot, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import shop_bot_service, shop_owner_service  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999601


async def _seed_owner_with_shop_bot() -> tuple[int, int]:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        owner = await shop_owner_service.complete_registration(session, owner, "فروشگاه‌دار", "تست", "09120000005", "susp@example.com", True, True)
        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, "fake", 999602, "shop_test")
        shop_bot.encrypted_token = encrypt_token("999602:AAFakeTokenForTestingPurposesOnlyXYZ")
        await session.flush()
        return owner.id, shop_bot.id


async def test_admin_can_suspend_owner(main_dp) -> None:
    await reset_database()
    owner_id, shop_bot_id = await _seed_owner_with_shop_bot()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_suspend:{owner_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.is_active is False, "فروشگاه‌بات باید غیرفعال بشه"
        assert shop_bot.disabled_reason is not None, "دلیلِ غیرفعال‌سازی باید ثبت بشه"

    print("✅ test_admin_can_suspend_owner PASSED")


async def test_admin_can_unsuspend_owner(main_dp) -> None:
    await reset_database()
    owner_id, shop_bot_id = await _seed_owner_with_shop_bot()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.is_active = False
        shop_bot.disabled_reason = "برای تست"

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_unsuspend:{owner_id}", user_id=ADMIN_TG_ID))
    await asyncio.sleep(0.1)  # فرصت بده تسکِ پس‌زمینه‌ی register (که ما network اش رو نادیده می‌گیریم) شروع بشه

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.is_active is True, "فروشگاه‌بات باید دوباره فعال بشه"
        assert shop_bot.disabled_reason is None

    print("✅ test_admin_can_unsuspend_owner PASSED")


async def test_non_admin_cannot_suspend(main_dp) -> None:
    await reset_database()
    owner_id, shop_bot_id = await _seed_owner_with_shop_bot()
    non_admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(non_admin_bot, make_callback_update(1, data=f"admin_owner_suspend:{owner_id}", user_id=999999))

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.is_active is True, "کاربرِ غیرِادمین نباید بتونه فروشگاه‌بات رو تعلیق کنه"

    print("✅ test_non_admin_cannot_suspend PASSED")


async def test_admin_gift_wallet_credit(main_dp) -> None:
    await reset_database()
    owner_id, shop_bot_id = await _seed_owner_with_shop_bot()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_gift:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="150000", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 150_000, f"باید ۱۵۰٬۰۰۰ تومن به کیف‌پول اضافه بشه، نه {owner.wallet_balance_toman}"

    print("✅ test_admin_gift_wallet_credit PASSED")


async def test_admin_gift_invalid_amount_rejected(main_dp) -> None:
    await reset_database()
    owner_id, shop_bot_id = await _seed_owner_with_shop_bot()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_owner_gift:{owner_id}", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="منفی نیست ولی عدد هم نیست", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        owner = await session.get(ShopOwner, owner_id)
        assert owner.wallet_balance_toman == 0, "با ورودیِ نامعتبر نباید موجودی اضافه بشه"

    assert any("نامعتبر" in m["text"] or "عدد" in m["text"] for m in session_obj.sent_messages[-1:])
    print("✅ test_admin_gift_invalid_amount_rejected PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_admin_can_suspend_owner(main_dp)
    await test_admin_can_unsuspend_owner(main_dp)
    await test_non_admin_cannot_suspend(main_dp)
    await test_admin_gift_wallet_credit(main_dp)
    await test_admin_gift_invalid_amount_rejected(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
