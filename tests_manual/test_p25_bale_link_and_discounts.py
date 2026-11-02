"""
تست: P25 — لینکِ بله‌پی از پیش‌فرضِ مستند، باطل‌شدنِ پرداختِ بی‌ارسال، حذفِ «مبلغ ثابت» و صفِ ۱۰ ثانیه‌ایِ بله

چهار باگ/خواسته که همه از شواهدِ زنده گرفته شدند (نه حدس):

۱. `bale_pay_link_template` مقدارِ نمونهٔ داکیومنت (`https://YOUR_BALE_PAYMENT_BASE_URL?…`) را داشت؛
   تلگرام آن را «Wrong HTTP URL» رد می‌کرد و هندلر **بعد از** ساختِ صورتحاس می‌ترکید
   (`panel.py:932` و `shop_bot/handlers/payments.py:225` در لاگِ ۱۳:۰۲ و ۱۳:۰۴) ⇒ «دکمه هیچ کاری
   نمی‌کند». راهِ رفع: پیش‌فرضِ داخلی `https://bale.ai/pay/{invoice_id}` از همان سند + ردِ میزبانِ
   جعلی در پنل.
۲. ردیفِ پرداختِ ساخته‌شده با ترکیدنِ هندلر rollback می‌شد (یا PENDINGِ بی‌صاحب می‌ماند).
۳. کرشِ `AttributeError: 'str' object has no attribute 'value'` در فهرستِ کدهایِ تخفیف
   (لاگِ ۱۳:۰۵:۴۸) + خواستهٔ کاربر: «کد تخفیف مبلغ ثابت را از پنلِ ادمین حذف کن».
۴. سندِ بله: پاسخِ `pre_checkout_query` باید حداکثر ۱۰ ثانیه بعد برسد ⇒ آن آپدیت‌ها اولِ صف.

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
from app.services.bale_updates_service import order_for_handling  # noqa: E402

OWNER_TG_ID = 999_801
SHOP_BOT_TG_ID = 999_802
BALE_RAW_ID = "invoice_id=M6dm2AJsfX32GuWpmlCX"
DEFAULT_LINK = "https://bale.ai/pay/M6dm2AJsfX32GuWpmlCX"
PANEL_TEMPLATE = "https://gateway.test/bale/pay?invoice_id={invoice_id}"
# همان مقداری که در دیتابیسِ توسعه نشسته بود و دکمه را می‌کشت:
DOC_PLACEHOLDER_TEMPLATE = "https://YOUR_BALE_PAYMENT_BASE_URL?invoice_id={invoice_id}"


async def _configure_bale(*, template: str | None) -> None:
    async with session_scope() as session:
        admin = await get_admin_settings(session)
        admin.bale_bot_token = "111111:fake-bale-bot-token-for-tests"
        admin.bale_provider_token = "provider-token-77"
        admin.bale_pay_enabled = True
        admin.bale_pay_link_template = template
        await session.flush()
        await bale_credentials_service.refresh(session)


async def _payments() -> list[Payment]:
    async with session_scope() as session:
        return list((await session.execute(select(Payment))).scalars().all())


async def _run_to_payment_methods(chat: Chat) -> list[str]:
    await chat.tap("topup_start")
    await chat.tap("topup_amount:100000")
    await chat.tap("skip_discount")
    return [btn.text for row in chat.last_markup.inline_keyboard for btn in row]


def _fake_invoice_link(raw: str):
    async def fake(*args, **kwargs):
        return raw

    return fake


# ============================================================================= ۱ — میزبانِ جعلی هرگز به تلگرام نمی‌رود
def test_unusable_host_never_becomes_a_button_url() -> None:
    assert bale_service.usable_link_template(DOC_PLACEHOLDER_TEMPLATE) is False
    assert bale_service.usable_link_template(PANEL_TEMPLATE) is True
    assert bale_service.usable_link_template(bale_service.DEFAULT_PAY_LINK_TEMPLATE) is True
    assert bale_service.usable_link_template("") is False, "خالی = «استفاده نکن»، نه «قابلِ استفاده»"
    assert bale_service.usable_link_template("https://bale.ai/pay") is False, "بی‌جای‌نگهدار"
    assert bale_service.usable_link_template("https://localhost:8080/pay?i={invoice_id}") is False, "میزبانِ بدونِ نقطه"
    assert bale_service.usable_link_template("https://bale.one.ai/s/{invoice_id}") is True, "زیردامنهٔ چندتکه"
    assert bale_service.usable_link_template("https://bale_ai/pay?i={invoice_id}") is False, "میزبانِ دارایِ زیرخط"
    # و پاسخِ بله با هر دو قالبِ به‌دردنخور به پیش‌فرضِ مستند می‌رسد:
    assert bale_service.resolve_payment_link(BALE_RAW_ID, DOC_PLACEHOLDER_TEMPLATE) == DEFAULT_LINK
    assert bale_service.resolve_payment_link(BALE_RAW_ID, None) == DEFAULT_LINK
    assert bale_service.resolve_payment_link(BALE_RAW_ID, PANEL_TEMPLATE) == (
        "https://gateway.test/bale/pay?invoice_id=M6dm2AJsfX32GuWpmlCX"
    )
    assert bale_service.payment_link_source(DOC_PLACEHOLDER_TEMPLATE) == "default"
    assert bale_service.payment_link_source(PANEL_TEMPLATE) == "panel"
    print("✅ test_unusable_host_never_becomes_a_button_url PASSED")


# ============================================================================= ۲ — قالبِ خالی دیگر دکمه را حذف نمی‌کند
async def test_button_and_status_survive_without_panel_template(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=None)

    async with session_scope() as session:
        admin = await get_admin_settings(session)
        ready, missing = bale_credentials_service.platform_status(admin)
    assert ready is True, f"پیش‌فرضِ داخلی هست ⇒ «قالبِ تنظیم‌نشده» دیگر علتِ نبودِ دکمه نیست: {missing}"
    assert "pay_link_template" not in missing

    chat = Chat(main_dp, OWNER_TG_ID)
    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = _fake_invoice_link(BALE_RAW_ID)
    try:
        labels = await _run_to_payment_methods(chat)
        assert any("بله‌پی" in label for label in labels), labels
        await chat.tap("payment_method:bale")
    finally:
        bale_service.create_invoice_link = original

    buttons = [btn for row in chat.last_markup.inline_keyboard for btn in row]
    assert buttons and buttons[0].url == DEFAULT_LINK, [b.url for b in buttons]
    rows = await _payments()
    assert len(rows) == 1 and rows[0].status == PaymentStatus.PENDING, [(r.status, r.final_amount) for r in rows]
    print("✅ test_button_and_status_survive_without_panel_template PASSED")


# ============================================================================= ۳ — لینکِ نرسیده، پرداختِ بی‌صاحب نمی‌گذارد
async def test_undeliverable_link_voids_the_payment(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=DOC_PLACEHOLDER_TEMPLATE)  # مقدارِ خرابِ واقعیِ پنل

    chat = Chat(main_dp, OWNER_TG_ID)
    await _run_to_payment_methods(chat)

    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = _fake_invoice_link(BALE_RAW_ID)
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
        bale_service.create_invoice_link = original

    rows = await _payments()
    assert len(rows) == 1, f"ردیف باید بماند و باطل شود، نه اینکه rollback شود: {len(rows)}"
    assert rows[0].status == PaymentStatus.REJECTED, rows[0].status
    assert rows[0].rejection_reason and "ارسال نشد" in rows[0].rejection_reason, rows[0].rejection_reason
    assert chat.last_text == main_texts.BALE_LINK_UNRESOLVED, chat.last_text
    print("✅ test_undeliverable_link_voids_the_payment PASSED")


# ============================================================================= ۴ — کرشِ فهرستِ کدهایِ تخفیف
def test_discount_list_keyboard_survives_both_type_shapes() -> None:
    """`c.type` یا enum است یا رشتهٔ خامِ ستون — لاگِ ۱۳:۰۵:۴۸ همان رشته را نمی‌شناخت."""
    percent_enum = DiscountCode(code="P1", type=DiscountType.PERCENT, value=Decimal("20"), is_active=True)
    fixed_str = DiscountCode(code="F1", type="fixed", value=Decimal("50000"), is_active=False)

    markup = main_keyboards.admin_discounts_list_keyboard([percent_enum, fixed_str])
    labels = [btn.text for row in markup.inline_keyboard for btn in row]
    assert any("۲۰٪" in label for label in labels), labels
    assert any("قدیمی" in label and "F1" in label for label in labels), labels
    datas = [btn.callback_data for row in markup.inline_keyboard for btn in row]
    assert "admin_discount_add" in datas and "admin_pricing_menu" in datas, datas
    print("✅ test_discount_list_keyboard_survives_both_type_shapes PASSED")


# ============================================================================= ۵ — حذفِ «مبلغ ثابت» از پنل (بدونِ دکمهٔ مرده)
async def test_fixed_amount_option_is_gone_from_panel(main_dp) -> None:
    await reset_database()
    assert settings.admin_ids, "این تست به ADMIN_TELEGRAM_IDSِ محیطِ تست نیاز دارد"
    admin_id = next(iter(settings.admin_ids))
    assert not hasattr(main_keyboards, "discount_type_keyboard"), "کیبوردِ انتخابِ نوع باید حذف شده باشد"
    assert not hasattr(AdminPricingStates, "waiting_discount_type"), "مرحلهٔ نوع باید از FSM حذف شده باشد"
    assert not hasattr(main_texts, "ADMIN_ASK_DISCOUNT_TYPE"), "پرسشِ نوع باید از متن‌ها حذف شده باشد"

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
    # دیگر «نوع تخفیف» پرسیده نمی‌شود؛ بلافاصله مقدارِ درصد
    await say("۱۵")
    await say("نامحدود")
    async with session_scope() as session:
        code = (await session.execute(select(DiscountCode).where(DiscountCode.code == "P25TEST"))).scalar_one_or_none()
    assert code is not None, "جریانِ ساختِ کدِ درصدی باید کار کند"
    type_value = code.type.value if hasattr(code.type, "value") else code.type
    assert type_value == "percent" and int(code.value) == 15, (type_value, code.value)

    # کیبوردِ کهنهٔ «مبلغ ثابت» ⇒ توستِ توضیحی و بیرون‌آمدن از FSM (نه کرش، نه سکوت)
    await cb("admin_discount_add")
    n += 1
    await main_dp.feed_update(admin_bot, make_callback_update(n, data="discount_type:fixed", user_id=admin_id))
    assert session_obj.answered_callbacks[-1]["text"] == main_texts.ADMIN_DISCOUNT_TYPE_REMOVED
    await say("50000")
    async with session_scope() as session:
        assert len(list((await session.execute(select(DiscountCode))).scalars().all())) == 1, "با state پاک‌شده کد ساخته نشود"

    # درصدِ بیش از ۱۰۰ «مبلغ ثابت» تفسیر نمی‌شود
    await cb("admin_discount_add")
    await say("TOOBIG")
    await say("5000")
    async with session_scope() as session:
        assert (await session.execute(select(DiscountCode).where(DiscountCode.code == "TOOBIG"))).scalar_one_or_none() is None
    print("✅ test_fixed_amount_option_is_gone_from_panel PASSED")


# ============================================================================= ۶ — پرداختِ سفارشِ فروشگاه: باطل‌شدنِ تلاشِ ناموفق
async def test_mark_link_failed_is_bounded_and_idempotent() -> None:
    """`P_FAILED` اولین مصرفِ واقعی‌اش را پیدا کرد: لینک نرسید ⇒ فقط همین تلاشِ پرداخت می‌سوزد."""
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
        assert fresh.decided_by == "system"

        await order_payment_service.mark_link_failed(session, fresh, reason="دوباره")
        assert (await session.get(OrderPayment, payment_id)).status == order_payment_service.P_FAILED

        # پرداختِ پرداخت‌شده هرگز باطل نمی‌شود (این شاخه پولِ واقعی است)
        paid = OrderPayment(
            group_id="h" * 32, shop_bot_id=shop_bot_id, method="bale",
            amount_toman=50_000, status=order_payment_service.P_PAID,
        )
        session.add(paid)
        await session.flush()
        await order_payment_service.mark_link_failed(session, paid, reason="نباید چیزی عوض کند")
        assert (await session.get(OrderPayment, paid.id)).status == order_payment_service.P_PAID
    print("✅ test_mark_link_failed_is_bounded_and_idempotent PASSED")


# ============================================================================= ۷ — صفِ ۱۰ ثانیه‌ایِ بله
def test_pre_checkout_updates_jump_the_queue() -> None:
    updates = [
        {"update_id": 1, "message": {"successful_payment": {"invoice_payload": "p1"}}},
        {"update_id": 2, "pre_checkout_query": {"id": "pc1"}},
        {"update_id": 3, "message": {"text": "سلام"}},
        {"update_id": 4, "pre_checkout_query": {"id": "pc2"}},
    ]
    ordered = order_for_handling(updates)
    assert [u["update_id"] for u in ordered[:2]] == [2, 4], "pre_checkoutها باید اول بروند (سقفِ ۱۰ ثانیه)"
    assert [u["update_id"] for u in ordered[2:]] == [1, 3], "ترتیبِ بقیه حفظ می‌شود"
    assert order_for_handling([{"update_id": 5, "message": {"text": "hi"}}]) == [{"update_id": 5, "message": {"text": "hi"}}]
    assert order_for_handling([]) == []
    print("✅ test_pre_checkout_updates_jump_the_queue PASSED")


# ============================================================================= ۸ — چیزی که عمداً مانده: پاسخِ بی‌شکل از بله
async def test_unstructured_response_creates_nothing(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _configure_bale(template=None)

    chat = Chat(main_dp, OWNER_TG_ID)
    original = bale_service.create_invoice_link
    bale_service.create_invoice_link = _fake_invoice_link("ok")
    try:
        await _run_to_payment_methods(chat)
        await chat.tap("payment_method:bale")
    finally:
        bale_service.create_invoice_link = original

    assert chat.last_text == main_texts.BALE_LINK_UNRESOLVED, chat.last_text
    assert await _payments() == [], "پاسخِ بی‌شکل نباید ردیفِ پرداخت بگذارد"
    print("✅ test_unstructured_response_creates_nothing PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_unusable_host_never_becomes_a_button_url()
    await test_button_and_status_survive_without_panel_template(main_dp)
    await test_undeliverable_link_voids_the_payment(main_dp)
    test_discount_list_keyboard_survives_both_type_shapes()
    await test_fixed_amount_option_is_gone_from_panel(main_dp)
    await test_mark_link_failed_is_bounded_and_idempotent()
    test_pre_checkout_updates_jump_the_queue()
    await test_unstructured_response_creates_nothing(main_dp)
    print("\n✅ همهٔ تست‌هایِ P25 پاس شدند")


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
