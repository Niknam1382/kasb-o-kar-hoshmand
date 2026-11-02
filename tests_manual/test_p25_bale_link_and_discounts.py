"""
تست: P25/P26 — لینکِ پرداختِ بله (BLE.IR) و حذفِ «مبلغ ثابت» از پنلِ ادمین

باگ‌هایی که این فایل می‌بندد (همه از شواهدِ زنده، نه حدس):

۱. `bale_pay_link_template` مقدارِ نمونهٔ داکیومنت (`https://YOUR_BALE_PAYMENT_BASE_URL?…`) را داشت؛
   تلگرام «Wrong HTTP URL» می‌داد و هندلر **بعد از** ساختِ صورتحساب می‌ترکید
   (`panel.py:932` و `shop_bot/handlers/payments.py:225` در لاگِ ۱۳:۰۲ و ۱۳:۰۴) ⇒ «دکمه هیچ کاری
   نمی‌کند» و ردیفِ Payment با هندلر rollback می‌شد.
۲. پروبِ زنده (P26): `https://bale.ai/pay/<id>` و `https://ble.ir/pay/abc` ⇒ ۴۰۴،
   `https://ble.ir/smartbusinessbot?start=…` ⇒ ۲۰۰. یعنی هیچ آدرسِ پرداختی وجود ندارد و لینکِ درست
   چتِ رباتِ پرداخت است؛ صورتحساب را خودِ بله در آن چت نشان می‌دهد.
۳. کرشِ `AttributeError: 'str' object has no attribute 'value'` در فهرستِ کدهایِ تخفیف
   (لاگِ ۱۳:۰۵:۴۸) + خواستهٔ کاربر: «کد تخفیف مبلغ ثابت را از پنلِ ادمین حذف کن».

اجرا: python3 tests_manual/run_one.py test_p25_bale_link_and_discounts.py
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from decimal import Decimal  # noqa: E402

from aiogram import Bot  # noqa: E402
from aiogram.exceptions import TelegramBadRequest  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    reset_database,
)
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.main_bot.states import AdminPricingStates  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import DiscountCode, DiscountType, OrderPayment, Payment, PaymentStatus  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service, order_payment_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402

OWNER_TG_ID = 999_801
SHOP_BOT_TG_ID = 999_802
PAY_BOT_USERNAME = "platform_pay_bot"
PAY_BOT_LINK = f"https://ble.ir/{PAY_BOT_USERNAME}"


async def _configure_bale(*, username: str | None = PAY_BOT_USERNAME) -> None:
    """پیکربندیِ پنلِ ادمین (توکنِ ربات + توکنِ درگاه + سوییچ). `getMe` جای‌گزین می‌شود تا
    تست هرگز به شبکه‌یِ واقعیِ بله نزند؛ نامِ کاربری از همان getMe خوانده می‌شود."""
    original_get_me = bale_service.get_me

    async def fake_get_me(token: str) -> dict:
        return {"id": 42, "username": username or ""}

    bale_service.get_me = fake_get_me
    try:
        async with session_scope() as session:
            admin = await get_admin_settings(session)
            admin.bale_bot_token = "111111:fake-bale-bot-token-for-tests"
            admin.bale_provider_token = "provider-token-77"
            admin.bale_pay_enabled = True
            await session.flush()
            await bale_credentials_service.refresh(session)
    finally:
        bale_service.get_me = original_get_me


async def _payments() -> list[Payment]:
    async with session_scope() as session:
        return list((await session.execute(select(Payment))).scalars().all())


async def _run_to_payment_methods(chat: Chat) -> list[str]:
    await chat.tap("topup_start")
    await chat.tap("topup_amount:100000")
    await chat.tap("skip_discount")
    return [btn.text for row in chat.last_markup.inline_keyboard for btn in row]


def _buttons(markup):
    return [btn for row in markup.inline_keyboard for btn in row] if markup else []


# ============================================================================= ۱ — لینکِ واقعیِ پرداخت
def test_pay_chat_link_shape() -> None:
    link = bale_service.pay_chat_link(PAY_BOT_USERNAME, "payment-7-abcdef")
    assert link == "https://ble.ir/platform_pay_bot?start=payment-7-abcdef", link
    assert bale_service.pay_chat_link(f"@{PAY_BOT_USERNAME}", "payment-7-x") == PAY_BOT_LINK + "?start=payment-7-x"
    # هیچ‌وقت لینکِ ناقص نساز: بدونِ نامِ کاربری / بدونِ payload / نامِ غیرمجاز ⇒ None
    assert bale_service.pay_chat_link("", "payment-7-x") is None
    assert bale_service.pay_chat_link(None, "payment-7-x") is None
    assert bale_service.pay_chat_link(PAY_BOT_USERNAME, "") is None
    assert bale_service.pay_chat_link("1badbot", "payment-7-x") is None, "نامِ ربات با رقم شروع نمی‌شود"
    assert bale_service.pay_chat_link("ab", "payment-7-x") is None, "خیلی کوتاه"
    # پاسخِ خودِ بله هم دیگر به شکلِ آدرس تفسیر نمی‌شود: createInvoiceLink فقط شناسهٔ مینی‌اپ است
    assert bale_service.pay_chat_link(PAY_BOT_USERNAME, "invoice_id=M6dm") == PAY_BOT_LINK + "?start=invoice_id%3DM6dm"
    print("✅ test_pay_chat_link_shape PASSED")


# ============================================================================= ۲ — بدونِ رباتِ شناخته‌شده: نه دکمه، نه ردیف
async def test_unknown_payment_bot_offers_nothing(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(username="")

    chat = Chat(main_dp, OWNER_TG_ID)
    labels = await _run_to_payment_methods(chat)
    assert not any("بله‌پی" in label for label in labels), f"لینکی که ساخته نمی‌شود نباید دکمه داشته باشد: {labels}"
    assert any("کارت" in label for label in labels), labels
    # کیبوردِ کهنه (دکمه‌ای که پیش‌تر فرستاده شده) هم باید صادقانه رد شود، نه لینکِ نصفه
    await chat.tap("payment_method:bale")
    assert "بله" in chat.last_text, chat.last_text
    assert await _payments() == [], "لینکی که وجود ندارد ⇒ پرداختی هم ثبت نمی‌شود"
    print("✅ test_unknown_payment_bot_offers_nothing PASSED")


# ============================================================================= ۳ — مسیرِ معمول: لینک + یکِ ردیف
async def test_topup_link_points_at_the_bale_chat(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale()

    chat = Chat(main_dp, OWNER_TG_ID)
    await _run_to_payment_methods(chat)
    await chat.tap("payment_method:bale")

    buttons = _buttons(chat.last_markup)
    assert len(buttons) == 1 and buttons[0].url is not None, [b.url for b in buttons]
    assert buttons[0].url.startswith(PAY_BOT_LINK + "?start=payment-"), buttons[0].url
    assert "۱۰۰٬۰۰۰" in chat.last_text or "100" in chat.last_text, chat.last_text
    rows = await _payments()
    assert len(rows) == 1 and rows[0].status == PaymentStatus.PENDING, [(r.status, r.final_amount) for r in rows]
    assert buttons[0].url.endswith(rows[0].bale_invoice_payload), "لینک همان payloadِ ردیف را می‌برد"
    print("✅ test_topup_link_points_at_the_bale_chat PASSED")


# ============================================================================= ۴ — لینکِ نرسیده، پرداخت نمی‌ماند
async def test_undeliverable_link_voids_the_payment(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale()

    chat = Chat(main_dp, OWNER_TG_ID)
    await _run_to_payment_methods(chat)

    real_make_request = chat.session.make_request

    async def failing_send(bot, method, timeout=None):
        if type(method).__name__ == "SendMessage" and getattr(method, "reply_markup", None) is not None:
            raise TelegramBadRequest(method="SendMessage", message="Bad Request: inline keyboard button URL is invalid")
        return await real_make_request(bot, method, timeout)

    chat.session.make_request = failing_send
    try:
        await chat.tap("payment_method:bale")
    finally:
        chat.session.make_request = real_make_request

    rows = await _payments()
    assert len(rows) == 1, f"ردیف باید بماند و باطل شود، نه rollback: {len(rows)}"
    assert rows[0].status == PaymentStatus.REJECTED, rows[0].status
    assert rows[0].rejection_reason and "ارسال نشد" in rows[0].rejection_reason, rows[0].rejection_reason
    assert chat.last_text == main_texts.BALE_PAY_LINK_SEND_FAILED, chat.last_text
    print("✅ test_undeliverable_link_voids_the_payment PASSED")


# ============================================================================= ۵ — کیبوردِ کهنه دیگر نمی‌ترکد
async def test_stale_payment_keyboard_answers(main_dp) -> None:
    """P23 (بدهیِ منتقل‌شده): با state خالی هر سه دکمهٔ «روشِ پرداخت» باید جوابِ دیدنی بدهند."""
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale()
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.zarinpal_enabled = True
        admin.zarinpal_merchant_id = "00000000-0000-0000-0000-000000000000"
        await session.flush()

    chat = Chat(main_dp, OWNER_TG_ID)
    for data in ("payment_method:card", "payment_method:zarinpal", "payment_method:bale"):
        await chat.tap(data)
        assert chat.last_toast["text"] == main_texts.PAYMENT_FLOW_STALE, (data, chat.last_toast)
        assert not chat.sent, f"با کیبوردِ کهنه نباید پیامی برود: {data}"
    assert await _payments() == []
    print("✅ test_stale_payment_keyboard_answers PASSED")


# ============================================================================= ۶ — فهرستِ تخفیف با هر دو شکلِ `type`
def test_discount_list_keyboard_survives_both_type_shapes() -> None:
    percent_enum = DiscountCode(code="P1", type=DiscountType.PERCENT, value=Decimal("20"), is_active=True)
    fixed_str = DiscountCode(code="F1", type="fixed", value=Decimal("50000"), is_active=False)

    markup = main_keyboards.admin_discounts_list_keyboard([percent_enum, fixed_str])
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("۲۰٪" in label for label in labels), labels
    assert any("قدیمی" in label and "F1" in label for label in labels), labels
    datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "admin_discount_add" in datas and "admin_pricing_menu" in datas, datas
    print("✅ test_discount_list_keyboard_survives_both_type_shapes PASSED")


# ============================================================================= ۷ — «مبلغ ثابت» از پنل رفت
async def test_fixed_amount_option_is_gone_from_panel(main_dp) -> None:
    await reset_database()
    assert settings.admin_ids, "این تست به ADMIN_TELEGRAM_IDSِ محیطِ تست نیاز دارد"
    admin_id = next(iter(settings.admin_ids))
    assert not hasattr(main_keyboards, "discount_type_keyboard"), "کیبوردِ نوع تخفیف باید حذف شده باشد"
    assert not hasattr(AdminPricingStates, "waiting_discount_type"), "مرحلهٔ نوع باید از FSM حذف شده باشد"
    assert not hasattr(main_texts, "ADMIN_ASK_DISCOUNT_TYPE"), "پرسشِ نوع باید از متن‌ها حذف شده باشد"
    assert not hasattr(main_texts, "ADMIN_ASK_BALE_PAY_LINK_TEMPLATE"), "تنظیمِ «قالبِ لینک» هم از پنل برداشته شده"

    admin_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = admin_bot.session  # type: ignore[assignment]
    n = 0

    async def cb(data: str) -> None:
        nonlocal n
        n += 1
        await main_dp.feed_update(admin_bot, make_callback_update(n, data=data, user_id=admin_id))

    async def say(text: str) -> None:
        nonlocal n
        n += 1
        await main_dp.feed_update(admin_bot, make_message_update(n, text=text, user_id=admin_id))

    await cb("admin_discount_add")
    await say("P25TEST")
    await say("۱۵")
    await say("نامحدود")
    async with session_scope() as session:
        code = (await session.execute(select(DiscountCode).where(DiscountCode.code == "P25TEST"))).scalar_one_or_none()
    assert code is not None, "جریانِ ساختِ کدِ درصدی باید کار کند"
    type_value = code.type.value if hasattr(code.type, "value") else code.type
    assert type_value == "percent" and int(code.value) == 15, (type_value, code.value)

    await cb("admin_discount_add")
    n += 1
    await main_dp.feed_update(admin_bot, make_callback_update(n, data="discount_type:fixed", user_id=admin_id))
    assert session_obj.answered_callbacks[-1]["text"] == main_texts.ADMIN_DISCOUNT_TYPE_REMOVED
    await say("50000")
    async with session_scope() as session:
        after = len(list((await session.execute(select(DiscountCode))).scalars().all()))
    assert after == 1, "با state پاک‌شده نباید کدی ساخته شود"

    await cb("admin_discount_add")
    await say("TOOBIG")
    await say("5000")
    async with session_scope() as session:
        assert (await session.execute(select(DiscountCode).where(DiscountCode.code == "TOOBIG"))).scalar_one_or_none() is None
    print("✅ test_fixed_amount_option_is_gone_from_panel PASSED")


# ============================================================================= ۸ — باطل‌کردنِ تلاشِ ناموفقِ پرداختِ سفارش
async def test_mark_link_failed_is_bounded_and_idempotent() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        payment = OrderPayment(
            group_id="g" * 32, shop_bot_id=shop_bot_id, method="bale",
            amount_toman=120_000, status=order_payment_service.P_INITIATED,
        )
        session.add(payment)
        await session.flush()
        payment_id = payment.id

        await order_payment_service.mark_link_failed(session, payment, reason="لینکِ پرداخت ارسال نشد (ردِ سمتِ ربات)")
        fresh = await session.get(OrderPayment, payment_id)
        assert fresh.status == order_payment_service.P_FAILED, fresh.status
        assert fresh.reject_reason and "ارسال نشد" in fresh.reject_reason, fresh.reject_reason
        await order_payment_service.mark_link_failed(session, fresh, reason="دوباره")
        assert (await session.get(OrderPayment, payment_id)).status == order_payment_service.P_FAILED

        paid = OrderPayment(
            group_id="h" * 32, shop_bot_id=shop_bot_id, method="bale",
            amount_toman=50_000, status=order_payment_service.P_PAID,
        )
        session.add(paid)
        await session.flush()
        await order_payment_service.mark_link_failed(session, paid, reason="نباید چیزی عوض کند")
        assert (await session.get(OrderPayment, paid.id)).status == order_payment_service.P_PAID
    print("✅ test_mark_link_failed_is_bounded_and_idempotent PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_pay_chat_link_shape()
    await test_unknown_payment_bot_offers_nothing(main_dp)
    await test_topup_link_points_at_the_bale_chat(main_dp)
    await test_undeliverable_link_voids_the_payment(main_dp)
    await test_stale_payment_keyboard_answers(main_dp)
    test_discount_list_keyboard_survives_both_type_shapes()
    await test_fixed_amount_option_is_gone_from_panel(main_dp)
    await test_mark_link_failed_is_bounded_and_idempotent()
    print("\n✅ همهٔ تست‌هایِ P25/P26 پاس شدند")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
