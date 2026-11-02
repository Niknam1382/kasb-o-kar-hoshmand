"""
تست: بله‌پی برایِ سفارشِ محصول (فازِ ۳) — پرداختِ مستقیمِ مشتری به فروشگاه‌دار،
کاملاً جدا از بله‌پیِ فروشگاه‌دار-به-پلتفرم که در test_bale_pay_wallet_topup.py
پوشش داده شده (این‌جا provider_token مالِ خودِ فروشگاهه، نه پلتفرم؛ و payload
با 'order-' شروع می‌شه نه 'payment-').

مهم: هیچ تماسِ HTTPِ واقعی به بله زده نمی‌شه — create_invoice_link،
inquire_transaction و answer_pre_checkout_query همه monkeypatch می‌شن، دقیقاً
همون الگویِ test_bale_pay_wallet_topup.py.

پوشش:
۱. فروشگاه‌دار می‌تونه کدِ درگاهِ خودش رو تنظیم/حذف کنه (پنل).
۲. بدونِ تنظیم‌بودنِ کد: بعدِ تاییدِ سفارش توسطِ مشتری، هیچ پیشنهادِ پرداختی
   فرستاده نمی‌شه (فلویِ اصلیِ تاییدِ سفارش دست‌نخورده می‌مونه).
۳. با تنظیم‌بودنِ کد: بعدِ تاییدِ سفارش، پیشنهادِ پرداخت با مبلغِ درست فرستاده
   می‌شه و payload روی خودِ سفارش ذخیره می‌شه.
۴. سفارشی که ارزشِ تخمینی نداره (None) هیچ‌وقت پیشنهادِ پرداخت نمی‌گیره، حتی
   با تنظیم‌بودنِ کد.
۵. وب‌هوکِ pre_checkout: قبول برایِ سفارشِ معتبر/پرداخت‌نشده، ردّ برایِ
   ناشناس/قبلاً-پرداخت‌شده.
۶. وب‌هوکِ successful_payment: بدونِ تاییدِ inquire_transaction هیچ‌وقت سفارش
   پرداخت‌شده علامت نمی‌خوره (مهم‌ترین محافظت در برابرِ وب‌هوکِ جعلی). با
   تاییدِ inquire_transaction: هم فروشگاه‌دار (ربات اصلی) هم مشتری (ربات
   فروشگاهی) خبردار می‌شن؛ وب‌هوکِ تکراری دوباره خبر نمی‌ده.

اجرا: python3 tests_manual/test_bale_pay_for_orders.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    register_fake_shop_bot,
    reset_database,
)
from shop_setup import seed_usable_shop  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import OrderStatus, OrderType, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service, customer_service, order_service, shop_bot_service, shop_owner_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings, update_setting  # noqa: E402

OWNER_TG_ID = 999901
SHOP_BOT_TG_ID = 999902
CUSTOMER_TG_ID = 999903
ADMIN_TG_ID = 12345

_created_invoices: list[dict] = []


async def _fake_create_invoice_link(bot_token, provider_token, title, description, payload, amount_rial) -> str:
    _created_invoices.append({"provider_token": provider_token, "payload": payload, "amount_rial": amount_rial})
    return f"https://fake-bale-pay.test/{payload}"


async def _seed(with_provider_token: bool) -> tuple[int, int]:
    await reset_database()
    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"  # فقط برایِ اینکه شرطِ truthy رد بشه؛ هیچ تماسِ واقعی نمی‌زنیم
    _created_invoices.clear()
    bale_service.create_invoice_link = _fake_create_invoice_link

    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        await update_setting(session, "bale_pay_enabled", True)
        # P26: لینکِ پرداخت = چتِ رباتِ پرداخت؛ نامِ کاربری را به‌جایِ getMe می‌گذاریم (تست به شبکه نمی‌زند).
        bale_credentials_service.remember_pay_bot_username('platform_pay_bot')
        if with_provider_token:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            shop_bot.bale_provider_token = "SHOP-OWN-PROVIDER-TOKEN"
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER_TG_ID, "مشتری", None)
        customer_id = customer.id
    return shop_bot_id, customer_id


async def _create_and_confirm_order(shop_dp, shop_bot_id: int, customer_id: int, estimated_value_toman: int | None) -> tuple[int, Bot]:
    async with session_scope() as session:
        order = await order_service.create_order_awaiting_confirmation(
            session, shop_bot_id, customer_id, OrderType.ORDER, "دو کیلو برنج", estimated_value_toman, None, None, None, None
        )
        order_id = order.id

    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    await shop_dp.feed_update(
        shop_bot_instance, make_callback_update(1, data=f"cust_confirm_order:{order_id}", user_id=CUSTOMER_TG_ID)
    )
    return order_id, shop_bot_instance


async def test_owner_can_set_and_remove_provider_token(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(owner_bot, make_message_update(1, text="💳 پرداختِ آنلاینِ سفارش‌ها", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(2, text="MY-REAL-PROVIDER-TOKEN", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        shop_bot = await shop_bot_service.get_by_owner(session, owner)
        assert shop_bot.bale_provider_token == "MY-REAL-PROVIDER-TOKEN"

    await main_dp.feed_update(owner_bot, make_message_update(3, text="💳 پرداختِ آنلاینِ سفارش‌ها", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(4, text="حذف", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        shop_bot = await shop_bot_service.get_by_owner(session, owner)
        assert shop_bot.bale_provider_token is None

    print("✅ test_owner_can_set_and_remove_provider_token PASSED")


async def test_no_payment_offer_without_provider_token() -> None:
    """
    قبلاً این تست از مسیرِ کاملِ callback (شبیه‌سازیِ کلیکِ واقعیِ مشتری) رد
    می‌شد، ولی چون چیزی که واقعاً می‌خوایم تست کنیم فقط شرطِ گاردِ داخلِ
    _maybe_offer_online_paymentِ خودشه (نه کل زنجیره‌ی resolve/confirm که جای
    دیگه‌ای — test_order_customer_confirmation.py — قبلاً تست شده)، مستقیم
    خودِ همون تابع رو صدا می‌زنیم. این هم دقیق‌تره هم اگه بازم مشکلی بود،
    پیامِ خطا خودش می‌گه دقیقاً چی فرستاده شده.
    """
    shop_bot_id, customer_id = await _seed(with_provider_token=False)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    async with session_scope() as session:
        order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "خلاصه", 500_000)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        await customer_handlers._maybe_offer_online_payment(shop_bot_instance, session, shop_bot, order, CUSTOMER_TG_ID)
        order_id = order.id

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert not sent.sent_messages, f"بدونِ کدِ درگاه نباید هیچ پیشنهادِ پرداختی بره؛ فرستاده‌شده: {[m['text'] for m in sent.sent_messages]}"
    assert not _created_invoices, "نباید هیچ لینکِ پرداختی ساخته بشه"

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert order.bale_invoice_payload is None
    print("✅ test_no_payment_offer_without_provider_token PASSED")


async def test_payment_offer_sent_and_payload_stored_when_configured(shop_dp) -> None:
    shop_bot_id, customer_id = await _seed(with_provider_token=True)
    order_id, shop_bot_instance = await _create_and_confirm_order(shop_dp, shop_bot_id, customer_id, 500_000)

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    # نکته‌ی مهم: پیامِ «✅ ثبت شد» با edit_text می‌ره (نه send_message)، پس اصلاً
    # توی sent_messages شمرده نمی‌شه — فقط پیشنهادِ پرداخت send_message ـه. قبلاً
    # اینجا اشتباهاً «۲» فرض شده بود (همون باگی که کرش داد).
    assert len(sent.sent_messages) == 1, (
        f"باید فقط پیشنهادِ پرداخت send بشه (تاییدِ ثبت edit ـه، شمرده نمی‌شه)؛ فرستاده‌شده ({len(sent.sent_messages)}): "
        f"{[m['text'] for m in sent.sent_messages]}"
    )
    offer_text = sent.sent_messages[0]["text"]
    assert offer_text == shop_texts.online_payment_offer(500_000)

    assert len(_created_invoices) == 1
    assert _created_invoices[0]["provider_token"] == "SHOP-OWN-PROVIDER-TOKEN"
    assert _created_invoices[0]["amount_rial"] == 5_000_000  # ۵۰۰٬۰۰۰ تومان × ۱۰

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert order.bale_invoice_payload is not None
        assert order.bale_invoice_payload.startswith("order-")
    print("✅ test_payment_offer_sent_and_payload_stored_when_configured PASSED")


async def test_no_payment_offer_when_no_estimated_value() -> None:
    shop_bot_id, customer_id = await _seed(with_provider_token=True)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())

    async with session_scope() as session:
        order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "خلاصه", None)
        shop_bot = await session.get(ShopBot, shop_bot_id)
        await customer_handlers._maybe_offer_online_payment(shop_bot_instance, session, shop_bot, order, CUSTOMER_TG_ID)

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert not sent.sent_messages, f"بدونِ ارزشِ تخمینی نباید پیشنهادی بره؛ فرستاده‌شده: {[m['text'] for m in sent.sent_messages]}"
    print("✅ test_no_payment_offer_when_no_estimated_value PASSED")


async def test_pre_checkout_for_order_payload() -> None:
    shop_bot_id, customer_id = await _seed(with_provider_token=True)
    async with session_scope() as session:
        order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "خلاصه", 300_000)
        order.bale_invoice_payload = "order-test-payload-1"
        await session.flush()

    answered: dict = {}

    async def fake_answer(bot_token, query_id, ok, error_message=None):
        answered["ok"] = ok

    bale_service.answer_pre_checkout_query = fake_answer

    await app_main._handle_bale_pre_checkout({"id": "pcq_o1", "invoice_payload": "order-test-payload-1"})
    assert answered["ok"] is True

    await app_main._handle_bale_pre_checkout({"id": "pcq_o2", "invoice_payload": "order-ناشناس"})
    assert answered["ok"] is False

    print("✅ test_pre_checkout_for_order_payload PASSED")


async def test_successful_payment_requires_inquiry_confirmation_for_orders() -> None:
    shop_bot_id, customer_id = await _seed(with_provider_token=True)
    async with session_scope() as session:
        order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "خلاصه", 300_000)
        order.bale_invoice_payload = "order-verify-fail"
        await session.flush()
        order_id = order.id

    async def fake_inquire_fails(bot_token, transaction_id):
        return {"status": "failed"}

    bale_service.inquire_transaction = fake_inquire_fails

    await app_main._handle_bale_successful_payment(
        {"invoice_payload": "order-verify-fail", "telegram_payment_charge_id": "chg_fail"}
    )

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert order.bale_paid_at is None, "چون inquire_transaction گفته failed، نباید پرداخت‌شده علامت بخوره"
    print("✅ test_successful_payment_requires_inquiry_confirmation_for_orders PASSED")


async def test_successful_payment_marks_order_paid_and_notifies_both_sides(main_bot, bot_manager) -> None:
    shop_bot_id, customer_id = await _seed(with_provider_token=True)
    shop_bot_instance = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    main_bot.session.sent_messages.clear()

    async with session_scope() as session:
        order = await order_service.create_order(session, shop_bot_id, customer_id, OrderType.ORDER, "خلاصه", 300_000)
        order.bale_invoice_payload = "order-verify-ok"
        await session.flush()
        order_id = order.id

    async def fake_inquire_ok(bot_token, transaction_id):
        return {"status": "successful"}

    bale_service.inquire_transaction = fake_inquire_ok

    await app_main._handle_bale_successful_payment(
        {"invoice_payload": "order-verify-ok", "telegram_payment_charge_id": "chg_ok"}
    )

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert order.bale_paid_at is not None
        assert order.bale_transaction_id == "chg_ok"
        assert order.status == OrderStatus.PENDING, "status نباید توسطِ پرداخت تغییر کنه — همچنان دستِ فروشگاه‌داره"

    assert len(main_bot.session.sent_messages) == 1
    assert main_bot.session.sent_messages[0]["text"] == main_texts.order_paid_online_notification(order)

    customer_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(customer_session.sent_messages) == 1
    assert customer_session.sent_messages[0]["text"] == shop_texts.ONLINE_PAYMENT_CONFIRMED

    # وب‌هوکِ تکراری نباید دوباره اطلاع‌رسانی کنه
    await app_main._handle_bale_successful_payment(
        {"invoice_payload": "order-verify-ok", "telegram_payment_charge_id": "chg_ok"}
    )
    assert len(main_bot.session.sent_messages) == 1
    assert len(customer_session.sent_messages) == 1

    print("✅ test_successful_payment_marks_order_paid_and_notifies_both_sides PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    app_main._state["bot_manager"] = bot_manager
    app_main._state["main_bot"] = main_bot

    await test_owner_can_set_and_remove_provider_token(main_dp)
    await test_no_payment_offer_without_provider_token()
    await test_payment_offer_sent_and_payload_stored_when_configured(shop_dp)
    await test_no_payment_offer_when_no_estimated_value()
    await test_pre_checkout_for_order_payload()
    await test_successful_payment_requires_inquiry_confirmation_for_orders()
    await test_successful_payment_marks_order_paid_and_notifies_both_sides(main_bot, bot_manager)


if __name__ == "__main__":
    asyncio.run(main())
