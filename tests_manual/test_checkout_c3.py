"""
تست: چک‌اوتِ مرحله‌ایِ سبد (W5 · C3) + پیشنهادِ AI برایِ ویرایشِ سبد (C2) — از دیسپچرِ واقعیِ ربات فروشگاهی.

پوشش: اعتبارسنج‌ها و منطقِ خالص، دفترچه‌آدرس (سقف/پیش‌فرض/حذف/ایزولاسیون)، جریانِ کاملِ فیزیکی، آدرسِ ذخیره‌شده،
انتخابِ روشِ ارسال و اثرش روی مبلغ، ارسالِ رایگان، سبدِ دیجیتال، برگشت/ویرایش/دکمه‌یِ کهنه/ورودیِ نامعتبر،
دابل‌تپِ «ثبتِ نهایی»، تغییرِ هزینه‌یِ ارسال بینِ پیش‌نمایش و ثبت، و سرویسِ پیشنهادِ AI.

اجرا: python3 tests_manual/test_checkout_c3.py
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from checkout_helpers import run_checkout  # noqa: E402

from app.bots.common import wizard_nav  # noqa: E402
from app.bots.main_bot import texts  # noqa: E402
from app.database.models import CartAiProposal, Customer, OrderConsultation  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import (  # noqa: E402
    address_book_service,
    cart_edit_service,
    cart_proposal_service,
    checkout_flow,
    order_transition_service,
    product_service,
    shipping_service,
)
from app.utils import validators  # noqa: E402

OWNER_TG_ID = 999801
SHOP_BOT_TG_ID = 999802
_user_counter = 999810


def _fresh_user_id() -> int:
    global _user_counter
    _user_counter += 1
    return _user_counter


class _Shopper:
    def __init__(self, shop_dp) -> None:
        self.dp = shop_dp
        self.user_id = _fresh_user_id()
        self.bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
        self.session: FakeSession = self.bot.session  # type: ignore[assignment]
        self._n = self.user_id * 1000

    async def say(self, text: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_message_update(self._n, text=text, user_id=self.user_id))

    async def tap(self, data: str) -> None:
        self._n += 1
        await self.dp.feed_update(self.bot, make_callback_update(self._n, data=data, user_id=self.user_id))

    @property
    def last_text(self) -> str:
        return self.session.sent_messages[-1]["text"]

    @property
    def last_markup(self):
        return self.session.sent_messages[-1]["reply_markup"]

    def last_callbacks(self) -> list[str]:
        markup = self.last_markup
        return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []

    @property
    def last_alert(self) -> dict:
        return self.session.answered_callbacks[-1]

    async def add(self, *product_ids: int) -> None:
        for product_id in product_ids:
            await self.tap(f"cart_add:{product_id}")


async def _seed(*, shipping: list[tuple[str, int, int | None]] | None = None) -> tuple[int, int, int]:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        rice = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, stock_quantity=50)
        tea = await product_service.create_product(session, shop_bot_id, "چای", None, 50_000, None, stock_quantity=None)
        for name, fee, free_over in shipping or []:
            await shipping_service.create_method(session, shop_bot_id, name, fee, free_over, "۲ تا ۳ روز")
    return shop_bot_id, rice.id, tea.id


async def _orders(shop_bot_id: int) -> list[OrderConsultation]:
    async with session_scope() as session:
        result = await session.execute(
            select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id).order_by(OrderConsultation.id)
        )
        return list(result.scalars().all())


async def _customer(user_id: int) -> Customer:
    async with session_scope() as session:
        return (await session.execute(select(Customer).where(Customer.telegram_id == user_id))).scalar_one()


# =============================================================================
# منطقِ خالص
# =============================================================================
async def test_validators_and_flow_logic() -> None:
    assert validators.is_valid_postal_code("۱۲۳۴۵۶۷۸۹۰") == "1234567890"
    assert validators.is_valid_postal_code("12345-67890") == "1234567890"
    for bad in ("0234567890", "1234067890", "123456789", "12345678901", "abcdefghij", "", None):
        assert validators.is_valid_postal_code(bad) is None, bad
    assert validators.clean_person_name("  علی   رضایی ") == "علی رضایی"
    for bad in ("a", "علی۱", "@ali", "x" * 61, "https://t.me/x", ""):
        assert validators.clean_person_name(bad) is None, bad
    assert validators.clean_place_name("تهران") == "تهران" and validators.clean_place_name("شهر۲") is None
    assert validators.clean_address_text("کوتاه") is None and validators.clean_address_text("x" * 401) is None
    assert validators.clean_address_text("خیابان آزادی\n\n پلاک 10") == "خیابان آزادی\nپلاک 10"

    nxt = checkout_flow.next_position
    assert nxt("name", physical=True, ship_choice=False, has_questions=False) == "phone"
    assert nxt("phone", physical=True, ship_choice=False, has_questions=False) == "addr_pick"
    assert nxt("phone", physical=False, ship_choice=True, has_questions=True) == "qa", "دیجیتال: بدونِ آدرس/ارسال"
    assert nxt("postal", physical=True, ship_choice=True, has_questions=True) == "ship"
    assert nxt("ship", physical=True, ship_choice=True, has_questions=False) == "note"
    assert nxt("note", physical=True, ship_choice=False, has_questions=False) == "preview"
    assert checkout_flow.shipping_fee(50_000, 100_000, 100_000) == 0
    assert checkout_flow.shipping_fee(50_000, 100_000, 99_999) == 50_000
    assert checkout_flow.custom_questions(None) == [] and checkout_flow.custom_questions("الف\n\nب") == ["الف", "ب"]
    assert checkout_flow.pop_history([]) == (None, [])

    row = wizard_nav.nav_row(back_cb="b", skip_cb="s", cancel_cb="c")
    assert [x.text for x in row] == [wizard_nav.BTN_BACK, wizard_nav.BTN_SKIP, wizard_nav.BTN_CANCEL]
    assert wizard_nav.nav_row() == []
    print("✅ test_validators_and_flow_logic PASSED")


async def test_proposal_ops_roundtrip() -> None:
    ops = [
        cart_edit_service.CartOperation("add", 5, 2),
        cart_edit_service.CartOperation("remove", 7, None),
        cart_edit_service.CartOperation("clear", None, None),
    ]
    back = cart_proposal_service.deserialize_ops(cart_proposal_service.serialize_ops(ops))
    assert [(o.action, o.product_id, o.quantity) for o in back] == [("add", 5, 2), ("remove", 7, None)], "clear هرگز ذخیره نمی‌شه"
    tampered = '[{"a":"clear","p":1,"q":1},{"a":"add","p":"x","q":1},{"a":"add","p":3,"q":0},{"a":"add","p":3,"q":99999},{"a":"set","p":4,"q":2}]'
    assert [(o.action, o.product_id) for o in cart_proposal_service.deserialize_ops(tampered)] == [("set", 4)]
    assert cart_proposal_service.deserialize_ops("not json") == [] and cart_proposal_service.deserialize_ops("{}") == []
    print("✅ test_proposal_ops_roundtrip PASSED")


# =============================================================================
# دفترچه‌آدرس
# =============================================================================
async def test_address_book_rules() -> None:
    shop_bot_id, _rice, _tea = await _seed()
    async with session_scope() as session:
        from app.services import customer_service

        c1 = await customer_service.get_or_create_customer(session, shop_bot_id, 880001, "الف", None)
        c2 = await customer_service.get_or_create_customer(session, shop_bot_id, 880002, "ب", None)
        c1_id, c2_id = c1.id, c2.id
        first = await address_book_service.add_address(session, c1_id, province="تهران", city="تهران", address="خیابان آزادی پلاک ۱", postal_code=None)
        assert first.is_default, "اولین آدرس خودکار پیش‌فرض می‌شه"
        second = await address_book_service.add_address(session, c1_id, province="البرز", city="کرج", address="میدان اصلی پلاک ۲", postal_code="1234567890")
        assert not second.is_default
        for index in range(address_book_service.MAX_ADDRESSES - 2):
            assert await address_book_service.add_address(session, c1_id, province="الف", city="ب", address=f"آدرسِ شماره {index}۰۰۰", postal_code=None)
        assert await address_book_service.add_address(session, c1_id, province="الف", city="ب", address="آدرسِ ششم اضافی", postal_code=None) is None, "سقفِ ۵"
        first_id, second_id = first.id, second.id

    async with session_scope() as session:
        assert await address_book_service.set_default(session, c1_id, second_id)
        rows = await address_book_service.list_addresses(session, c1_id)
        assert rows[0].id == second_id and sum(r.is_default for r in rows) == 1
        # ایزولاسیون: مشتریِ دیگه نه می‌بینه، نه پیش‌فرض/حذف می‌کنه
        assert await address_book_service.get_owned(session, first_id, c2_id) is None
        assert not await address_book_service.set_default(session, c2_id, first_id)
        assert not await address_book_service.delete_address(session, c2_id, first_id)
        assert await address_book_service.list_addresses(session, c2_id) == []
        # حذفِ پیش‌فرض ⇒ یکی دیگه پیش‌فرض می‌شه
        assert await address_book_service.delete_address(session, c1_id, second_id)
        rows = await address_book_service.list_addresses(session, c1_id)
        assert len(rows) == address_book_service.MAX_ADDRESSES - 1 and sum(r.is_default for r in rows) == 1
        text = address_book_service.format_address(rows[0])
        assert rows[0].province in text and rows[0].city in text
    print("✅ test_address_book_rules PASSED")


# =============================================================================
# جریانِ کاملِ فیزیکی
# =============================================================================
async def test_full_physical_flow_saves_everything(shop_dp, main_bot) -> None:
    shop_bot_id, rice, tea = await _seed()
    main_bot.session.sent_messages.clear()
    s = _Shopper(shop_dp)
    await s.add(rice, tea)
    await run_checkout(s.tap, s.say, postal="1234567890", note="لطفاً زنگ نزنید")
    preview = s.last_text
    assert "علی رضایی" in preview and "+989120000000" in preview and "تهران" in preview and "1234567890" in preview
    assert "لطفاً زنگ نزنید" in preview and "250,000" in preview
    assert "ck_edit:name" in s.last_callbacks() and "ck_edit:addr" in s.last_callbacks()
    assert "ck_edit:ship" not in s.last_callbacks(), "بدونِ روشِ ارسال دکمه‌یِ ویرایشِ ارسال نمی‌آید"

    await s.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 2 and sorted(o.estimated_value_toman for o in orders) == [50_000, 200_000]
    assert all(o.customer_phone == "+989120000000" for o in orders)
    assert all(o.customer_address and "تهران" in o.customer_address and "1234567890" in o.customer_address for o in orders)
    assert all("علی رضایی" in (o.checkout_answers or "") and "لطفاً زنگ نزنید" in o.checkout_answers for o in orders)
    assert all(not o.shipping_fee_toman for o in orders)
    customer = await _customer(s.user_id)
    assert customer.phone_number == "+989120000000"
    async with session_scope() as session:
        rows = await address_book_service.list_addresses(session, customer.id)
        assert len(rows) == 1 and rows[0].is_default and rows[0].postal_code == "1234567890"
    owner_text = main_bot.session.sent_messages[0]["text"]
    assert "+989120000000" in owner_text and "علی رضایی" in owner_text
    # B8: سبدِ فیزیکی بدونِ هیچ روشِ ارسال ⇒ هشدارِ روشن در اعلانِ فروشگاه‌دار
    assert texts.OWNER_NO_SHIPPING_METHOD_WARNING in owner_text, "بدونِ روشِ ارسال باید به فروشگاه‌دار هشدار داد"
    # B8: جمعِ قابلِ پرداخت همیشه در پیش‌نمایش هست (حتی بدونِ روشِ ارسال)
    assert f"💳 مبلغِ قابلِ پرداخت: {validators.format_toman(250_000)}" in preview, preview
    print("✅ test_full_physical_flow_saves_everything PASSED")


async def test_saved_address_chooser_manage_and_cap(shop_dp) -> None:
    shop_bot_id, rice, _tea = await _seed()
    s = _Shopper(shop_dp)
    await s.add(rice)
    await run_checkout(s.tap, s.say)  # آدرسِ اول ذخیره می‌شه
    await s.tap("cart_checkout_cancel")

    await s.tap("cart_checkout_start")
    await s.say("علی رضایی")
    await s.say("09121112233")
    assert any(c.startswith("ck_addr_sel:") for c in s.last_callbacks()) and "ck_addr_new" in s.last_callbacks()
    assert "ck_addr_mng" in s.last_callbacks()
    customer = await _customer(s.user_id)
    assert customer.phone_number == "+989121112233"

    # مدیریت: پیش‌فرض/حذف با آدرسِ دیگران رد می‌شه
    await s.tap("ck_addr_mng")
    assert "مدیریت" in s.last_text or "آدرس‌هایِ ذخیره‌شده" in s.last_text
    await s.tap("ck_addr_del:999999")
    assert s.last_alert["show_alert"] is True
    await s.tap("ck_addr_pick")
    selector = next(c for c in s.last_callbacks() if c.startswith("ck_addr_sel:"))
    await s.tap(selector)
    await s.tap("ck_skip")  # مرحله‌یِ «توضیح» (اختیاری)
    assert "ثبت بشه؟" in s.last_text and "تهران" in s.last_text

    # آدرسِ ذخیره‌شده‌ی کسِ دیگه انتخاب‌شدنی نیست
    other = _Shopper(shop_dp)
    await other.add(rice)
    await other.tap("cart_checkout_start")
    await other.say("نفرِ دوم")
    await other.say("09123334455")
    await other.tap(selector)  # دکمه‌یِ مشتریِ اول در چک‌اوتِ مشتریِ دوم (او آدرسی ندارد ⇒ در مرحله‌یِ استان)
    assert "ثبت بشه؟" not in other.last_text
    print("✅ test_saved_address_chooser_manage_and_cap PASSED")


# =============================================================================
# ارسال
# =============================================================================
async def test_shipping_choice_fee_free_over_and_confirm(shop_dp, main_bot) -> None:
    shop_bot_id, rice, tea = await _seed(shipping=[("پست", 40_000, None), ("پیک", 90_000, 200_000)])
    async with session_scope() as session:
        methods = await shipping_service.list_methods(session, shop_bot_id, only_active=True)
        post, courier = methods[0].id, methods[1].id
    main_bot.session.sent_messages.clear()

    s = _Shopper(shop_dp)
    await s.add(tea)  # ۵۰٬۰۰۰ تومان
    await s.tap("cart_checkout_start")
    await s.say("علی رضایی")
    await s.say("09120000000")
    await s.say("تهران")
    await s.say("تهران")
    await s.say("خیابانِ آزادی، پلاکِ ده")
    await s.tap("ck_skip")
    assert any(c.startswith("ck_ship:") for c in s.last_callbacks()), "با ≥۲ روش باید انتخاب بپرسه"
    assert "40,000" in s.last_text or any("40,000" in b.text for row in s.last_markup.inline_keyboard for b in row)
    await s.tap(f"ck_ship:{post}")
    await s.tap("ck_skip")
    assert "پست" in s.last_text and "40,000" in s.last_text and "90,000" in s.last_text, s.last_text  # جمعِ ۵۰ + ۴۰
    assert "ck_edit:ship" in s.last_callbacks()

    await s.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 1 and orders[0].estimated_value_toman == 50_000, "مبلغِ سفارش *بدونِ* ارسال ذخیره می‌شه"
    assert orders[0].shipping_fee_toman == 40_000 and orders[0].shipping_method_name == "پست"
    assert order_transition_service.group_total_toman(orders) == 90_000, "جمعِ گروه = اقلام + ارسال"
    assert "90,000" in main_bot.session.sent_messages[-1]["text"]

    # ارسالِ رایگان بالایِ آستانه: برنج (۲۰۰٬۰۰۰) با پیک رایگان
    s2 = _Shopper(shop_dp)
    await s2.add(rice)
    await run_checkout(s2.tap, s2.say, ship_method_id=courier)
    assert "رایگان" in s2.last_text and "200,000" in s2.last_text
    await s2.tap("cart_checkout_confirm")
    free = (await _orders(shop_bot_id))[-1]
    assert free.shipping_fee_toman == 0 and free.shipping_method_name == "پیک"
    print("✅ test_shipping_choice_fee_free_over_and_confirm PASSED")


async def test_single_method_still_requires_explicit_choice(shop_dp) -> None:
    """B8 (تغییرِ عمدی): با یک روشِ فعال هم مرحله‌یِ ارسال نشان داده می‌شود و مشتری باید تایید کند؛
    قبلاً تنها روش بی‌صدا انتخاب می‌شد و اگر روشی تعریف نشده بود مرحله کاملاً رد می‌شد."""
    shop_bot_id, rice, tea = await _seed(shipping=[("پست", 30_000, None)])
    async with session_scope() as session:
        post = (await shipping_service.list_methods(session, shop_bot_id, only_active=True))[0].id

    s = _Shopper(shop_dp)
    await s.add(tea)
    await s.tap("cart_checkout_start")
    await s.say("علی رضایی")
    await s.say("09120000000")
    await s.say("تهران")
    await s.say("تهران")
    await s.say("خیابانِ آزادی، پلاکِ ده")
    await s.tap("ck_skip")  # کدپستی
    assert any(c.startswith("ck_ship:") for c in s.last_callbacks()), "با یک روشِ فعال هم باید انتخاب پرسیده شود"
    assert "ثبت بشه؟" not in s.last_text, "بدونِ انتخابِ روشِ ارسال نباید به پیش‌نمایش برسد"
    await s.tap(f"ck_ship:{post}")
    await s.tap("ck_skip")  # توضیح
    assert "پست" in s.last_text and "30,000" in s.last_text and "80,000" in s.last_text, s.last_text
    assert "ck_edit:ship" in s.last_callbacks()

    # بینِ پیش‌نمایش و ثبت: هزینه‌یِ ارسال عوض می‌شه ⇒ ثبت نمی‌شه و پیش‌نمایشِ تازه می‌آید
    async with session_scope() as session:
        method = (await shipping_service.list_methods(session, shop_bot_id))[0]
        method.fee_toman = 45_000
    await s.tap("cart_checkout_confirm")
    assert await _orders(shop_bot_id) == [], "قیمت عوض شده؛ نباید ثبت بشه"
    assert "45,000" in s.session.edited_texts[-1]["text"] and "95,000" in s.session.edited_texts[-1]["text"]
    await s.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 1 and orders[0].shipping_fee_toman == 45_000

    # روشِ غیرفعال ⇒ انتخابِ قبلی بی‌اثر و مرحله دوباره پرسیده می‌شود
    async with session_scope() as session:
        method = (await shipping_service.list_methods(session, shop_bot_id))[0]
        method.is_active = False
    s2 = _Shopper(shop_dp)
    await s2.add(rice)
    await run_checkout(s2.tap, s2.say)  # هیچ روشِ فعالی نیست ⇒ بدونِ مرحله‌یِ ارسال
    assert "ck_edit:ship" not in s2.last_callbacks()
    assert "ثبت بشه؟" in s2.last_text
    print("✅ test_single_method_still_requires_explicit_choice PASSED")


# =============================================================================
# دیجیتال، برگشت، ویرایش، ورودیِ نامعتبر
# =============================================================================
async def test_digital_only_cart_skips_address_and_shipping(shop_dp) -> None:
    shop_bot_id, _rice, _tea = await _seed(shipping=[("پست", 30_000, None), ("پیک", 60_000, None)])
    async with session_scope() as session:
        product = await product_service.create_digital_product(session, shop_bot_id, "دوره", None, 70_000, None, "text", instructions="سلام")
        digital_id = product.id
    s = _Shopper(shop_dp)
    await s.add(digital_id)
    await run_checkout(s.tap, s.say, physical=False)
    assert "ثبت بشه؟" in s.last_text and "آدرسِ تحویل" not in s.last_text and "روشِ ارسال" not in s.last_text
    assert not any(c.startswith("ck_edit:addr") or c == "ck_edit:ship" for c in s.last_callbacks())
    await s.tap("cart_checkout_confirm")
    orders = await _orders(shop_bot_id)
    assert len(orders) == 1 and not orders[0].customer_address and not orders[0].shipping_fee_toman
    print("✅ test_digital_only_cart_skips_address_and_shipping PASSED")


async def test_invalid_inputs_back_edit_and_stale_buttons(shop_dp) -> None:
    shop_bot_id, rice, _tea = await _seed()
    s = _Shopper(shop_dp)
    await s.add(rice)
    await s.tap("cart_checkout_start")
    assert "ck_back" not in s.last_callbacks() and "cart_checkout_cancel" in s.last_callbacks()

    await s.say("علی۱۲۳")
    assert "۲ تا ۶۰ حرف" in s.last_text
    await s.say("علی رضایی")
    assert "ck_back" in s.last_callbacks()
    await s.say("12345")
    assert "معتبر نیست" in s.last_text
    await s.say("09120000000")
    await s.say("ت")  # استانِ نامعتبر
    assert "۲ تا ۴۰ حرف" in s.last_text
    await s.say("تهران")
    await s.say("تهران")
    await s.say("کوتاه")
    assert "۸ تا ۴۰۰" in s.last_text
    await s.say("خیابانِ آزادی، پلاکِ ده")
    await s.say("123")
    assert "۱۰ رقم" in s.last_text
    assert "ck_skip" in s.last_callbacks() and "ck_back" in s.last_callbacks()

    # برگشت: کدپستی ← آدرس ← شهر
    await s.tap("ck_back")
    assert "آدرسِ کامل" in s.last_text
    await s.tap("ck_back")
    assert "شهر" in s.last_text
    await s.say("کرج")
    await s.say("بلوارِ اصلی، کوچه‌یِ سوم، پلاکِ پنج")
    await s.tap("ck_skip")  # کدپستی
    await s.tap("ck_skip")  # توضیح
    assert "کرج" in s.last_text and "ثبت بشه؟" in s.last_text

    # ویرایش از پیش‌نمایش: موبایل
    await s.tap("ck_edit:phone")
    assert "موبایل" in s.last_text
    await s.say("09125556677")
    assert "ثبت بشه؟" in s.last_text and "+989125556677" in s.last_text
    # ویرایشِ آدرس ⇒ برگشت بدونِ ساختنِ آدرسِ اضافه
    await s.tap("ck_edit:addr")
    assert "ck_addr_new" in s.last_callbacks()
    await s.tap("ck_back")
    assert "ثبت بشه؟" in s.last_text, "برگشت در حالتِ ویرایش ⇒ پیش‌نمایش"

    # دکمه‌یِ کهنه: ck_* در وضعیتِ نامربوط ⇒ پیامِ مودبانه، نه سکوت/خطا
    await s.tap("ck_name_ok")
    assert s.last_alert["show_alert"] is True and "منقضی" in (s.last_alert["text"] or "")

    await s.tap("cart_checkout_cancel")
    await s.tap("ck_skip")
    assert "منقضی" in (s.last_alert["text"] or ""), "بعدِ انصراف، دکمه‌هایِ قدیمی کهنه‌اند"
    assert await _orders(shop_bot_id) == []
    print("✅ test_invalid_inputs_back_edit_and_stale_buttons PASSED")


async def test_double_confirm_creates_one_order_and_contact_share(shop_dp) -> None:
    shop_bot_id, rice, _tea = await _seed()
    s = _Shopper(shop_dp)
    await s.add(rice)
    await s.tap("cart_checkout_start")
    await s.say("علی رضایی")
    # مخاطبِ دیگران پذیرفته نمی‌شه؛ مخاطبِ خودش بله
    s._n += 1
    await s.dp.feed_update(s.bot, make_message_update(s._n, text=None, user_id=s.user_id, contact_phone="+989127778899", contact_user_id=s.user_id + 1))
    assert "فقط شماره‌یِ خودت" in s.last_text
    s._n += 1
    await s.dp.feed_update(s.bot, make_message_update(s._n, text=None, user_id=s.user_id, contact_phone="+989127778899", contact_user_id=s.user_id))
    assert "استان" in s.last_text
    await s.say("تهران")
    await s.say("تهران")
    await s.say("خیابانِ آزادی، پلاکِ ده")
    await s.tap("ck_skip")
    await s.tap("ck_skip")
    customer = await _customer(s.user_id)
    assert customer.phone_number == "+989127778899" and customer.phone_via_contact is True

    await asyncio.gather(s.tap("cart_checkout_confirm"), s.tap("cart_checkout_confirm"))
    assert len(await _orders(shop_bot_id)) == 1, "دابل‌تپِ «ثبتِ نهایی» = یک سفارش"
    print("✅ test_double_confirm_creates_one_order_and_contact_share PASSED")


# =============================================================================
# C2: سرویسِ پیشنهادِ AI
# =============================================================================
async def test_proposal_claim_is_atomic_and_expires() -> None:
    shop_bot_id, rice, _tea = await _seed()
    import datetime

    from app.services import cart_service, customer_service

    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, 880100, "ک", None)
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer.id)
        cart_id = cart.id
        ops = [cart_edit_service.CartOperation("add", rice, 1)]
        p1 = await cart_proposal_service.create(session, cart_id, ops, "abcdef")
        p1_id = p1.id
        p2 = await cart_proposal_service.create(session, cart_id, ops, "abcdef")  # p1 را منسوخ می‌کند
        p2_id = p2.id
    async with session_scope() as session:
        status, _row = await cart_proposal_service.claim(session, p1_id, cart_id)
        assert status == cart_proposal_service.CLAIM_ALREADY_USED, "پیشنهادِ قبلی منسوخ شده"
        status, row = await cart_proposal_service.claim(session, p2_id, cart_id)
        assert status == cart_proposal_service.CLAIM_OK and row.fingerprint == "abcdef"
        status, _row = await cart_proposal_service.claim(session, p2_id, cart_id)
        assert status == cart_proposal_service.CLAIM_ALREADY_USED, "یک‌بارمصرف"
        assert (await cart_proposal_service.claim(session, p2_id, cart_id + 999))[0] == cart_proposal_service.CLAIM_NOT_FOUND, "cart دیگران"
        p3 = await cart_proposal_service.create(session, cart_id, ops, "zzzzzz")
        p3_id = p3.id
    async with session_scope() as session:
        later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=cart_proposal_service.PROPOSAL_TTL_MINUTES + 1)
        status, _row = await cart_proposal_service.claim(session, p3_id, cart_id, now=later)
        assert status == cart_proposal_service.CLAIM_EXPIRED
        status, _row = await cart_proposal_service.claim(session, p3_id, cart_id)
        assert status == cart_proposal_service.CLAIM_ALREADY_USED, "منقضی هم مصرف می‌شه"
        assert await cart_proposal_service.reject(session, p3_id, cart_id) is False
    async with session_scope() as session:
        rows = (await session.execute(select(CartAiProposal))).scalars().all()
        assert all(r.used for r in rows)
    print("✅ test_proposal_claim_is_atomic_and_expires PASSED")


async def main() -> None:
    _main_dp, shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    await test_validators_and_flow_logic()
    await test_proposal_ops_roundtrip()
    await test_address_book_rules()
    await test_full_physical_flow_saves_everything(shop_dp, main_bot)
    await test_saved_address_chooser_manage_and_cap(shop_dp)
    await test_shipping_choice_fee_free_over_and_confirm(shop_dp, main_bot)
    await test_single_method_still_requires_explicit_choice(shop_dp)
    await test_digital_only_cart_skips_address_and_shipping(shop_dp)
    await test_invalid_inputs_back_edit_and_stale_buttons(shop_dp)
    await test_double_confirm_creates_one_order_and_contact_share(shop_dp)
    await test_proposal_claim_is_atomic_and_expires()


if __name__ == "__main__":
    asyncio.run(main())
