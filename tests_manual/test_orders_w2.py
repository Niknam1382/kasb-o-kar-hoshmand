"""
تست: W2 (P1-S4) — ماشینِ وضعیتِ سفارش (`order_state`)، گذارِ گروهی (`order_transition_service`)،
عملیاتِ گروهیِ فروشگاه‌دار (`og_*`)، ردّ با دلیل/استرداد، «📦 سفارش‌هایِ من»، فاکتور، پیامِ مستقیم،
پیشنهادِ دکمه‌یِ سبد (C2) و فلگِ `legacy_ai_order_detection`.

نکته: EditMessageText در `FakeSession.edited_texts` ثبت می‌شود؛ SendMessage/SendDocument در `sent_*`.
اجرا: python3 tests_manual/test_orders_w2.py
"""
from __future__ import annotations

import asyncio
import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import (  # noqa: E402
    FakeSession,
    build_test_dispatchers,
    make_callback_update,
    make_message_update,
    register_fake_shop_bot,
    reset_database,
)
from shop_setup import seed_usable_shop  # noqa: E402
from checkout_helpers import run_checkout  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.bots.shop_bot import keyboards as shop_keyboards  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.bots.shop_bot.handlers import customer as customer_handlers  # noqa: E402
from app.bots.shop_bot.handlers.orders import parse_key  # noqa: E402
from app.database.models import (  # noqa: E402
    DirectMessage,
    Invoice,
    OrderConsultation,
    OrderEvent,
    OrderStatus,
    OrderType,
    Product,
    ShopBot,
)
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    accounting_service,
    ai_pool_service,
    campaign_service,
    cart_suggest_service,
    crm_service,
    customer_service,
    digital_service,
    invoice_service,
    order_service,
    order_state,
    order_transition_service,
    product_service,
)

OWNER = 7_100_000_001
SHOP_TG = 7_100_000_002
CUSTOMER = 7_100_000_003
OTHER_OWNER = 7_100_000_011
OTHER_SHOP_TG = 7_100_000_012
OTHER_CUSTOMER = 7_100_000_013


# ----------------------------------------------------------------------------- کمکی‌ها
async def _seed() -> tuple[int, int, int]:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER, SHOP_TG)
    async with session_scope() as session:
        p1 = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, stock_quantity=3)
        p2 = await product_service.create_product(session, shop_bot_id, "چای", None, 50_000, None, stock_quantity=None)
    return shop_bot_id, p1.id, p2.id


def _shop_bot_instance() -> Bot:
    return Bot(token=f"{SHOP_TG}:FAKE", session=FakeSession())


def _owner_bot() -> Bot:
    return Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())


