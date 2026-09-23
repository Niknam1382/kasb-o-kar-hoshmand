"""
تست: مدیریتِ طرح‌های قیمت‌گذاری (اشتراک) توسط ادمین — افزودنِ طرحِ جدید، آپدیتِ
قیمتِ طرحِ موجود (به‌جای ساختِ طرحِ تکراری)، و فعال/غیرفعال کردن.

اجرا: python3 tests_manual/test_admin_pricing.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.models import SubscriptionPlan  # noqa: E402
from app.database.session import session_scope  # noqa: E402

ADMIN_TG_ID = 12345


async def test_admin_creates_new_plan(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_plan_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="1", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="250,000", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.duration_months == 1))
        plan = result.scalar_one_or_none()
        assert plan is not None, "طرحِ یک‌ماهه باید ساخته بشه"
        assert plan.price_toman == 250_000, f"قیمت: {plan.price_toman}"

    print("✅ test_admin_creates_new_plan PASSED")


async def test_admin_updates_existing_plan_price_instead_of_duplicating(main_dp) -> None:
    await reset_database()
    async with session_scope() as session:
        session.add(SubscriptionPlan(duration_months=6, price_toman=1_000_000, is_active=True))
        await session.commit()

    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_plan_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="6", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="1200000", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(SubscriptionPlan).where(SubscriptionPlan.duration_months == 6))
        plans = list(result.scalars().all())
        assert len(plans) == 1, f"نباید طرحِ تکراری ساخته بشه، تعداد: {len(plans)}"
        assert plans[0].price_toman == 1_200_000, "قیمتِ طرحِ موجود باید آپدیت بشه"

    print("✅ test_admin_updates_existing_plan_price_instead_of_duplicating PASSED")


async def test_admin_toggles_plan_active_status(main_dp) -> None:
    await reset_database()
    async with session_scope() as session:
        plan = SubscriptionPlan(duration_months=12, price_toman=2_000_000, is_active=True)
        session.add(plan)
        await session.flush()
        plan_id = plan.id

    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(admin_bot, make_callback_update(1, data=f"admin_plan_toggle:{plan_id}", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        plan = await session.get(SubscriptionPlan, plan_id)
        assert plan.is_active is False, "طرح باید غیرفعال بشه"

    await main_dp.feed_update(admin_bot, make_callback_update(2, data=f"admin_plan_toggle:{plan_id}", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        plan = await session.get(SubscriptionPlan, plan_id)
        assert plan.is_active is True, "با کلیکِ دوباره باید دوباره فعال بشه"

    print("✅ test_admin_toggles_plan_active_status PASSED")


async def test_invalid_price_input_rejected(main_dp) -> None:
    await reset_database()
    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(admin_bot, make_callback_update(1, data="admin_plan_add", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(2, text="1", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(admin_bot, make_message_update(3, text="منفی نیست ولی عدد هم نیست", user_id=ADMIN_TG_ID))

    async with session_scope() as session:
        result = await session.execute(select(SubscriptionPlan))
        assert len(list(result.scalars().all())) == 0, "با قیمتِ نامعتبر نباید طرحی ساخته بشه"

    assert any("نامعتبر" in m["text"] or "عدد" in m["text"] for m in session_obj.sent_messages[-1:])
    print("✅ test_invalid_price_input_rejected PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_admin_creates_new_plan(main_dp)
    await test_admin_updates_existing_plan_price_instead_of_duplicating(main_dp)
    await test_admin_toggles_plan_active_status(main_dp)
    await test_invalid_price_input_rejected(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
