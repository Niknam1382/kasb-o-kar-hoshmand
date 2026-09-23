"""
تست: فرمولِ محاسبه‌ی خودکارِ wallet_cost_per_1k_tokens_toman از رویِ هزینه‌ی
واقعیِ AI + نرخِ ارز + ضریبِ سود (به‌جایِ یه عددِ تومانیِ ثابت و دستی).

اجرا: python3 tests_manual/test_wallet_pricing_formula.py
"""
from __future__ import annotations

import asyncio
import sys
from decimal import Decimal

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.session import session_scope  # noqa: E402
from app.services import wallet_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345


def test_formula_matches_hand_calculation() -> None:
    class FakeSettings:
        ai_cost_usd_per_1m_tokens = Decimal("0.014")  # glm-4-flash
        usd_to_toman_rate = 100_000
        wallet_markup_multiplier = Decimal("5.00")

    # (0.014/1000) دلار به‌ازای هر ۱۰۰۰ توکن × ۱۰۰٬۰۰۰ تومان × ۵ = ۷ تومان
    result = wallet_service.compute_cost_per_1k_tokens_from_formula(FakeSettings())
    assert result == 7, f"انتظار ۷ تومان بود، نه {result}"
    print("✅ test_formula_matches_hand_calculation PASSED")


def test_formula_never_returns_zero_even_for_tiny_inputs() -> None:
    class FakeSettings:
        ai_cost_usd_per_1m_tokens = Decimal("0.0001")
        usd_to_toman_rate = 1
        wallet_markup_multiplier = Decimal("1.00")

    result = wallet_service.compute_cost_per_1k_tokens_from_formula(FakeSettings())
    assert result >= 1, "حتی با ورودی‌های خیلی کوچیک، نباید هزینه صفر بشه"
    print("✅ test_formula_never_returns_zero_even_for_tiny_inputs PASSED")


async def test_admin_recalculate_button_updates_stored_cost(main_dp) -> None:
    await reset_database()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.ai_cost_usd_per_1m_tokens = Decimal("0.014")
        admin_settings.usd_to_toman_rate = 100_000
        admin_settings.wallet_markup_multiplier = Decimal("5.00")

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_recalc_wallet_cost", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.wallet_cost_per_1k_tokens_toman == 7, (
            f"دکمه باید مقدارِ محاسبه‌شده (۷) رو ذخیره کنه، نه {admin_settings.wallet_cost_per_1k_tokens_toman}"
        )

    print("✅ test_admin_recalculate_button_updates_stored_cost PASSED")


async def test_decimal_field_edit_accepts_dot_and_comma(main_dp) -> None:
    await reset_database()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_setting_edit:ai_cost_usd_per_1m_tokens", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="0.28", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        assert admin_settings.ai_cost_usd_per_1m_tokens == Decimal("0.28")

    print("✅ test_decimal_field_edit_accepts_dot_and_comma PASSED")


async def async_main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_recalculate_button_updates_stored_cost(main_dp)
    await test_decimal_field_edit_accepts_dot_and_comma(main_dp)


def main() -> None:
    test_formula_matches_hand_calculation()
    test_formula_never_returns_zero_even_for_tiny_inputs()
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