class _Env:
    """دیسپچرها + ابزارکِ ارسالِ آپدیت با شمارنده‌یِ update_id."""

    def __init__(self, shop_dp, main_dp, bot_manager, main_bot, shop_bot_id: int, p1: int, p2: int) -> None:
        self.shop_dp, self.main_dp, self.bot_manager, self.main_bot = shop_dp, main_dp, bot_manager, main_bot
        self.shop_bot_id, self.p1, self.p2 = shop_bot_id, p1, p2
        self.shop_bot = _shop_bot_instance()
        register_fake_shop_bot(bot_manager, shop_bot_id, self.shop_bot)
        self.owner_bot = _owner_bot()
        self._n = 1000
        self._addr_saved = False  # دفترچه‌آدرسِ مشتری بعد از اولین چک‌اوت پر می‌شه (W5/C3)

    def _next(self) -> int:
        self._n += 1
        return self._n

    async def owner_cb(self, data: str, user_id: int = OWNER) -> None:
        await self.main_dp.feed_update(self.owner_bot, make_callback_update(self._next(), data=data, user_id=user_id))

    async def owner_say(self, text: str, user_id: int = OWNER) -> None:
        await self.main_dp.feed_update(self.owner_bot, make_message_update(self._next(), text=text, user_id=user_id))

    async def cust_cb(self, data: str, user_id: int = CUSTOMER) -> None:
        await self.shop_dp.feed_update(self.shop_bot, make_callback_update(self._next(), data=data, user_id=user_id))

    async def cust_say(self, text: str, user_id: int = CUSTOMER) -> None:
        await self.shop_dp.feed_update(self.shop_bot, make_message_update(self._next(), text=text, user_id=user_id))

    async def checkout(self, product_ids: list[int]) -> str:
        for pid in product_ids:
            await self.cust_cb(f"cart_add:{pid}")
        await run_checkout(self.cust_cb, self.cust_say, has_saved_addresses=self._addr_saved)  # W5/C3: چک‌اوتِ مرحله‌ایِ جدید
        self._addr_saved = True
        await self.cust_cb("cart_checkout_confirm")
        return await self.group_id()

    async def group_id(self) -> str:
        async with session_scope() as session:
            rows = list((await session.execute(select(OrderConsultation).order_by(OrderConsultation.id.desc()))).scalars().all())
            assert rows and rows[0].cart_checkout_group_id, "چک‌اوت باید گروه بسازه"
            return rows[0].cart_checkout_group_id  # گروهِ آخرین چک‌اوت

    async def rows(self) -> list[OrderConsultation]:
        async with session_scope() as session:
            return list((await session.execute(select(OrderConsultation).order_by(OrderConsultation.id))).scalars().all())

    async def statuses(self) -> set[str]:
        return {order_state.value_of(r.status) for r in await self.rows()}

    def customer_msgs(self) -> list[str]:
        return [m["text"] for m in self.shop_bot.session.sent_messages]

    def owner_alerts(self) -> list[dict]:
        return self.owner_bot.session.answered_callbacks

    def cust_alerts(self) -> list[dict]:
        return self.shop_bot.session.answered_callbacks


# ============================================================================= منطقِ خالص
async def test_order_state_tables_and_wiring() -> None:
    assert order_state.validate_tables() == [], order_state.validate_tables()
    assert order_state.can_transition("pending", "confirmed") and not order_state.can_transition("pending", "shipped")
    assert order_state.can_transition(OrderStatus.PAID, OrderStatus.PROCESSING)
    assert order_state.can_transition("paid", "completed"), "دیجیتال: paid → completed"
    assert not order_state.can_transition("completed", "processing") and not order_state.TRANSITIONS["refunded"]
    assert order_state.can_transition("awaiting_payment", "paid") and order_state.can_transition("receipt_submitted", "awaiting_payment")
    assert order_state.next_step("processing") == "shipped" and order_state.next_step("completed") is None

    # مصرف‌کننده‌ها از مجموعه‌یِ مرکزی می‌خونن
    assert "paid" in accounting_service.SUCCESS_STATUS_VALUES and "refunded" not in accounting_service.SUCCESS_STATUS_VALUES
    assert "refunded" in accounting_service.RELEASED_STATUS_VALUES
    assert set(accounting_service.STATUS_ORDER) == set(order_state.ALL_STATUSES)
    for v in ("awaiting_payment", "receipt_submitted", "paid", "refund_pending", "pending"):
        assert v in order_service.OPEN_ORDER_STATUS_VALUES, v
    assert "completed" not in order_service.OPEN_ORDER_STATUS_VALUES and "shipped" not in order_service.OPEN_ORDER_STATUS_VALUES
    assert OrderStatus.PAID in digital_service.DELIVERABLE_STATUSES and OrderStatus.PENDING not in digital_service.DELIVERABLE_STATUSES
    assert OrderStatus.REFUNDED in campaign_service.RELEASED_ORDER_STATUSES
    assert OrderStatus.PAID in crm_service.SUCCESS_STATUSES
    # هر وضعیتِ enum در order_state هست و برعکس
    assert {s.value for s in OrderStatus} == set(order_state.ALL_STATUSES)
    for v in order_state.ALL_STATUSES:
        assert main_texts.order_status_label(v) != v, f"برچسبِ فروشگاه‌دار برایِ {v}"
        assert shop_texts.customer_status_label(v) != v, f"برچسبِ مشتری برایِ {v}"
    print("✅ test_order_state_tables_and_wiring PASSED")


