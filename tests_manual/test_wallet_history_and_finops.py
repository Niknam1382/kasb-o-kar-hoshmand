"""
تست: تاریخچه‌ی کیف‌پول برای فروشگاه‌دار + آمارِ مالیِ سبک برای ادمین.

اجرا: python3 tests_manual/test_wallet_history_and_finops.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import stats_service, wallet_service  # noqa: E402
from app.services.shop_owner_service import get_by_telegram_id  # noqa: E402

OWNER_TG_ID = 999601
SHOP_BOT_TG_ID = 999602


async def test_wallet_history_shows_recent_transactions(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        owner = await get_by_telegram_id(session, OWNER_TG_ID)
        transactions = await wallet_service.get_recent_transactions(session, owner.id)
        assert len(transactions) >= 1, "باید حداقل تراکنشِ شارژِ اولیه‌ی تست وجود داشته باشه"

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    await main_dp.feed_update(main_bot, make_callback_update(1, data="wallet_history", user_id=OWNER_TG_ID))

    assert any("تاریخچه" in m.get("text", "") for m in session_obj.sent_messages), "باید عنوانِ تاریخچه نشون داده بشه"

    print("✅ test_wallet_history_shows_recent_transactions PASSED")


async def test_platform_stats_include_wallet_economy() -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)

    async with session_scope() as session:
        stats = await stats_service.get_platform_stats(session)
        assert "total_wallet_consumed_toman" in stats
        assert "total_given_away_toman" in stats
        assert stats["total_given_away_toman"] >= 0

    print("✅ test_platform_stats_include_wallet_economy PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_wallet_history_shows_recent_transactions(main_dp)
    await test_platform_stats_include_wallet_economy()


if __name__ == "__main__":
    asyncio.run(main())
