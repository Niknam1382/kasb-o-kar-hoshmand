"""
تست: P18 · A6 — حذفِ UIِ «طرح‌های اشتراک» از «💰 تنظیمات قیمت و تخفیف».

پوشش:
۱. هیچ دکمه/کالبک/حالتِ FSM/متنی برایِ طرح‌هایِ اشتراک در پنلِ ادمین نمانده و کالبک‌هایِ قدیمی بی‌اثرند.
۲. داده دست‌نخورده: جدولِ `subscription_plans` و `subscription_plan_service` کامل کار می‌کنند.
۳. بقیه‌یِ همین منو (کدهای تخفیف) سرِ جایش است و جریانِ ساختِ کد تخفیف هنوز کار می‌کند.

اجرا: python3 tests_manual/test_admin_pricing.py
"""
from __future__ import annotations

import asyncio
import pathlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot.states import AdminPricingStates  # noqa: E402
from app.database.models import DiscountCode, SubscriptionPlan  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import subscription_plan_service  # noqa: E402

ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


def _labels(markup) -> list[str]:
    return [b.text for row in markup.inline_keyboard for b in row] if markup else []


# ============================================================================= ۱ — UI حذف شده
async def test_subscription_plans_ui_removed(main_dp) -> None:
    await reset_database()

    menu = keyboards.admin_pricing_menu_keyboard()
    assert not any("اشتراک" in label for label in _labels(menu)), _labels(menu)
    assert "admin_pricing_plans" not in _datas(menu) and "admin_plan_add" not in _datas(menu), _datas(menu)
    assert "admin_pricing_discounts" in _datas(menu), "فقط UIِ طرح‌ها حذف شد، نه بقیه‌یِ منو"

    for name in ("admin_plans_list_keyboard",):
        assert not hasattr(keyboards, name), name
    for name in ("ADMIN_ASK_PLAN_DURATION", "ADMIN_ASK_PLAN_PRICE", "admin_plan_saved"):
        assert not hasattr(texts, name), name
    for name in ("waiting_plan_duration", "waiting_plan_price"):
        assert not hasattr(AdminPricingStates, name), name

    admin_source = pathlib.Path("app/bots/main_bot/handlers/admin.py").read_text(encoding="utf-8")
    assert "subscription_plan_service" not in admin_source, "هندلرِ ادمین نباید دیگر سرویسِ طرح‌ها را صدا بزند"

    # کالبک‌هایِ قدیمی/کهنه بی‌اثرند: نه پیامی می‌رود، نه ردیفی ساخته می‌شود
    admin_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]
    n = 0
    for data in ("admin_pricing_plans", "admin_plan_add", "admin_plan_toggle:1"):
        n += 1
        await main_dp.feed_update(admin_bot, make_callback_update(n, data=data, user_id=ADMIN_TG_ID))
    n += 1
    await main_dp.feed_update(admin_bot, make_message_update(n, text="3", user_id=ADMIN_TG_ID))
    assert session_obj.sent_messages == [], session_obj.sent_messages
    async with session_scope() as session:
        assert list((await session.execute(select(SubscriptionPlan))).scalars().all()) == []

    print("✅ test_subscription_plans_ui_removed PASSED")


# ============================================================================= ۲ — داده و سرویس سالم
async def test_plan_table_and_service_intact() -> None:
    await reset_database()
    async with session_scope() as session:
        await subscription_plan_service.create_plan(session, 6, 1_000_000)
        plans = await subscription_plan_service.get_all_plans(session)
        assert len(plans) == 1 and plans[0].duration_months == 6

        existing = await subscription_plan_service.get_by_duration(session, 6)
        assert existing is not None
        await subscription_plan_service.update_price(session, existing, 900_000)
        await subscription_plan_service.toggle_plan_active(session, existing.id)

    async with session_scope() as session:
        rows = list((await session.execute(select(SubscriptionPlan))).scalars().all())
        assert len(rows) == 1 and rows[0].price_toman == 900_000 and rows[0].is_active is False

    print("✅ test_plan_table_and_service_intact PASSED")


# ============================================================================= ۳ — تخفیف‌ها سرِ جایشان
async def test_pricing_menu_still_opens_discounts(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_pricing_menu", user_id=ADMIN_TG_ID))
    assert "admin_pricing_discounts" in _datas(session_obj.edited_texts[-1]["reply_markup"])

    await main_dp.feed_update(admin_bot, make_callback_update(2, data="admin_pricing_discounts", user_id=ADMIN_TG_ID))
    assert "admin_discount_add" in _datas(session_obj.edited_texts[-1]["reply_markup"])

    await main_dp.feed_update(admin_bot, make_callback_update(3, data="admin_discount_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(4, text="MEHR10", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_callback_update(5, data="discount_type:percent", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(6, text="10", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(7, text="نامحدود", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        code = (await session.execute(select(DiscountCode).where(DiscountCode.code == "MEHR10"))).scalar_one_or_none()
        assert code is not None and code.max_uses is None and code.is_active is True

    # ورودیِ نامعتبر هنوز رد می‌شود
    await main_dp.feed_update(admin_bot, make_callback_update(8, data="admin_discount_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(9, text="bad code!", user_id=ADMIN_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == texts.ADMIN_DISCOUNT_CODE_INVALID
    async with session_scope() as session:
        assert len(list((await session.execute(select(DiscountCode))).scalars().all())) == 1

    print("✅ test_pricing_menu_still_opens_discounts PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_subscription_plans_ui_removed(main_dp)
    await test_plan_table_and_service_intact()
    await test_pricing_menu_still_opens_discounts(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