async def test_cart_suggest_pure() -> None:
    P = types.SimpleNamespace
    products = [
        P(id=1, name="برنج هاشمی", is_active=True, stock_quantity=5, reserved_quantity=0),
        P(id=2, name="چای ۲۵۰ گرمی", is_active=True, stock_quantity=None, reserved_quantity=0),
        P(id=3, name="روغن", is_active=True, stock_quantity=1, reserved_quantity=1),
        P(id=4, name="زعفران", is_active=False, stock_quantity=None, reserved_quantity=0),
        P(id=5, name="ک", is_active=True, stock_quantity=None, reserved_quantity=0),
    ]
    text = "پیشنهاد من چاي ٢٥٠ گرمي و برنج‌هاشمی (ك) است؛ روغن و زعفران هم داریم"
    found = cart_suggest_service.suggest_cart_products(text, products)
    assert [p.id for p in found] == [2, 1], [p.id for p in found]  # ي/ك/ارقام نرمال؛ ZWNJ؛ نابود/غیرفعال/تک‌حرفی رد
    assert cart_suggest_service.suggest_cart_products("", products) == []
    many = [P(id=i, name=f"کالا{i}", is_active=True, stock_quantity=None, reserved_quantity=0) for i in range(10, 16)]
    assert len(cart_suggest_service.suggest_cart_products(" ".join(p.name for p in many), many)) == 3
    kb = shop_keyboards.cart_suggest_keyboard(found, show_cart_row=True)
    datas = [b.callback_data for row in kb.inline_keyboard for b in row]
    assert datas == ["cart_add:2", "cart_add:1", "cart_view", "cart_checkout_start"], datas
    assert all(len(d.encode()) <= 64 for d in datas)
    print("✅ test_cart_suggest_pure PASSED")


async def test_invoice_pure_and_keys() -> None:
    import datetime

    P = types.SimpleNamespace
    row = P(
        id=5, product_id=1, quantity=2, estimated_value_toman=90_000, discount_toman=10_000, summary="خلاصه",
        shipping_fee_toman=20_000, shipping_method_name="پست", customer_phone="+989121234567", customer_address="تهران",
        checkout_answers=None, payment_method=None, status="pending", cart_checkout_group_id=None,
    )
    customer = P(first_name="علی", last_name=None, username=None, phone_number=None)
    data = invoice_service.build_invoice_data(
        "INV-1-202610-1", datetime.datetime.now(datetime.timezone.utc), [row],
        {1: P(name="<b>برنج</b>", kind="physical")}, customer, "@shop",
    )
    assert data["list_total"] == 100_000 and data["discount"] == 10_000 and data["shipping"] == 20_000 and data["total"] == 110_000, data
    assert data["paid"] is False and data["payment_method"] == "manual"
    text = invoice_service.format_invoice_text(data)
    assert "INV-1-202610-1" in text and "۱۱۰٬۰۰۰" in text and "پرداخت در محل" in text
    html_doc = invoice_service.build_invoice_html(data)
    assert "dir='rtl'" in html_doc and "<b>برنج</b>" not in html_doc and "&lt;b&gt;" in html_doc, "escape"
    assert "http" not in html_doc, "بدونِ منبعِ خارجی"
    paid = dict(data, paid=True, payment_method="bale")
    assert "پرداخت‌شده" in invoice_service.format_invoice_text(paid)

    assert parse_key("o123") == ("single", 123) and parse_key("o") == ("bad", None) and parse_key("o1²") == ("bad", None)
    assert parse_key("0a1b2c3d4e5f0a1b2c3d4e5f")[0] == "group" and parse_key("ZZZ")[0] == "bad" and parse_key("")[0] == "bad"
    key = "0a1b2c3d4e5f0a1b2c3d4e5f"
    for status in order_state.ALL_STATUSES:
        kb = main_keyboards.order_group_actions_keyboard(key, status)
        for row_ in kb.inline_keyboard:
            for b in row_:
                assert len(b.callback_data.encode()) <= 64, b.callback_data
    kb = main_keyboards.order_reject_reasons_keyboard(key, main_texts.ORDER_REJECT_REASONS)
    assert all(len(b.callback_data.encode()) <= 64 for r in kb.inline_keyboard for b in r)
    print("✅ test_invoice_pure_and_keys PASSED")


