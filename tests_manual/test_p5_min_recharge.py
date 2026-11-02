"""
تست‌هایِ PHASE 5A — کمترینِ مبلغِ «شارژِ کیف‌پول» (پیش‌فرض ۵۰٬۰۰۰ تومان، تنظیمیِ ادمین، الزامی در سمتِ سرور).

قفل‌ها:
۱. سرویسِ پرداخت (نه فقط UI) مبلغِ کمتر از حداقل را برایِ هر سه روش (کارت‌به‌کارت، زرین‌پال، بله‌پی)
   رد می‌کند و **هیچ ردیفِ Payment نمی‌سازد**.
۲. دقیقاً همان عددِ حداقل قبول می‌شود (مرزِ بازه).
۳. ادمین می‌تواند حداقل را عوض کند و سرویس همان لحظه همان عدد را اعمال می‌کند؛ ورودیِ خارجِ بازه ذخیره نمی‌شود.
۴. حداقل فقط رویِ `PaymentPurpose.WALLET_TOPUP` اثر می‌کند؛ خریدِ اشتراک عمداً خارج از این قاعده است (تصمیمِ مستند).
۵. UI از سرویس جدا نمی‌افتد: پیش‌فرض‌هایِ زیرِ حداقل نمایش داده نمی‌شوند، callbackِ جعلی
   (`topup_amount:1`) رد می‌شود، و متنِ راهنما عددِ واقعیِ حداقل را می‌گوید.
۶. اگر تنظیمِ ادمین صفر/منفی شود، کفِ ایمنیِ کد (۱٬۰۰۰) نگهبان است.

مواردِ ۱، ۲ و ۳ از چک‌لیستِ اجباریِ PHASE 10 همین‌جا پوشش داده شده‌اند.

اجرا: python3 tests_manual/test_p5_min_recharge.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.database.models import AdminSettings, Payment, PaymentPurpose, ShopOwner  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import payment_service, shop_owner_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_511
SECOND_OWNER_TG_ID = 999_512
ADMIN_TG_ID = 12345
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"


async def _seed_owner(telegram_id: int = OWNER_TG_ID) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, telegram_id)
        await shop_owner_service.complete_registration(
            session, owner, "شارژ", "تست", "09123333333", "min@example.com", True, True
        )
        return owner.id


async def _owner_row(session, owner_id: int):
    return (await session.execute(select(ShopOwner).where(ShopOwner.id == owner_id))).scalar_one()


async def _payment_count() -> int:
    async with session_scope() as session:
        return int((await session.execute(select(func.count()).select_from(Payment))).scalar_one())


async def _set_min(value: int) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.min_topup_amount_toman = value
        await session.flush()


# ============================================================================= ۱ — ردِ سمتِ سرور
async def test_service_rejects_below_minimum_for_every_method() -> None:
    await reset_database()
    owner_id = await _seed_owner()
    before = await _payment_count()

    async with session_scope() as session:
        owner = await _owner_row(session, owner_id)

        try:
            await payment_service.create_card_to_card_payment(session, owner, 49_999, None, purpose=PaymentPurpose.WALLET_TOPUP)
            raise AssertionError("کارت‌به‌کارتِ ۴۹٬۹۹۹ باید رد می‌شد")
        except payment_service.MinRechargeAmountError as exc:
            assert exc.minimum_toman == 50_000, exc.minimum_toman

        try:
            await payment_service.create_zarinpal_payment(session, owner, 10_000, None, "auth-1", purpose=PaymentPurpose.WALLET_TOPUP)
            raise AssertionError("زرین‌پالِ ۱۰٬۰۰۰ باید رد می‌شد")
        except payment_service.MinRechargeAmountError:
            pass

        try:
            await payment_service.create_bale_payment(session, owner, 1, None, "{}", purpose=PaymentPurpose.WALLET_TOPUP)
            raise AssertionError("بله‌پیِ ۱ تومانی باید رد می‌شد")
        except payment_service.MinRechargeAmountError:
            pass

    assert await _payment_count() == before, "ردِ اعتباری نباید ردیفِ Payment بسازد"
    print("✅ test_service_rejects_below_minimum_for_every_method PASSED")


# ============================================================================= ۲ — مرزِ دقیق
async def test_service_accepts_exactly_the_minimum() -> None:
    await reset_database()
    owner_id = await _seed_owner()

    async with session_scope() as session:
        owner = await _owner_row(session, owner_id)
        payment = await payment_service.create_card_to_card_payment(session, owner, 50_000, None, purpose=PaymentPurpose.WALLET_TOPUP)
        assert payment.base_amount == 50_000
        # کارت‌به‌کارت چند تومانِ تصادفی اضافه می‌کند ⇒ مبلغِ درخواستی هرگز زیرِ حداقل نمی‌افتد
        assert payment.final_amount >= 50_010, payment.final_amount

        bale = await payment_service.create_bale_payment(session, owner, 50_000, None, "{}", purpose=PaymentPurpose.WALLET_TOPUP)
        assert bale.final_amount == 50_000
    assert await _payment_count() == 2
    print("✅ test_service_accepts_exactly_the_minimum PASSED")


# ============================================================================= ۳ — تنظیمِ ادمین
async def test_admin_can_change_the_minimum_and_service_follows(main_dp) -> None:
    await reset_database()
    owner_id = await _seed_owner()
    await seed_usable_shop(SECOND_OWNER_TG_ID, 999_513)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    async with session_scope() as session:
        labels = dict(main_texts.admin_settings_button_labels(await get_admin_settings(session)))
    assert "min_topup_amount_toman" in labels, list(labels)
    assert "۵۰٬۰۰۰" in labels["min_topup_amount_toman"], labels["min_topup_amount_toman"]

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_setting_edit:min_topup_amount_toman", user_id=ADMIN_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_ASK_MIN_TOPUP_AMOUNT
    await main_dp.feed_update(main_bot, make_message_update(2, text="120000", user_id=ADMIN_TG_ID))
    async with session_scope() as session:
        assert (await get_admin_settings(session)).min_topup_amount_toman == 120_000

    async with session_scope() as session:
        owner = await _owner_row(session, owner_id)
        try:
            await payment_service.create_card_to_card_payment(session, owner, 100_000, None, purpose=PaymentPurpose.WALLET_TOPUP)
            raise AssertionError("۱۰۰٬۰۰۰ با حداقلِ ۱۲۰٬۰۰۰ باید رد شود")
        except payment_service.MinRechargeAmountError as exc:
            assert exc.minimum_toman == 120_000, exc.minimum_toman
        ok = await payment_service.create_card_to_card_payment(session, owner, 120_000, None, purpose=PaymentPurpose.WALLET_TOPUP)
        assert ok.base_amount == 120_000
    print("✅ test_admin_can_change_the_minimum_and_service_follows PASSED")


async def test_admin_input_out_of_range_is_not_saved(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(SECOND_OWNER_TG_ID, 999_514)
    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_callback_update(1, data="admin_setting_edit:min_topup_amount_toman", user_id=ADMIN_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="50000000", user_id=ADMIN_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == main_texts.ADMIN_INVALID_NUMBER, session_obj.sent_messages[-1]
    async with session_scope() as session:
        assert (await get_admin_settings(session)).min_topup_amount_toman == 50_000
    print("✅ test_admin_input_out_of_range_is_not_saved PASSED")


# ============================================================================= ۴ — دامنه
async def test_minimum_does_not_gate_subscription_purchases() -> None:
    """تصمیمِ مستند: خواسته «حداقلِ شارژِ کیف‌پول» است، نه حداقلِ خریدِ اشتراک."""
    await reset_database()
    owner_id = await _seed_owner()
    async with session_scope() as session:
        owner = await _owner_row(session, owner_id)
        payment = await payment_service.create_zarinpal_payment(
            session, owner, 5_000, None, "auth-2", purpose=PaymentPurpose.SUBSCRIPTION
        )
        assert payment.base_amount == 5_000
    print("✅ test_minimum_does_not_gate_subscription_purchases PASSED")


# ============================================================================= ۵ — هم‌راستاییِ UI و سرویس
async def test_ui_follows_the_configured_minimum(main_dp) -> None:
    await reset_database()
    await _seed_owner()
    await _set_min(200_000)

    datas = [b.callback_data for row in keyboards.topup_amount_keyboard(200_000).inline_keyboard for b in row]
    assert "topup_amount:50000" not in datas and "topup_amount:100000" not in datas, datas
    assert "topup_amount:300000" in datas and "topup_amount:500000" in datas, datas
    assert "topup_amount:custom" in datas, datas

    main_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]
    await main_dp.feed_update(main_bot, make_message_update(1, text="💰 کیف‌پول", user_id=OWNER_TG_ID))
    n = 2
    await main_dp.feed_update(main_bot, make_callback_update(n, data="topup_start", user_id=OWNER_TG_ID))
    shown = [b.callback_data for row in session_obj.sent_messages[-1]["reply_markup"].inline_keyboard for b in row]
    assert "topup_amount:50000" not in shown, shown

    # callbackِ جعلیِ زیرِ حداقل ⇒ toastِ روشن با عددِ واقعی
    n += 1
    await main_dp.feed_update(main_bot, make_callback_update(n, data="topup_amount:1", user_id=OWNER_TG_ID))
    assert session_obj.answered_callbacks[-1]["text"] == main_texts.topup_below_minimum_toast(200_000), session_obj.answered_callbacks[-1]
    assert await _payment_count() == 0, "ردِ UI نباید ردیفِ پرداخت بسازد"

    # مبلغِ دلخواهِ زیرِ حداقل ⇒ راهنما عددِ تنظیم‌شده را می‌گوید، نه عددِ قدیمیِ ۱۰٬۰۰۰
    n += 1
    await main_dp.feed_update(main_bot, make_callback_update(n, data="topup_amount:custom", user_id=OWNER_TG_ID))
    prompt = session_obj.sent_messages[-1]["text"]
    assert "۲۰۰٬۰۰۰" in prompt and "۱۰٬۰۰۰" not in prompt, prompt
    n += 1
    await main_dp.feed_update(main_bot, make_message_update(n, text="40000", user_id=OWNER_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == main_texts.invalid_topup_amount(200_000), session_obj.sent_messages[-1]

    n += 1
    await main_dp.feed_update(main_bot, make_message_update(n, text="abc", user_id=OWNER_TG_ID))
    assert session_obj.sent_messages[-1]["text"] == main_texts.invalid_topup_amount(200_000)
    assert await _payment_count() == 0
    print("✅ test_ui_follows_the_configured_minimum PASSED")


# ============================================================================= ۶ — کفِ ایمنی
async def test_hard_floor_protects_broken_config() -> None:
    await reset_database()
    await _seed_owner()

    for broken in (0, -5, 10):
        await _set_min(broken)
        async with session_scope() as session:
            assert await payment_service.minimum_recharge_toman(session) == payment_service.MIN_TOPUP_HARD_FLOOR_TOMAN, (
                broken,
                "عددِ زیرِ کفِ ایمنیِ کد هرگز اعمال نمی‌شود (جلوگیریِ «حداقلِ یک‌تومانی» با اشتباهِ تایپی)",
            )

    await _set_min(2_500)
    async with session_scope() as session:
        assert await payment_service.minimum_recharge_toman(session) == 2_500, "عددِ معتبرِ ادمین بالایِ کف عیناً اعمال می‌شود"
    print("✅ test_hard_floor_protects_broken_config PASSED")


async def test_default_column_value_is_fifty_thousand() -> None:
    column = AdminSettings.__table__.columns["min_topup_amount_toman"]
    assert column.default.arg == 50_000 and column.server_default is not None
    assert payment_service.DEFAULT_MIN_TOPUP_TOMAN == 50_000
    assert main_texts.topup_presets_for(50_000) == [50_000, 100_000, 300_000, 500_000], "پیش‌فرض‌هایِ امروز نباید عوض شوند"
    print("✅ test_default_column_value_is_fifty_thousand PASSED")


async def main() -> None:
    await test_default_column_value_is_fifty_thousand()
    await test_service_rejects_below_minimum_for_every_method()
    await test_service_accepts_exactly_the_minimum()
    await test_minimum_does_not_gate_subscription_purchases()
    await test_hard_floor_protects_broken_config()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_admin_can_change_the_minimum_and_service_follows(main_dp)
    await test_admin_input_out_of_range_is_not_saved(main_dp)
    await test_ui_follows_the_configured_minimum(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
