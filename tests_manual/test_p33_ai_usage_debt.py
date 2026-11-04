"""
تست: P33-C — مصرفِ AIِ پرداخت‌نشده بدهی می‌شود و سقفِ بدهی را می‌گیرد

قاعده‌ای که این فایل قفل می‌کند:
۱. با سوییچِ «ادامهٔ سفارش با اعتبارِ صفر» **خاموش**، کسرِ ناموفق هیچ بدهی نمی‌سازد
۲. با سوییچِ **روشن**، هر کسرِ ناموفقِ مربوطِ مصرفِ AI یکِ ردیفِ بدهیِ باز می‌سازد
۳. `evaluate()` سقف را با مجموعِ کمیسیون + AI می‌سنجد (بدهیِ AI به‌تنهایی هم فروشگاه را
   از سقف رد می‌کند — وگرنه سوییچِ اعتبارِ صفر راهِ فرارِ بی‌سقف از هزینهٔ AI بود)
۴. `waive` ردیف را نمی‌هد؛ فقط وضعیت را عوض می‌کند

اجرا: python3 tests_manual/run_one.py test_p33_ai_usage_debt.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import func, select, update  # noqa: E402

from harness import FakeSession, reset_database  # noqa: E402

from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import AiUsageDebt, ShopBot, WalletCharge, WalletTransactionReason  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, ai_debt_service, order_access_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 999421
SHOP_BOT_TG_ID = 999422


async def _owner_and_settings(switch_on: bool, ceiling: int):
    async with session_scope() as session:
        settings = await admin_settings_service.get_admin_settings(session)
        settings.orders_allowed_when_wallet_empty = switch_on
        settings.commission_debt_ceiling_toman = ceiling
        await session.commit()


async def _owner_of(shop_bot_id: int):
    async with session_scope() as session:
        bot = await session.get(ShopBot, shop_bot_id)
        return await shop_owner_service.get_by_id(session, bot.shop_owner_id)


async def _zero_balance(owner_id: int):
    """موجودی را صفر می‌کند و نسخهٔ تازهٔ owner را برمی‌گرداند (evaluate آن را می‌خواند)."""
    async with session_scope() as session:
        fresh = await shop_owner_service.get_by_id(session, owner_id)
        fresh.wallet_balance_toman = 0
        await session.commit()
    async with session_scope() as session:
        return await shop_owner_service.get_by_id(session, owner_id)


async def _debt_rows() -> int:
    async with session_scope() as session:
        return int(await session.scalar(select(func.count()).select_from(AiUsageDebt)) or 0)


async def test_record_totals_and_waive() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = await _owner_of(shop_bot_id)

    async with session_scope() as session:
        assert await ai_debt_service.record(session, owner_id=owner.id, amount_toman=0, reason="chat_message") is None
        assert await ai_debt_service.record(session, owner_id=owner.id, amount_toman=-500, reason="chat_message") is None
        key = await ai_debt_service.record(
            session, owner_id=owner.id, amount_toman=1200, reason="chat_message", note="مصرفِ AI با اعتبارِ صفر"
        )
        assert key, "درجِ معتبر باید کلیدِ ایدبمپوتنسی بدهد"
        await session.commit()

    assert await _debt_rows() == 1
    async with session_scope() as session:
        assert await ai_debt_service.open_total_for_owner(session, owner.id) == 1200
        assert (await ai_debt_service.summary(session))["open_count"] == 1
        row_id = int((await session.scalar(select(AiUsageDebt.id))) or 0)
        assert await ai_debt_service.waive(session, debt_id=row_id, note="تصمیمِ ادمین") is True
        await session.commit()
    async with session_scope() as session:
        assert await ai_debt_service.open_total_for_owner(session, owner.id) == 0
        assert (await ai_debt_service.summary(session))["waived_count"] == 1
        assert await ai_debt_service.waive(session, debt_id=row_id, note="دوباره") is False
    assert await _debt_rows() == 1, "بخشودن نباید ردیف را حذف کند (سابقه می‌ماند)"
    print("✅ test_record_totals_and_waive PASSED")


async def test_ceiling_counts_ai_debt_not_only_commission() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)
    owner = await _owner_of(shop_bot_id)
    await _owner_and_settings(switch_on=True, ceiling=10_000)
    owner = await _zero_balance(owner.id)

    async with session_scope() as session:
        assert await order_access_service.evaluate(session, owner, await admin_settings_service.get_admin_settings(session)) == order_access_service.ALLOWED
        await ai_debt_service.record(session, owner_id=owner.id, amount_toman=4_000, reason="chat_message")
        await session.commit()
    async with session_scope() as session:
        assert await order_access_service.evaluate(session, owner, await admin_settings_service.get_admin_settings(session)) == order_access_service.ALLOWED, (
            "۴٬۰۰۰ بدهیِ AI زیرِ سقفِ ۱۰٬۰۰۰ نباید جلویِ فروش را بگیرد"
        )
        await ai_debt_service.record(session, owner_id=owner.id, amount_toman=7_000, reason="photo_analysis")
        await session.commit()

    async with session_scope() as session:
        state = await order_access_service.evaluate(session, owner, await admin_settings_service.get_admin_settings(session))
    assert state == order_access_service.DEBT_CEILING, (
        "مجموعِ ۱۱٬۰۰۰ از سقفِ ۱۰٬۰۰۰ رد شده و باید فقط دکمه‌هایِ سفارش/پرداخت را ببندد"
    )
    assert order_access_service.chat_continues(state) is True, "چت باید باز بماند"
    print("✅ test_ceiling_counts_ai_debt_not_only_commission PASSED")


async def test_deduct_failure_records_debt_only_with_the_switch() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2)
    owner = await _owner_of(shop_bot_id)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    async def _try(switch_on: bool) -> None:
        await _owner_and_settings(switch_on=switch_on, ceiling=0)
        async with session_scope() as session:
            # کسر از «بسته‌هایِ شارژ» انجام می‌شود، نه از عددِ کش‌شده ⇒ برایِ ناموفق‌شدنِ واقعی
            # باید ماندهٔ بسته‌ها صفر شود (وگرنه کسر موفق است و بدهی‌ای ثبت نمی‌شود).
            await session.execute(
                update(WalletCharge).where(WalletCharge.shop_owner_id == owner.id).values(remaining_toman=0)
            )
            fresh = await shop_owner_service.get_by_id(session, owner.id)
            fresh.wallet_balance_toman = 0
            settings = await admin_settings_service.get_admin_settings(session)
            await customer_handlers._deduct_and_notify(
                session, fresh, settings, 800, WalletTransactionReason.CHAT_MESSAGE, main_bot
            )
            await session.commit()

    await _try(switch_on=False)
    assert await _debt_rows() == 0, "با سوییچِ خاموش هیچ بدهیِ AI ثبت نمی‌شود (رفتارِ امروز)"
    await _try(switch_on=True)
    assert await _debt_rows() == 1, "با سوییچِ روشن همان هزینهٔ پرداخت‌نشده بدهی می‌شود"
    async with session_scope() as session:
        row = (await session.execute(select(AiUsageDebt))).scalar_one()
        assert row.amount_toman == 800 and row.reason == "chat_message" and row.status == "open", row
    print("✅ test_deduct_failure_records_debt_only_with_the_switch PASSED")


async def main() -> None:
    await test_record_totals_and_waive()
    await test_ceiling_counts_ai_debt_not_only_commission()
    await test_deduct_failure_records_debt_only_with_the_switch()


if __name__ == "__main__":
    asyncio.run(main())