# ============================================================================= سرویس + DB
async def test_transition_service_paid_flow() -> None:
    shop_bot_id, p1, _p2 = await _seed()
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER, "علی", None)
        order = await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, "برنج × 2", 400_000, product_id=p1, quantity=2)
        assert order.stock_reserved
        order.status = OrderStatus.AWAITING_PAYMENT
        await session.flush()

        res = await order_transition_service.transition_group(session, order, "shipped", actor_type="owner")
        assert not res.ok and res.reason == "illegal" and order.status == OrderStatus.AWAITING_PAYMENT

        res = await order_transition_service.transition_group(session, order, order_state.PAID, actor_type="system")
        assert res.ok and res.changed
        product = await session.get(Product, p1)
        assert product.stock_quantity == 1 and product.reserved_quantity == 0, (product.stock_quantity, product.reserved_quantity)
        assert order.paid_at is not None and order.confirmed and not order.stock_reserved

        res = await order_transition_service.transition_group(session, order, order_state.PROCESSING)
        assert res.ok and res.changed
        events_before = len(await order_transition_service.get_timeline(session, order))
        res = await order_transition_service.transition_group(session, order, order_state.PROCESSING)
        assert res.ok and not res.changed, "ایدمپوتنت"
        assert len(await order_transition_service.get_timeline(session, order)) == events_before == 2
        res = await order_transition_service.transition_group(session, order, order_state.PAID)
        assert not res.ok, "processing → paid مجاز نیست"

        res = await order_transition_service.transition_group(session, order, order_state.SHIPPED, tracking_code="T-9", carrier_name="پست")
        assert res.ok and order.tracking_code == "T-9" and order.carrier_name == "پست"
        res = await order_transition_service.customer_cancel_group(session, order, customer_id=customer.id)
        assert not res.ok, "بعد از پرداخت لغوِ مشتری ممنوع"
        res = await order_transition_service.reject_or_refund_group(session, order, reason="خراب")
        assert res.ok and res.to_status == order_state.REFUND_PENDING and order.cancel_reason == "خراب"
        res = await order_transition_service.transition_group(session, order, order_state.REFUNDED)
        assert res.ok
        assert order_transition_service.group_total_toman([order]) == 400_000
    print("✅ test_transition_service_paid_flow PASSED")


async def test_legacy_flag_off_no_order_detection(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, _p1, _p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, _p1, _p2)
    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.legacy_ai_order_detection is True, "seed: تست‌هایِ قدیمی با فلگِ روشن"
        shop_bot.legacy_ai_order_detection = False
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, CUSTOMER, "علی", None)
        customer_id = customer.id

    calls: list[int] = []
    original = ai_pool_service.build_ai_service

    async def boom(*args, **kwargs):
        calls.append(1)
        raise AssertionError("نباید AI صدا زده بشه")

    ai_pool_service.build_ai_service = boom
    try:
        history = [{"role": "user", "content": "برنج می‌خوام، آدرسم تهران، ۰۹۱۲۰۰۰۰۰۰۰"}]
        await customer_handlers._detect_and_notify_order(shop_bot_id, customer_id, history, env.shop_bot, main_bot)
    finally:
        ai_pool_service.build_ai_service = original
    assert not calls, "فلگِ خاموش ⇒ هزینه/فراخوانیِ AIِ تشخیصِ سفارش صفر"
    assert await env.rows() == [], "چتِ خرید سفارش نمی‌سازه"
    print("✅ test_legacy_flag_off_no_order_detection PASSED")


