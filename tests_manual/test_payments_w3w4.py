"""
تست: W3 + W4 — روش‌هایِ پرداختِ مشتری (تنظیمات)، کارت‌به‌کارت با رسید (تایید/ردّ/تلاشِ مجدد/سقف/تکراری)،
پرداختِ دستی، انقضا (جاب + expire-on-read)، نگهبانِ «پرداخت کردم»، بله‌پی و زرین‌پالِ هر فروشگاه
(تاییدِ سمتِ سرور، ایدمپوتنسی، پرداختِ دیرهنگام، فروشِ بیش از موجودی).
اجرا: python3 tests_manual/test_payments_w3w4.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from harness import make_message_update  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from test_orders_w2 import CUSTOMER, OTHER_OWNER, OTHER_SHOP_TG, _Env, _seed  # noqa: E402

from app import main as app_main  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import OrderConsultation, OrderPayment, Product, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    ai_pool_service,
    bale_service,
    order_payment_service,
    order_state,
    payment_expiry_service,
    payment_settings_service,
    zarinpal_service,
)
from app.services.admin_settings_service import update_setting  # noqa: E402

VALID_CARD = "4111111111111111"
MERCHANT = "12345678-1234-1234-1234-123456789012"


# ----------------------------------------------------------------------------- کمکی‌ها
async def _configure(shop_bot_id: int, *, card: bool = False, bale: bool = False, zarinpal: bool = False, max_attempts: int = 5, auto_accept: bool = True) -> None:
    async with session_scope() as session:
        row = await payment_settings_service.get_or_create(session, shop_bot_id)
        if card:
            payment_settings_service.set_card(row, VALID_CARD, "علی رضایی", "ملی")
            row.card_enabled = True
        if zarinpal:
            from app.utils.encryption import encrypt_token

            row.zarinpal_merchant_id_enc = encrypt_token(MERCHANT)
            row.zarinpal_enabled = True
        row.max_receipt_attempts = max_attempts
        row.auto_accept_online = auto_accept
        if bale:
            shop_bot = await session.get(ShopBot, shop_bot_id)
            shop_bot.bale_provider_token = "SHOP-OWN-PROVIDER-TOKEN"
            await update_setting(session, "bale_pay_enabled", True)


async def _payments() -> list[OrderPayment]:
    async with session_scope() as session:
        return list((await session.execute(select(OrderPayment).order_by(OrderPayment.id))).scalars().all())


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data]


async def _product(pid: int) -> Product:
    async with session_scope() as session:
        return await session.get(Product, pid)


async def _set_deadline(minutes: int) -> None:
    async with session_scope() as session:
        for r in (await session.execute(select(OrderConsultation))).scalars().all():
            r.reservation_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)


def _seconds_left(row) -> float:
    return (row.reservation_expires_at - datetime.datetime.now(datetime.timezone.utc)).total_seconds()


# ============================================================================= خالص
async def test_pure_payment_helpers() -> None:
    pss, ops = payment_settings_service, order_payment_service
    assert pss.parse_card_number("4111 1111 1111 1111") == VALID_CARD
    assert pss.parse_card_number("۴۱۱۱-۱۱۱۱-۱۱۱۱-۱۱۱۱") == VALID_CARD, "ارقامِ فارسی"
    assert pss.parse_card_number("4111111111111112") is None, "Luhn"
    assert pss.parse_card_number("1111111111111111") is None and pss.parse_card_number("411") is None and pss.parse_card_number("") is None
    assert pss.mask_card(VALID_CARD) == "4111 **** **** 1111" and pss.format_card(VALID_CARD) == "4111 1111 1111 1111"
    # P18 · A5: بازه‌یِ مجازِ فروشگاه‌دار دیگر از پنلِ ادمین نمی‌آید؛ فقط همین بازه‌یِ ایمنیِ کد وجود دارد
    # و clampِ زمانِ استفاده (سقفِ سخت) سرِ جایش است.
    assert pss.clamp_deadline(0) == 1 and pss.clamp_deadline(99999) == 10080 and pss.clamp_review_hold(1) == 10
    assert pss.deadline_bounds() == (5, 1440) and pss.review_hold_bounds() == (60, 4320)
    assert pss.parse_positive_int("۳۰", 5, 1440) == 30 and pss.parse_positive_int("4", 5, 1440) is None
    assert pss.parse_positive_int("abc", 5, 1440) is None and pss.parse_positive_int("1" * 9, 1, 10**9) is None
    for text in ("پرداخت کردم", "واریز کردم", "کارت به کارت کردم", "پول رو ریختم", "پرداخت شد"):
        assert ops.looks_like_payment_claim(text), text
    for text in ("قیمتش چنده؟", "می‌خوام پرداخت کنم", "سلام"):
        assert not ops.looks_like_payment_claim(text), text
    assert ops.extract_tracking_ref("۱۲۳۴۵۶۷۸۹۰") == "1234567890" and ops.extract_tracking_ref("12 34-56") == "123456"
    assert ops.extract_tracking_ref("12345") is None and ops.extract_tracking_ref("سلام") is None and ops.extract_tracking_ref("1" * 40) is None
    assert ops.payment_flags(duplicate_hash=True, duplicate_tracking=True) == "dup_file,dup_tracking" and ops.payment_flags(duplicate_hash=False, duplicate_tracking=False) is None
    assert len(ops.receipt_sha256(b"x")) == 64
    assert pss.checkout_methods(None) == [] and pss.online_methods(None) == []
    print("✅ test_pure_payment_helpers PASSED")


# ============================================================================= تنظیمات
async def test_settings_ui_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    await env.owner_cb("pays_menu")
    assert "روش‌هایِ پرداختِ مشتری" in env.owner_bot.session.edited_texts[-1]["text"]

    await env.owner_cb("pays_tog:card")  # بدونِ کارت ⇒ رد
    assert env.owner_alerts()[-1].get("show_alert") is True
    await env.owner_cb("pays_tog:zarinpal")
    assert env.owner_alerts()[-1].get("show_alert") is True
    await env.owner_cb("pays_tog:manual")  # تنها روشِ فعال
    assert env.owner_alerts()[-1].get("show_alert") is True
    await env.owner_cb("pays_tog:bogus")
    assert env.owner_alerts()[-1].get("show_alert") is True

    await env.owner_cb("pays_card")
    await env.owner_say("4111111111111112")
    assert env.owner_bot.session.sent_messages[-1]["text"] == main_texts.PAYS_INVALID_CARD
    await env.owner_say("4111 1111 1111 1111")
    await env.owner_say("علی رضایی")
    await env.owner_say("ملی")
    async with session_scope() as session:
        row = await payment_settings_service.get(session, shop_bot_id)
        assert row.card_enabled and payment_settings_service.get_card_number(row) == VALID_CARD
        assert row.card_holder_name == "علی رضایی" and row.bank_name == "ملی"
        assert VALID_CARD not in row.card_number_enc, "رمزنگاری‌شده"

    await env.owner_cb("pays_dl:card")
    await env.owner_say("2")
    assert env.owner_bot.session.sent_messages[-1]["text"].startswith(main_texts.PAYS_INVALID_NUMBER)  # W5: + «بازه‌یِ مجاز: …»
    assert "بازه‌یِ مجاز" in env.owner_bot.session.sent_messages[-1]["text"]
    await env.owner_say("۳۰")
    await env.owner_cb("pays_hold")
    await env.owner_say("120")
    await env.owner_cb("pays_zp")
    await env.owner_say("short")
    assert env.owner_bot.session.sent_messages[-1]["text"] == main_texts.PAYS_INVALID_MERCHANT
    await env.owner_say(MERCHANT)
    async with session_scope() as session:
        row = await payment_settings_service.get(session, shop_bot_id)
        assert row.card_deadline_minutes == 30 and row.receipt_review_hold_minutes == 120
        assert row.zarinpal_enabled and row.zarinpal_merchant_id_enc and MERCHANT not in row.zarinpal_merchant_id_enc
    await env.owner_cb("pays_tog:card")
    await env.owner_cb("pays_tog:manual")  # حالا آنلاین هست ⇒ مجازه
    async with session_scope() as session:
        row = await payment_settings_service.get(session, shop_bot_id)
        assert not row.card_enabled and not row.manual_enabled
    await env.owner_cb("pays_tog:zarinpal")  # آخرین روشِ آنلاین رو خاموش کنیم ⇒ manual باید برگرده روشن
    await env.owner_cb("pays_tog:manual")
    async with session_scope() as session:
        row = await payment_settings_service.get(session, shop_bot_id)
        assert row.manual_enabled or payment_settings_service.online_methods(row, await session.get(ShopBot, shop_bot_id))
    print("✅ test_settings_ui_flow PASSED")


# ============================================================================= کارت‌به‌کارت
async def test_card_flow_approve(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1, p2])
    assert await env.statuses() == {"awaiting_payment"}
    ack = env.shop_bot.session.edited_texts[-1]
    assert shop_texts.PAY_METHOD_LABELS["card"] in [b.text for r in ack["reply_markup"].inline_keyboard for b in r]
    assert f"pm_card:{g}" in _datas(ack["reply_markup"]) and f"pm_manual:{g}" in _datas(ack["reply_markup"])
    owner_msg = main_bot.session.sent_messages[-1]
    assert not any("confirm_cart_group" in d for d in _datas(owner_msg["reply_markup"])), "سفارشِ منتظرِ پرداخت دکمه‌یِ تاییدِ دستی نداره"

    await env.cust_cb(f"pm_card:{g}")
    text = env.shop_bot.session.edited_texts[-1]["text"]
    assert "4111 1111 1111 1111" in text and "250,000" in text and "علی رضایی" in text
    payments = await _payments()
    assert len(payments) == 1 and payments[0].method == "card" and payments[0].status == "initiated" and payments[0].amount_toman == 250_000
    assert 3400 < _seconds_left((await env.rows())[0]) < 3700
    await env.cust_cb(f"pm_card:{g}")  # دابل‌تپ: همون پرداخت
    assert len(await _payments()) == 1

    await env.cust_cb(f"pay_receipt:{g}")
    await env.cust_say("سلام این رسیده")
    assert env.customer_msgs()[-1] == shop_texts.PAY_RECEIPT_INVALID
    await env.cust_say("۱۲۳۴۵۶۷۸۹۰۱۲")
    assert await env.statuses() == {"receipt_submitted"} and env.customer_msgs()[-1] == shop_texts.PAY_RECEIPT_RECEIVED
    assert 86000 < _seconds_left((await env.rows())[0]) < 86500, "مهلتِ بررسیِ رسید"
    review = main_bot.session.sent_messages[-1]
    assert "123456789012" in review["text"]
    pid = (await _payments())[0].id
    assert f"rcpt_ok:{pid}" in _datas(review["reply_markup"]) and f"rcpt_no:{pid}" in _datas(review["reply_markup"])

    await env.owner_cb(f"rcpt_ok:{pid}")
    assert await env.statuses() == {"paid"}
    assert (await _payments())[0].status == "approved"
    assert all(r.paid_at is not None and r.confirmed for r in await env.rows())
    product = await _product(p1)
    assert product.stock_quantity == 2 and product.reserved_quantity == 0
    assert any("تایید شد" in t for t in env.customer_msgs())
    assert len(env.shop_bot.session.sent_documents) == 1 and any(t.startswith("🧾 فاکتورِ INV-") and "پرداخت‌شده" in t for t in env.customer_msgs())
    count = len(env.customer_msgs())
    await env.owner_cb(f"rcpt_ok:{pid}")  # دابل‌تپ
    assert len(env.customer_msgs()) == count and len(env.shop_bot.session.sent_documents) == 1
    await env.owner_cb(f"og_start:{g}")
    assert await env.statuses() == {"processing"}
    print("✅ test_card_flow_approve PASSED")


async def test_card_flow_reject_retry_and_limit(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True, max_attempts=2)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    env.shop_bot.session.set_downloaded_file("incoming_photo_id", b"fake-receipt-bytes-1")
    g = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g}")

    await env.cust_cb(f"pay_receipt:{g}")
    await env.shop_dp.feed_update(env.shop_bot, make_message_update(env._next(), user_id=CUSTOMER, photo=True))
    assert await env.statuses() == {"receipt_submitted"}
    assert len(main_bot.session.sent_photos) == 1, "رسیدِ عکس برایِ فروشگاه‌دار فرستاده شد"
    pid1 = (await _payments())[0].id

    await env.owner_cb(f"rcpt_nr:0:{pid1}")  # ردّ ⇒ برمی‌گرده منتظرِ پرداخت (تلاشِ مجدد باقیه)
    assert await env.statuses() == {"awaiting_payment"}
    last = env.customer_msgs()[-1]
    assert main_texts.RECEIPT_REJECT_REASONS[0] in last and "رسیدِ جدید" in last
    assert (await _payments())[0].status == "rejected"
    count = len(env.customer_msgs())
    await env.owner_cb(f"rcpt_nr:0:{pid1}")  # دابل‌تپ
    assert len(env.customer_msgs()) == count

    await env.cust_cb(f"pay_receipt:{g}")  # تلاشِ دوم (آخر): ردّ ⇒ بسته
    await env.cust_say("987654321")
    assert await env.statuses() == {"receipt_submitted"}
    pid2 = [p for p in await _payments() if p.status == "submitted"][0].id
    await env.owner_cb(f"rcpt_no:{pid2}")
    assert main_texts.PAYS_ASK_REJECT_REASON in env.owner_bot.session.edited_texts[-1]["text"]
    await env.owner_cb(f"rcpt_nr:t:{pid2}")
    await env.owner_say("x" * 301)
    await env.owner_say("مبلغ اشتباهه")
    assert await env.statuses() == {"rejected"}
    assert "مبلغ اشتباهه" in env.customer_msgs()[-1] and "سقف" in env.customer_msgs()[-1]
    assert (await _product(p1)).reserved_quantity == 0, "رزرو آزاد شد"
    print("✅ test_card_flow_reject_retry_and_limit PASSED")


async def test_duplicate_receipt_flags(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g1 = await env.checkout([p2])
    await env.cust_cb(f"pm_card:{g1}")
    await env.cust_cb(f"pay_receipt:{g1}")
    await env.cust_say("555666777")
    assert (await _payments())[0].flags is None
    g2 = await env.checkout([p2])
    await env.cust_cb(f"pm_card:{g2}")
    await env.cust_cb(f"pay_receipt:{g2}")
    await env.cust_say("555666777")  # همون شماره‌پیگیری
    second = [p for p in await _payments() if p.group_id == g2][0]
    assert second.flags == "dup_tracking" and second.status == "submitted", "فقط پرچم؛ خودکار رد نمی‌شه"
    assert "قبلاً هم ثبت" in main_bot.session.sent_messages[-1]["text"]
    print("✅ test_duplicate_receipt_flags PASSED")


async def test_manual_choice_keeps_legacy_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.cust_cb(f"pm_manual:{g}")
    assert await env.statuses() == {"pending"}
    msg = main_bot.session.sent_messages[-1]
    assert f"confirm_cart_group:{g}" in _datas(msg["reply_markup"]), "مسیرِ قدیمیِ تاییدِ دستی"
    count = len(main_bot.session.sent_messages)
    await env.cust_cb(f"pm_manual:{g}")  # دابل‌تپ
    assert len(main_bot.session.sent_messages) == count
    await env.owner_cb(f"confirm_cart_group:{g}")
    assert await env.statuses() == {"confirmed"}
    await env.cust_cb(f"pm_card:{g}")  # دیگه منتظرِ پرداخت نیست
    assert env.cust_alerts()[-1].get("text") == shop_texts.PAY_STALE
    print("✅ test_manual_choice_keeps_legacy_flow PASSED")


async def test_expiry_job_and_expire_on_read(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g}")
    assert (await _product(p1)).reserved_quantity == 1
    await _set_deadline(-1)
    assert await payment_expiry_service.process_payment_expiry(main_bot, bot_manager) == 1
    assert await env.statuses() == {"expired"} and (await _product(p1)).reserved_quantity == 0
    assert (await _payments())[0].status == "expired"
    assert "مهلتِ پرداخت" in env.customer_msgs()[-1]
    assert await payment_expiry_service.process_payment_expiry(main_bot, bot_manager) == 0, "ایدمپوتنت"

    g2 = await env.checkout([p1])  # expire-on-read: جاب هنوز اجرا نشده
    await _set_deadline(-1)
    async with session_scope() as session:
        for r in (await session.execute(select(OrderConsultation).where(OrderConsultation.status == "expired"))).scalars().all():
            r.reservation_expires_at = None
    await env.cust_cb(f"pm_card:{g2}")
    assert env.cust_alerts()[-1].get("text") == shop_texts.PAY_STALE
    assert {r.cart_checkout_group_id: order_state.value_of(r.status) for r in await env.rows()}[g2] == "expired"
    assert (await _product(p1)).reserved_quantity == 0
    print("✅ test_expiry_job_and_expire_on_read PASSED")


async def test_payment_claim_guard_no_ai(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    calls: list[int] = []
    original = ai_pool_service.build_ai_service

    async def boom(*args, **kwargs):
        calls.append(1)
        raise AssertionError("نباید AI صدا زده بشه")

    ai_pool_service.build_ai_service = boom
    try:
        await env.cust_say("سلام، پرداخت کردم")
    finally:
        ai_pool_service.build_ai_service = original
    last = env.shop_bot.session.sent_messages[-1]
    assert last["text"] == shop_texts.PAY_CLAIM_GUIDE and f"pay_receipt:{g}" in _datas(last["reply_markup"])
    assert not calls
    print("✅ test_payment_claim_guard_no_ai PASSED")


async def test_stale_and_cross_shop_payment_ops(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, card=True)
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.cust_cb(f"pm_card:{g}")
    await env.cust_cb(f"pay_receipt:{g}")
    await env.cust_say("11223344")
    pid = (await _payments())[0].id
    await seed_usable_shop(OTHER_OWNER, OTHER_SHOP_TG)
    for data in (f"rcpt_ok:{pid}", f"rcpt_no:{pid}", f"rcpt_nr:0:{pid}", f"rcpt_nr:t:{pid}"):
        await env.owner_cb(data, user_id=OTHER_OWNER)
        assert env.owner_alerts()[-1].get("show_alert") is True, data
    for bad in ("rcpt_ok:abc", "rcpt_ok:999999", "rcpt_no:", "rcpt_nr:9:" + str(pid), "rcpt_nr:x", "rcpt_ok:-5"):
        await env.owner_cb(bad)
        assert env.owner_alerts()[-1].get("show_alert") is True, bad
    assert await env.statuses() == {"receipt_submitted"}
    # مشتریِ دیگه نمی‌تونه روی گروهِ من عمل کنه
    for data in (f"pm_card:{g}", f"pm_manual:{g}", f"pay_receipt:{g}", f"pm_menu:{g}", "pm_card:zzz", "pm_bale:o999"):
        await env.cust_cb(data, user_id=CUSTOMER + 77)
        assert env.cust_alerts()[-1].get("show_alert") is True, data
    print("✅ test_stale_and_cross_shop_payment_ops PASSED")


# ============================================================================= بله‌پی (W4)
async def test_bale_new_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, bale=True)
    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"
    created: list[dict] = []

    async def fake_create(bot_token, provider_token, title, description, payload, amount_rial):
        created.append({"provider_token": provider_token, "payload": payload, "amount_rial": amount_rial})
        return f"https://fake-bale.test/{payload}"

    bale_service.create_invoice_link = fake_create
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    app_main._state["bot_manager"], app_main._state["main_bot"] = bot_manager, main_bot
    g = await env.checkout([p1, p2])
    assert f"pm_bale:{g}" in _datas(env.shop_bot.session.edited_texts[-1]["reply_markup"])
    await env.cust_cb(f"pm_bale:{g}")
    assert len(created) == 1 and created[0]["provider_token"] == "SHOP-OWN-PROVIDER-TOKEN" and created[0]["amount_rial"] == 2_500_000
    payment = (await _payments())[0]
    assert payment.method == "bale" and payment.provider_ref.startswith(f"cartgroup-{g}-")
    urls = [b.url for r in env.shop_bot.session.edited_texts[-1]["reply_markup"].inline_keyboard for b in r if b.url]
    assert urls and urls[0].startswith("https://fake-bale.test/")

    # ۱) استعلام ناموفق/مبلغِ اشتباه/نامشخص ⇒ هیچ تغییری
    async def inquire_wrong_amount(bot_token, transaction_id):
        return {"status": "succeed", "amount": 1}

    bale_service.inquire_transaction = inquire_wrong_amount
    await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-wrong")
    assert await env.statuses() == {"awaiting_payment"} and (await _payments())[0].status == "initiated"

    async def inquire_unknown(bot_token, transaction_id):
        return {"status": "weird"}

    bale_service.inquire_transaction = inquire_unknown
    await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-unknown")
    assert await env.statuses() == {"awaiting_payment"}

    async def inquire_pending(bot_token, transaction_id):
        return {"status": "pending", "amount": 2_500_000}

    bale_service.inquire_transaction = inquire_pending
    original_delays = app_main._BALE_RETRY_DELAYS
    app_main._BALE_RETRY_DELAYS = ()  # بدونِ تلاشِ مجدد در تست
    try:
        await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-pending")
    finally:
        app_main._BALE_RETRY_DELAYS = original_delays
    assert await env.statuses() == {"awaiting_payment"}

    # ۲) موفق ⇒ paid → processing (auto_accept) + اعلان‌ها + فاکتور
    async def inquire_ok(bot_token, transaction_id):
        return {"status": "succeed", "amount": 2_500_000}

    bale_service.inquire_transaction = inquire_ok
    owner_before = len(main_bot.session.sent_messages)
    await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-ok")
    assert await env.statuses() == {"processing"}
    done = (await _payments())[0]
    assert done.status == "paid" and done.transaction_ref == "tx-ok" and not done.needs_review
    assert len(main_bot.session.sent_messages) == owner_before + 1 and "بله‌پی" in main_bot.session.sent_messages[-1]["text"]
    assert any("تایید شد" in t for t in env.customer_msgs()) and len(env.shop_bot.session.sent_documents) == 1
    stock = await _product(p1)
    assert stock.stock_quantity == 2 and stock.reserved_quantity == 0

    # ۳) وب‌هوکِ تکراری ⇒ بی‌اثر
    count = len(env.customer_msgs())
    await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-ok")
    assert len(env.customer_msgs()) == count and len(main_bot.session.sent_messages) == owner_before + 1
    print("✅ test_bale_new_flow PASSED")


async def test_bale_late_payment_and_oversell(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, bale=True)
    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"

    async def fake_create(bot_token, provider_token, title, description, payload, amount_rial):
        return f"https://fake-bale.test/{payload}"

    async def inquire_ok(bot_token, transaction_id):
        return {"status": "succeed", "amount": 2_000_000}

    bale_service.create_invoice_link, bale_service.inquire_transaction = fake_create, inquire_ok
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    app_main._state["bot_manager"], app_main._state["main_bot"] = bot_manager, main_bot
    async with session_scope() as session:  # موجودیِ ۱ تا؛ قیمت ۲۰۰٬۰۰۰
        product = await session.get(Product, p1)
        product.stock_quantity = 1
    g = await env.checkout([p1])
    await env.cust_cb(f"pm_bale:{g}")
    payment = (await _payments())[0]
    await _set_deadline(-1)
    await payment_expiry_service.process_payment_expiry(main_bot, bot_manager)
    assert await env.statuses() == {"expired"} and (await _product(p1)).reserved_quantity == 0

    # پرداختِ دیرهنگام با موجودیِ آزاد ⇒ دوباره رزرو ⇒ paid/processing، بدونِ نیازِ بررسی
    await app_main._handle_bale_new_flow(payment.id, shop_bot_id, "tx-late-1")
    assert await env.statuses() == {"processing"} and not (await _payments())[0].needs_review
    assert "بعد از پایانِ مهلت" in main_bot.session.sent_messages[-1]["text"]
    assert (await _product(p1)).stock_quantity == 0

    # فروشِ بیش از موجودی: بعد از انقضا نفرِ دیگه آخرین واحد رو می‌خره، بعد پرداختِ دیرهنگام می‌رسه
    await _seed_second_scenario(env, shop_bot_id, p1)
    print("✅ test_bale_late_payment_and_oversell PASSED")


async def _seed_second_scenario(env: _Env, shop_bot_id: int, p1: int) -> None:
    async with session_scope() as session:
        product = await session.get(Product, p1)
        product.stock_quantity = 1
        product.reserved_quantity = 0
    g2 = await env.checkout([p1])
    await env.cust_cb(f"pm_bale:{g2}")
    pay2 = [p for p in await _payments() if p.group_id == g2][0]
    async with session_scope() as session:
        for r in (await session.execute(select(OrderConsultation).where(OrderConsultation.cart_checkout_group_id == g2))).scalars().all():
            r.reservation_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    await payment_expiry_service.process_payment_expiry(env.main_bot, env.bot_manager)
    g3 = await env.checkout([p1])  # آخرین واحد رو نفرِ دیگه رزرو کرد
    await app_main._handle_bale_new_flow(pay2.id, shop_bot_id, "tx-late-2")
    paid = [p for p in await _payments() if p.id == pay2.id][0]
    assert paid.status == "paid" and paid.needs_review, "پول گرفته شد ولی موجودی نبود ⇒ نیازِ بررسی"
    rows = [r for r in await env.rows() if r.cart_checkout_group_id == g2]
    assert {order_state.value_of(r.status) for r in rows} == {"paid"}, "autoaccept نمی‌شه؛ فروشگاه‌دار تصمیم می‌گیره"
    assert "نیازِ بررسیِ دستی" in env.main_bot.session.sent_messages[-1]["text"]
    assert {r.cart_checkout_group_id: order_state.value_of(r.status) for r in await env.rows()}[g3] == "awaiting_payment"


# ============================================================================= زرین‌پالِ فروشگاه (W4)
async def test_zarinpal_shop_flow(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    await _configure(shop_bot_id, zarinpal=True)
    settings.webhook_base_url = "https://shop.example.test"
    calls: dict[str, list] = {"request": [], "verify": []}

    async def fake_request(merchant_id, amount_toman, callback_url, description):
        calls["request"].append((merchant_id, amount_toman, callback_url))
        return f"AUTH{len(calls['request'])}", f"https://zp.test/start/AUTH{len(calls['request'])}"

    async def fake_verify(merchant_id, amount_toman, authority):
        calls["verify"].append((merchant_id, amount_toman, authority))
        return "REF777"

    zarinpal_service.request_payment, zarinpal_service.verify_payment = fake_request, fake_verify
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    app_main._state["bot_manager"], app_main._state["main_bot"] = bot_manager, main_bot
    g = await env.checkout([p1, p2])
    await env.cust_cb(f"pm_zarinpal:{g}")
    assert calls["request"] == [(MERCHANT, 250_000, "https://shop.example.test/payment/zarinpal/callback")], "مرچنتِ خودِ فروشگاه"
    await env.cust_cb(f"pm_zarinpal:{g}")  # تلاشِ دوم ⇒ اتوریتیِ تازه، پرداختِ قبلی منقضی
    pays = await _payments()
    assert [p.status for p in pays] == ["expired", "initiated"] and pays[1].provider_ref == "AUTH2"

    assert await app_main._zarinpal_shop_callback("UNKNOWN", "OK") is None, "اتوریتیِ ناشناس ⇒ مسیرِ پلتفرم"
    page = await app_main._zarinpal_shop_callback("AUTH2", "NOK")
    assert page.body == main_texts.ZARINPAL_PAYMENT_FAILED_PAGE.encode() and await env.statuses() == {"awaiting_payment"}
    assert calls["verify"] == []

    owner_before = len(main_bot.session.sent_messages)
    page = await app_main._zarinpal_shop_callback("AUTH2", "OK")
    assert page.body == main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE.encode()
    assert calls["verify"] == [(MERCHANT, 250_000, "AUTH2")]
    assert await env.statuses() == {"processing"} and (await _payments())[1].transaction_ref == "zp-REF777"
    assert len(main_bot.session.sent_messages) == owner_before + 1 and "زرین‌پال" in main_bot.session.sent_messages[-1]["text"]
    assert any("تایید شد" in t for t in env.customer_msgs())
    page = await app_main._zarinpal_shop_callback("AUTH2", "OK")  # بازگشتِ تکراری
    assert page.body == main_texts.ZARINPAL_PAYMENT_SUCCESSFUL_PAGE.encode() and len(calls["verify"]) == 1
    assert len(main_bot.session.sent_messages) == owner_before + 1
    print("✅ test_zarinpal_shop_flow PASSED")


async def main() -> None:
    from harness import build_test_dispatchers

    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()
    await test_pure_payment_helpers()
    await test_settings_ui_flow(shop_dp, main_dp, bot_manager, main_bot)
    await test_card_flow_approve(shop_dp, main_dp, bot_manager, main_bot)
    await test_card_flow_reject_retry_and_limit(shop_dp, main_dp, bot_manager, main_bot)
    await test_duplicate_receipt_flags(shop_dp, main_dp, bot_manager, main_bot)
    await test_manual_choice_keeps_legacy_flow(shop_dp, main_dp, bot_manager, main_bot)
    await test_expiry_job_and_expire_on_read(shop_dp, main_dp, bot_manager, main_bot)
    await test_payment_claim_guard_no_ai(shop_dp, main_dp, bot_manager, main_bot)
    await test_stale_and_cross_shop_payment_ops(shop_dp, main_dp, bot_manager, main_bot)
    await test_bale_new_flow(shop_dp, main_dp, bot_manager, main_bot)
    await test_bale_late_payment_and_oversell(shop_dp, main_dp, bot_manager, main_bot)
    await test_zarinpal_shop_flow(shop_dp, main_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
