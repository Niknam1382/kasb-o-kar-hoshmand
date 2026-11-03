"""
تست: P30 — «ادامهٔ سفارش با اعتبارِ صفر» + سقفِ بدهیِ کمیسیون

رفتارِ قبل: با صفرشدنِ موجودیِ کیف‌پول، رباتِ آن فروشگاه کاملاً می‌ایستاد (متنِ «این فروشگاه
فعلاً در دسترس نیست»). رفتارِ تازه: ادمین یکِ سوییچِ سراسری دارد؛ اگر روشن باشد فروش ادامه
می‌یابد و بدهیِ کمیسیون در `commission_receivables` جمع می‌شود — وقتی از سقفِ تعیین‌شده گذشت،
فقط سفارش و پرداختِ آنلاین می‌ایستند و چت باز می‌ماند.

اجرا: python3 tests_manual/run_one.py test_p30_zero_credit_orders.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import commission_receivable_service, order_access_service, shop_owner_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

ADMIN_TG_ID = 12345
OWNER_TG_ID = 999961
SHOP_BOT_TG_ID = 999962
CEILING_TOMAN = 200_000


async def _owner_id_of(shop_bot_id: int) -> int:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        return int(shop_bot.shop_owner_id)


async def _set_balance(owner_id: int, balance: int) -> None:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_id(session, owner_id)
        owner.wallet_balance_toman = balance
        await session.commit()


async def _set_settings(*, switch_on: bool, ceiling: int) -> None:
    async with session_scope() as session:
        settings = await get_admin_settings(session)
        settings.orders_allowed_when_wallet_empty = switch_on
        settings.commission_debt_ceiling_toman = ceiling
        await session.commit()


async def _add_debt(owner_id: int, amount: int, group_key: str) -> None:
    async with session_scope() as session:
        await commission_receivable_service.record(session, owner_id=owner_id, group_key=group_key, amount_toman=amount)
        await session.commit()


async def _state(shop_bot_id: int) -> str:
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        return await order_access_service.state_for_shop_bot(session, shop_bot)


async def test_zero_credit_with_switch_off_stops_everything(shop_bot_id: int, owner_id: int) -> None:
    await _set_balance(owner_id, 0)
    await _set_settings(switch_on=False, ceiling=0)
    state = await _state(shop_bot_id)
    assert state == order_access_service.NO_CREDIT
    assert order_access_service.chat_continues(state) is False, "با سوییچِ خاموش، رفتارِ قبلی دست‌نخورده می‌ماند"
    print("✅ test_zero_credit_with_switch_off_stops_everything PASSED")


async def test_positive_credit_never_sees_the_new_doors(shop_bot_id: int, owner_id: int) -> None:
    await _set_balance(owner_id, 900_000)
    await _set_settings(switch_on=False, ceiling=1)
    assert await _state(shop_bot_id) == order_access_service.ALLOWED, "با موجودیِ مثبت هیچ دری بسته نمی‌شود"
    print("✅ test_positive_credit_never_sees_the_new_doors PASSED")


async def test_switch_on_with_zero_credit_and_no_ceiling_keeps_selling(shop_bot_id: int, owner_id: int) -> None:
    await _set_balance(owner_id, 0)
    await _set_settings(switch_on=True, ceiling=0)
    await _add_debt(owner_id, 9_000_000, "p30-unlimited")
    assert await _state(shop_bot_id) == order_access_service.ALLOWED, "سقفِ ۰ یعنی بی‌سقف"
    print("✅ test_switch_on_with_zero_credit_and_no_ceiling_keeps_selling PASSED")


async def test_ceiling_stops_ordering_but_not_chat(shop_bot_id: int, owner_id: int) -> None:
    await _set_balance(owner_id, 0)
    await _set_settings(switch_on=True, ceiling=CEILING_TOMAN)
    await _add_debt(owner_id, CEILING_TOMAN, "p30-at-ceiling")
    assert await _state(shop_bot_id) == order_access_service.ALLOWED, "دقیقاً رویِ سقف هنوز مجاز است"
    await _add_debt(owner_id, 50_000, "p30-over-ceiling")
    state = await _state(shop_bot_id)
    assert state == order_access_service.DEBT_CEILING, "عبورِ از سقف باید سفارش/پرداخت را ببندد"
    assert order_access_service.chat_continues(state) is True, "چت باید باز بماند"
    print("✅ test_ceiling_stops_ordering_but_not_chat PASSED")


async def test_debt_is_scoped_to_its_own_shop(first_shop_bot_id: int, second_shop_bot_id: int) -> None:
    # سوییچ روشن و سقف ۲۰۰٬۰۰۰ است (تستِ قبل). فروشگاهِ اول از سقف گذشته، ولی فروشگاهِ دوم
    # که بدهیِ باز ندارد باید بتواند بفروشد ⇒ عددِ بدهی per-owner خوانده می‌شود، نه سراسری.
    assert await _state(first_shop_bot_id) == order_access_service.DEBT_CEILING
    assert await _state(second_shop_bot_id) == order_access_service.ALLOWED, (
        "بدهیِ فروشگاهِ دیگر نباید درِ فروشگاهِ بی‌بدهی را ببندد"
    )
    print("✅ test_debt_is_scoped_to_its_own_shop PASSED")


async def test_admin_switch_and_ceiling_from_panel(main_dp) -> None:
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_toggle_zero_credit_orders", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        settings = await get_admin_settings(session)
        assert settings.orders_allowed_when_wallet_empty is False, "در این تست با سوییچِ روشن شروع می‌کنیم ⇒ یکِ تپ خاموشش می‌کند"

    await main_dp.feed_update(main_bot, make_callback_update(2, data="admin_toggle_zero_credit_orders", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(
        main_bot, make_callback_update(3, data="admin_setting_edit:commission_debt_ceiling_toman", user_id=ADMIN_TG_ID)
    )
    await main_dp.feed_update(main_bot, make_message_update(21, text="350000", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        settings = await get_admin_settings(session)
        assert settings.orders_allowed_when_wallet_empty is True
        assert settings.commission_debt_ceiling_toman == 350_000, "سقف باید از پنل نوشته شود"

    await main_dp.feed_update(
        main_bot, make_callback_update(4, data="admin_setting_edit:commission_debt_ceiling_toman", user_id=ADMIN_TG_ID)
    )
    await main_dp.feed_update(main_bot, make_message_update(22, text="0", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        settings = await get_admin_settings(session)
        assert settings.commission_debt_ceiling_toman == 0, "۰ پذیرفته می‌شود (یعنی بی‌سقف)"

    await main_dp.feed_update(
        main_bot, make_callback_update(5, data="admin_setting_edit:commission_debt_ceiling_toman", user_id=ADMIN_TG_ID)
    )
    await main_dp.feed_update(main_bot, make_message_update(23, text="600000000", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        settings = await get_admin_settings(session)
        assert settings.commission_debt_ceiling_toman == 0, "بالایِ سقفِ مجاز (۵۰۰ میلیون) نباید نوشته شود"
    print("✅ test_admin_switch_and_ceiling_from_panel PASSED")


def test_customer_refusal_text_is_neutral() -> None:
    body = shop_texts.CHECKOUT_STOPPED_BY_DEBT
    assert "سفارش" in body and "پشتیبانی" in body
    for leaked in ("کمیسیون", "بدهی", "اعتبار", "تومان"):
        assert leaked not in body, f"عبارتِ «{leaked}» نباید به مشتری گفته شود"
    print("✅ test_customer_refusal_text_is_neutral PASSED")


async def main() -> None:
    # هر تستِ سیاست با فروشگاهِ خودش کار می‌کند، چون ردیف‌هایِ بدهی جمع می‌شوند و
    # سوییچ/سقف سراسری‌اند؛ فروشگاهِ مشترک = تستِ بعدی از بدهیِ تستِ قبلی آلوده می‌شود.
    await reset_database()
    shop_a = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner_a = await _owner_id_of(shop_a)
    await test_zero_credit_with_switch_off_stops_everything(shop_a, owner_a)
    await test_positive_credit_never_sees_the_new_doors(shop_a, owner_a)

    shop_b = await seed_usable_shop(OWNER_TG_ID + 1, SHOP_BOT_TG_ID + 1)
    await test_switch_on_with_zero_credit_and_no_ceiling_keeps_selling(shop_b, await _owner_id_of(shop_b))

    shop_c = await seed_usable_shop(OWNER_TG_ID + 2, SHOP_BOT_TG_ID + 2)
    owner_c = await _owner_id_of(shop_c)
    await _set_balance(owner_c, 0)
    await test_ceiling_stops_ordering_but_not_chat(shop_c, owner_c)

    shop_d = await seed_usable_shop(OWNER_TG_ID + 3, SHOP_BOT_TG_ID + 3)
    await _set_balance(await _owner_id_of(shop_d), 0)
    await test_debt_is_scoped_to_its_own_shop(shop_c, shop_d)

    test_customer_refusal_text_is_neutral()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_switch_and_ceiling_from_panel(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