# ============================================================================= عملیاتِ فروشگاه‌دار
async def test_lifecycle_group_ops(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1, p2])
    assert await env.statuses() == {"pending"}

    await env.owner_cb(f"confirm_cart_group:{g}")
    assert await env.statuses() == {"confirmed"}

    await env.owner_cb(f"og_start:{g}")
    assert await env.statuses() == {"processing"}
    assert "آماده‌سازی" in env.customer_msgs()[-1]
    count = len(env.customer_msgs())
    await env.owner_cb(f"og_start:{g}")  # دابل‌تپ
    assert len(env.customer_msgs()) == count, "دابل‌تپ = یک اعلان"

    await env.owner_cb(f"og_ship:{g}")
    await env.owner_say("TRK-123")
    assert await env.statuses() == {"shipped"}
    assert all(r.tracking_code == "TRK-123" for r in await env.rows())
    assert "TRK-123" in env.customer_msgs()[-1] and "ارسال" in env.customer_msgs()[-1]

    await env.owner_cb(f"og_done:{g}")
    assert await env.statuses() == {"completed"}
    assert all(r.delivered_at is not None for r in await env.rows())
    assert "تکمیل" in env.customer_msgs()[-1]

    async with session_scope() as session:
        events = list((await session.execute(select(OrderEvent).order_by(OrderEvent.id))).scalars().all())
    assert [e.to_status for e in events] == ["confirmed", "processing", "shipped", "completed"], [e.to_status for e in events]
    assert all(e.group_id == g for e in events)

    await env.owner_cb(f"og_start:{g}")  # از completed مجاز نیست
    assert env.owner_alerts()[-1].get("text") == main_texts.ORDER_OPS_ILLEGAL
    assert await env.statuses() == {"completed"}
    print("✅ test_lifecycle_group_ops PASSED")


async def test_reject_with_reason_and_stale_keys(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1, p2])
    async with session_scope() as session:
        assert (await session.get(Product, p1)).reserved_quantity == 1

    await env.owner_cb(f"og_rej:{g}")
    assert main_texts.ORDER_ASK_REJECT_REASON in env.owner_bot.session.edited_texts[-1]["text"]
    await env.owner_cb(f"og_rr:0:{g}")
    assert await env.statuses() == {"rejected"}
    async with session_scope() as session:
        assert (await session.get(Product, p1)).reserved_quantity == 0, "رزرو آزاد شد"
    last = env.customer_msgs()[-1]
    assert main_texts.ORDER_REJECT_REASONS[0] in last and "نتونست" in last
    count = len(env.customer_msgs())
    await env.owner_cb(f"og_rr:0:{g}")
    assert len(env.customer_msgs()) == count, "دابل‌تپِ ردّ = یک اعلان"

    for bad in ("og_rr:9:" + g, "og_rr:x:" + g, "og_rr:0:zzz", "og_start:o999999", "og_ship:bogus", "og_msg:o999999", "og_rej:bogus"):
        await env.owner_cb(bad)
        assert env.owner_alerts()[-1].get("show_alert") is True, bad
    assert await env.statuses() == {"rejected"}

    # ردِ متنیِ آزاد
    await env.checkout([p2])
    async with session_scope() as session:
        g2 = (await session.execute(select(OrderConsultation).order_by(OrderConsultation.id.desc()))).scalars().first().cart_checkout_group_id
    await env.owner_cb(f"og_rr:t:{g2}")
    await env.owner_say("x" * 301)
    assert main_texts.ORDER_ASK_REJECT_TEXT in env.owner_bot.session.sent_messages[-1]["text"], "طولانی ⇒ دوباره می‌پرسه"
    await env.owner_say("فعلاً ارسال نداریم")
    rows = [r for r in await env.rows() if r.cart_checkout_group_id == g2]
    assert rows and all(order_state.value_of(r.status) == "rejected" and r.cancel_reason == "فعلاً ارسال نداریم" for r in rows)
    assert "فعلاً ارسال نداریم" in env.customer_msgs()[-1]
    print("✅ test_reject_with_reason_and_stale_keys PASSED")


async def test_refund_path(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.owner_cb(f"confirm_cart_group:{g}")
    async with session_scope() as session:
        assert (await session.get(Product, p1)).stock_quantity == 2
    await env.owner_cb(f"og_rr:3:{g}")  # confirmed ⇒ refund_pending (نه rejected)
    assert await env.statuses() == {"refund_pending"}
    assert "استرداد" in env.customer_msgs()[-1]
    await env.owner_cb(f"og_start:{g}")
    assert env.owner_alerts()[-1].get("text") == main_texts.ORDER_OPS_ILLEGAL
    await env.owner_cb(f"og_refunded:{g}")
    assert await env.statuses() == {"refunded"}
    assert "استرداد" in env.customer_msgs()[-1]
    print("✅ test_refund_path PASSED")


async def test_cross_shop_ops_blocked(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await seed_usable_shop(OTHER_OWNER, OTHER_SHOP_TG)
    for data in (f"og_start:{g}", f"og_rr:0:{g}", f"og_msg:{g}", f"og_done:{g}"):
        await env.owner_cb(data, user_id=OTHER_OWNER)
        assert env.owner_alerts()[-1].get("show_alert") is True, data
    assert await env.statuses() == {"pending"}
    print("✅ test_cross_shop_ops_blocked PASSED")


async def test_direct_message(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    await env.owner_cb(f"og_msg:{g}")
    await env.owner_say("y" * 1001)
    assert env.owner_bot.session.sent_messages[-1]["text"] == main_texts.ORDER_DIRECT_TOO_LONG
    await env.owner_say("سلام، سفارشت آماده‌ست")
    assert env.customer_msgs()[-1] == shop_texts.DIRECT_MESSAGE_PREFIX + "سلام، سفارشت آماده‌ست"
    assert env.owner_bot.session.sent_messages[-1]["text"] == main_texts.ORDER_DIRECT_SENT

    bot_manager._bots.pop(shop_bot_id)  # رباتِ فروشگاه در دسترس نیست
    await env.owner_cb(f"og_msg:{g}")
    await env.owner_say("پیام دوم")
    assert env.owner_bot.session.sent_messages[-1]["text"] == main_texts.ORDER_DIRECT_BLOCKED
    async with session_scope() as session:
        msgs = list((await session.execute(select(DirectMessage).order_by(DirectMessage.id))).scalars().all())
    assert [m.delivered for m in msgs] == [True, False] and msgs[0].body == "سلام، سفارشت آماده‌ست"
    print("✅ test_direct_message PASSED")


# ============================================================================= سمتِ مشتری
async def test_my_orders_flow_and_invoice(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    await env.cust_say(shop_texts.BTN_MY_ORDERS)
    assert env.customer_msgs()[-1] == shop_texts.MY_ORDERS_EMPTY

    g = await env.checkout([p1, p2])
    await env.owner_cb(f"confirm_cart_group:{g}")
    await env.cust_say(shop_texts.BTN_MY_ORDERS)
    msg = env.shop_bot.session.sent_messages[-1]
    assert shop_texts.customer_status_label("confirmed") in msg["text"] and "برنج" in msg["text"] and "چای" in msg["text"]
    datas = [b.callback_data for row in msg["reply_markup"].inline_keyboard for b in row]
    assert datas == [f"myord_view:{g}"], datas

    await env.cust_cb(f"myord_view:{g}")
    card = env.shop_bot.session.edited_texts[-1]["text"]
    assert "خط‌زمان" in card and shop_texts.customer_status_label("confirmed") in card
    card_datas = [b.callback_data for row in env.shop_bot.session.edited_texts[-1]["reply_markup"].inline_keyboard for b in row]
    assert f"myord_inv:{g}" in card_datas and f"myord_cancel:{g}" not in card_datas

    await env.cust_cb(f"myord_inv:{g}")
    await env.cust_cb(f"myord_inv:{g}")
    assert len(env.shop_bot.session.sent_documents) == 2
    invoice_texts = [t for t in env.customer_msgs() if t.startswith("🧾 فاکتورِ INV-")]
    assert len(invoice_texts) == 2 and invoice_texts[0] == invoice_texts[1], "دوباره‌ارسال = همان شماره/متن"
    async with session_scope() as session:
        assert len(list((await session.execute(select(Invoice))).scalars().all())) == 1
    assert f"INV-{shop_bot_id}-" in invoice_texts[0] and "۲۵۰٬۰۰۰" in invoice_texts[0]

    # امنیت/کهنگی
    await env.cust_cb(f"myord_view:{g}", user_id=OTHER_CUSTOMER)
    assert env.cust_alerts()[-1].get("text") == shop_texts.MY_ORDER_STALE
    for bad in ("zzz", "o999999", "", "o1²"):
        await env.cust_cb(f"myord_view:{bad}")
        assert env.cust_alerts()[-1].get("text") == shop_texts.MY_ORDER_STALE, bad
    for bad_page in ("x", "99999", "-1"):
        await env.cust_cb(f"myord_page:{bad_page}")
    await env.cust_cb(f"myord_cancel:{g}")
    assert env.cust_alerts()[-1].get("text") == shop_texts.MY_ORDER_CANNOT_CANCEL
    assert await env.statuses() == {"confirmed"}
    print("✅ test_my_orders_flow_and_invoice PASSED")


async def test_customer_cancel_before_payment(shop_dp, main_dp, bot_manager, main_bot) -> None:
    shop_bot_id, p1, p2 = await _seed()
    env = _Env(shop_dp, main_dp, bot_manager, main_bot, shop_bot_id, p1, p2)
    g = await env.checkout([p1])
    async with session_scope() as session:
        assert (await session.get(Product, p1)).reserved_quantity == 1
        for r in await order_service.get_by_cart_checkout_group(session, g):
            r.status = OrderStatus.AWAITING_PAYMENT  # W3 این وضعیت رو می‌سازه؛ این‌جا دستی

    await env.cust_cb(f"myord_view:{g}")
    kb = env.shop_bot.session.edited_texts[-1]["reply_markup"]
    assert f"myord_cancel:{g}" in [b.callback_data for row in kb.inline_keyboard for b in row]

    owner_msgs = len(main_bot.session.sent_messages)
    await env.cust_cb(f"myord_cancel:{g}")
    assert await env.statuses() == {"cancelled"}
    async with session_scope() as session:
        assert (await session.get(Product, p1)).reserved_quantity == 0, "رزرو آزاد شد"
    assert len(main_bot.session.sent_messages) == owner_msgs + 1 and "لغو" in main_bot.session.sent_messages[-1]["text"]
    await env.cust_cb(f"myord_cancel:{g}")  # دابل‌تپ
    assert len(main_bot.session.sent_messages) == owner_msgs + 1, "دابل‌تپِ لغو = یک اعلان"
    async with session_scope() as session:
        assert (await session.get(Product, p1)).reserved_quantity == 0
    print("✅ test_customer_cancel_before_payment PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()

    await test_order_state_tables_and_wiring()
    await test_cart_suggest_pure()
    await test_invoice_pure_and_keys()
    await test_transition_service_paid_flow()
    await test_legacy_flag_off_no_order_detection(shop_dp, main_dp, bot_manager, main_bot)
    await test_lifecycle_group_ops(shop_dp, main_dp, bot_manager, main_bot)
    await test_reject_with_reason_and_stale_keys(shop_dp, main_dp, bot_manager, main_bot)
    await test_refund_path(shop_dp, main_dp, bot_manager, main_bot)
    await test_cross_shop_ops_blocked(shop_dp, main_dp, bot_manager, main_bot)
    await test_direct_message(shop_dp, main_dp, bot_manager, main_bot)
    await test_my_orders_flow_and_invoice(shop_dp, main_dp, bot_manager, main_bot)
    await test_customer_cancel_before_payment(shop_dp, main_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
