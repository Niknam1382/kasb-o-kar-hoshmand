"""
تست: سبدِ خریدِ واقعی (فازِ ۳) — مرورِ محصولات، سبد (افزودن)، چک‌اوتِ
چندمرحله‌ای با سوال‌هایِ فروشگاه‌دار-تعریف‌شده، تبدیل به چند سفارشِ
گروه‌بندی‌شده، تاییدِ/ردِ گروهیِ فروشگاه‌دار، تنظیماتِ سوال‌هایِ چک‌اوت، و
بله‌پیِ گروهی.

نکته‌ی مهمِ هارنس (یادگرفته‌شده در همین فاز): EditMessageText هیچ‌جا ثبت
نمی‌شه (نه sent_messages نه چیزِ دیگه‌ای) — فقط SendMessage توی sent_messages
و AnswerCallbackQuery توی answered_callbacks ثبت می‌شن. پس برایِ چک‌کردنِ
چیزی که با edit_text رفته، مستقیم وضعیتِ دیتابیس رو چک می‌کنیم، نه یه لیستِ
«ادیت‌شده‌ها»ی ناموجود.

اجرا: python3 tests_manual/test_shopping_cart.py
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
from checkout_helpers import run_checkout  # noqa: E402

from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import Customer, OrderConsultation, OrderStatus, ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import bale_credentials_service, bale_service, cart_service, product_service  # noqa: E402
from app.services.admin_settings_service import update_setting  # noqa: E402
from sqlalchemy import select  # noqa: E402

OWNER_TG_ID = 999001
SHOP_BOT_TG_ID = 999002
CUSTOMER_TG_ID = 999003
ADMIN_TG_ID = 12345

_created_invoices: list[dict] = []


async def _fake_create_invoice_link(bot_token, provider_token, title, description, payload, amount_rial) -> str:
    _created_invoices.append({"provider_token": provider_token, "payload": payload, "amount_rial": amount_rial})
    return f"https://fake-bale-pay.test/{payload}"


async def _seed_shop_with_products() -> tuple[int, int, int]:
    """برمی‌گردونه: (shop_bot_id, product1_id, product2_id). محصولِ اول موجودیِ
    محدود (۲ عدد) داره تا سقفِ موجودی هم تست بشه؛ محصولِ دوم نامحدوده."""
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        p1 = await product_service.create_product(session, shop_bot_id, "برنج", None, 200_000, None, stock_quantity=2)
        p2 = await product_service.create_product(session, shop_bot_id, "چای", None, 50_000, None, stock_quantity=None)
    return shop_bot_id, p1.id, p2.id


async def _customer_id(session, shop_bot_id: int) -> int:
    """آیدیِ واقعیِ مشتریِ تستی (اگه هنوز نیست می‌سازه) — سبد یه کلیدِ خارجی به
    جدولِ customers داره، پس customer_id=۱ِ هاردکد فقط وقتی کار می‌کنه که
    مشتری از قبل ساخته شده باشه."""
    result = await session.execute(
        select(Customer).where(Customer.shop_bot_id == shop_bot_id, Customer.telegram_id == CUSTOMER_TG_ID)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=CUSTOMER_TG_ID, first_name="مشتریِ تستی")
        session.add(customer)
        await session.flush()
    return customer.id


def _new_shop_bot_instance() -> Bot:
    return Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())


async def _orders_for_shop(session, shop_bot_id: int) -> list[OrderConsultation]:
    result = await session.execute(select(OrderConsultation).where(OrderConsultation.shop_bot_id == shop_bot_id).order_by(OrderConsultation.id))
    return list(result.scalars().all())


_ADDRESS_SAVED_FOR: list = []  # رباتِ تستی‌ایی که مشتریش آدرس ذخیره کرده (ارجاعِ قوی ⇒ بدونِ بازاستفاده‌یِ id)


async def _quick_checkout(shop_dp, shop_bot_instance: Bot, product_ids: list[int], start_update_id: int = 100) -> None:
    """میان‌بر: هر محصول رو یه‌بار اضافه و با سوال‌هایِ پیش‌فرض چک‌اوت می‌کنه —
    برایِ تست‌هایی که خودِ فلویِ چک‌اوت موضوعشون نیست، فقط یه سفارشِ گروهیِ
    آماده لازم دارن."""
    counter = [start_update_id]

    async def tap(data: str) -> None:
        counter[0] += 1
        await shop_dp.feed_update(shop_bot_instance, make_callback_update(counter[0], data=data, user_id=CUSTOMER_TG_ID))

    async def say(text: str) -> None:
        counter[0] += 1
        await shop_dp.feed_update(shop_bot_instance, make_message_update(counter[0], text=text, user_id=CUSTOMER_TG_ID))

    for pid in product_ids:
        await tap(f"cart_add:{pid}")
    await run_checkout(tap, say, has_saved_addresses=any(b is shop_bot_instance for b in _ADDRESS_SAVED_FOR))  # W5/C3: چک‌اوتِ مرحله‌ایِ جدید
    _ADDRESS_SAVED_FOR.append(shop_bot_instance)
    await tap("cart_checkout_confirm")


# =============================================================================
# ۱. cart_service به‌تنهایی (بدونِ ربات/دیسپچر)
# =============================================================================
async def test_add_item_respects_stock_cap() -> None:
    shop_bot_id, product1_id, _p2 = await _seed_shop_with_products()
    async with session_scope() as session:
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id=await _customer_id(session, shop_bot_id))
        product = await product_service.get_by_id(session, product1_id)

        item, added = await cart_service.add_item(session, cart, product, quantity=5)  # موجودی فقط ۲ ـه
        assert added == 2, f"باید فقط تا سقفِ موجودی (۲) اضافه بشه، شد {added}"
        assert item.quantity == 2

        item2, added2 = await cart_service.add_item(session, cart, product, quantity=3)
        assert added2 == 0, "وقتی از قبل به سقفِ موجودی رسیده، نباید چیزِ بیشتری اضافه بشه"
        assert item2.quantity == 2, "مقدارِ از‌قبل‌تویِ‌سبد نباید کم بشه"

    print("✅ test_add_item_respects_stock_cap PASSED")


async def test_add_item_out_of_stock_new_item_returns_none() -> None:
    shop_bot_id, product1_id, _p2 = await _seed_shop_with_products()
    async with session_scope() as session:
        product = await product_service.get_by_id(session, product1_id)
        product.stock_quantity = 0
        await session.flush()

        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id=await _customer_id(session, shop_bot_id))
        item, added = await cart_service.add_item(session, cart, product, quantity=1)
        assert item is None and added == 0, "محصولِ بدونِ موجودی نباید اصلاً به سبد اضافه بشه"

    print("✅ test_add_item_out_of_stock_new_item_returns_none PASSED")


# =============================================================================
# ۲. فلویِ کاملِ مشتری: مرور → افزودن → سبد → چک‌اوت
# =============================================================================
async def test_full_cart_flow_creates_grouped_orders_and_notifies_owner(shop_dp, main_bot, bot_manager) -> None:
    shop_bot_id, product1_id, product2_id = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)
    main_bot.session.sent_messages.clear()

    await shop_dp.feed_update(shop_bot_instance, make_message_update(1, text="🛍 محصولات", user_id=CUSTOMER_TG_ID))
    await shop_dp.feed_update(shop_bot_instance, make_callback_update(2, data=f"cart_add:{product1_id}", user_id=CUSTOMER_TG_ID))
    await shop_dp.feed_update(shop_bot_instance, make_callback_update(3, data=f"cart_add:{product2_id}", user_id=CUSTOMER_TG_ID))

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert len(sent.sent_messages) == 1, "فقط پیامِ لیستِ محصولات باید send بشه؛ افزودن‌ها toast ـن نه پیام"
    assert len(sent.answered_callbacks) == 2
    assert sent.answered_callbacks[0]["text"] == shop_texts.item_added_to_cart("برنج")
    assert sent.answered_callbacks[1]["text"] == shop_texts.item_added_to_cart("چای")

    await shop_dp.feed_update(shop_bot_instance, make_message_update(4, text="🛒 سبدِ خرید", user_id=CUSTOMER_TG_ID))
    assert len(sent.sent_messages) == 2
    assert "برنج" in sent.sent_messages[-1]["text"] and "چای" in sent.sent_messages[-1]["text"]

    # W5/C3: چک‌اوتِ مرحله‌ایِ جدید — هر مرحله یک پیامِ تازه (answer) است
    async def _step(kind: str, value: str, n: int, expect_count: int, expect_in_text: str) -> None:
        if kind == "tap":
            await shop_dp.feed_update(shop_bot_instance, make_callback_update(n, data=value, user_id=CUSTOMER_TG_ID))
        else:
            await shop_dp.feed_update(shop_bot_instance, make_message_update(n, text=value, user_id=CUSTOMER_TG_ID))
        assert len(sent.sent_messages) == expect_count, (value, len(sent.sent_messages))
        assert expect_in_text in sent.sent_messages[-1]["text"], (value, sent.sent_messages[-1]["text"])

    await _step("tap", "cart_checkout_start", 5, 3, "نامِ تحویل‌گیرنده")
    await _step("say", "علی رضایی", 6, 4, "شماره‌یِ موبایل")
    await _step("say", "09120000000", 7, 5, "آدرسِ کامل")  # پ۶۸: استان/شهر پیش‌فرض پرسیده نمی‌شوند
    await _step("say", "خیابونِ آزادی، پلاکِ ۱۰", 8, 6, "کدپستی")
    await _step("tap", "ck_skip", 9, 7, "هماهنگی")  # P22: بعد از کدپستی، پرسشِ ارسال (بدونِ روش ⇒ هماهنگی)
    await _step("tap", "ck_ship:0", 10, 8, "توضیح")
    await _step("tap", "ck_skip", 11, 9, "ثبت بشه؟")  # پیش‌نمایشِ نهایی send می‌شه
    confirm_text = sent.sent_messages[-1]["text"]
    assert "علی رضایی" in confirm_text and "+989120000000" in confirm_text and "خیابونِ آزادی" in confirm_text
    assert "برنج" in confirm_text and "چای" in confirm_text and "۲۵۰٬۰۰۰" in confirm_text  # جمعِ کل: ۲۰۰٬۰۰۰ + ۵۰٬۰۰۰

    await shop_dp.feed_update(shop_bot_instance, make_callback_update(14, data="cart_checkout_confirm", user_id=CUSTOMER_TG_ID))
    assert len(sent.sent_messages) == 9, "تاییدِ نهایی edit_text ـه، شمارش نباید عوض بشه"

    async with session_scope() as session:
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id=await _customer_id(session, shop_bot_id))
        remaining_items = await cart_service.get_items_with_products(session, cart.id)
        assert remaining_items == [], "بعدِ چک‌اوتِ موفق، سبد باید خالی بشه"

        product1 = await product_service.get_by_id(session, product1_id)
        assert product1.reserved_quantity == 1, "باید موجودیِ محصولِ محدود رزرو شده باشه (order_service.create_order)"

        orders = await _orders_for_shop(session, shop_bot_id)
        assert len(orders) == 2, f"باید دو سفارشِ جدا (یکی به‌ازایِ هر محصول) ساخته بشه، شد {len(orders)}"
        assert orders[0].cart_checkout_group_id == orders[1].cart_checkout_group_id, "هر دو باید یه group_idِ مشترک داشته باشن"
        assert all(o.status == OrderStatus.PENDING for o in orders)

    assert len(main_bot.session.sent_messages) == 1, "باید دقیقاً یه اطلاع‌رسانیِ ترکیبی به فروشگاه‌دار بره"
    owner_text = main_bot.session.sent_messages[0]["text"]
    assert "برنج" in owner_text and "چای" in owner_text and "۲۵۰٬۰۰۰" in owner_text
    assert "+989120000000" in owner_text and "خیابونِ آزادی" in owner_text and "علی رضایی" in owner_text

    print("✅ test_full_cart_flow_creates_grouped_orders_and_notifies_owner PASSED")


async def test_checkout_uses_owner_configured_questions(shop_dp, main_bot, bot_manager) -> None:
    shop_bot_id, product1_id, _p2 = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)
    main_bot.session.sent_messages.clear()

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.checkout_questions = "کدِ پستی\nساعتِ ترجیحیِ تحویل"

    await shop_dp.feed_update(shop_bot_instance, make_callback_update(1, data=f"cart_add:{product1_id}", user_id=CUSTOMER_TG_ID))
    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    steps = [("tap", "cart_checkout_start"), ("say", "علی رضایی"), ("say", "09120000000"),
             ("say", "خیابونِ آزادی، پلاکِ ۱۰"), ("tap", "ck_skip"), ("tap", "ck_ship:0")]  # P22: هماهنگیِ ارسال
    for index, (kind, value) in enumerate(steps, start=2):
        if kind == "tap":
            await shop_dp.feed_update(shop_bot_instance, make_callback_update(index, data=value, user_id=CUSTOMER_TG_ID))
        else:
            await shop_dp.feed_update(shop_bot_instance, make_message_update(index, text=value, user_id=CUSTOMER_TG_ID))
    # W5/C3: سوال‌هایِ فروشگاه‌دار *بعد از* نام/موبایل/آدرس می‌آن و دیگه پیش‌فرضِ «شماره/آدرس» وجود نداره
    assert "کدِ پستی" in sent.sent_messages[-1]["text"], "باید سوالِ اولِ خودِ فروشگاه‌دار پرسیده بشه"

    await shop_dp.feed_update(shop_bot_instance, make_message_update(20, text="1234567890", user_id=CUSTOMER_TG_ID))
    assert "ساعتِ ترجیحیِ تحویل" in sent.sent_messages[-1]["text"]

    await shop_dp.feed_update(shop_bot_instance, make_message_update(21, text="عصر", user_id=CUSTOMER_TG_ID))
    await shop_dp.feed_update(shop_bot_instance, make_callback_update(22, data="ck_skip", user_id=CUSTOMER_TG_ID))  # توضیح: رد
    final_text = sent.sent_messages[-1]["text"]
    assert "کدِ پستی" in final_text and "1234567890" in final_text and "عصر" in final_text

    print("✅ test_checkout_uses_owner_configured_questions PASSED")


async def test_out_of_stock_add_shows_alert(shop_dp, bot_manager) -> None:
    shop_bot_id, product1_id, _p2 = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)

    async with session_scope() as session:
        product = await product_service.get_by_id(session, product1_id)
        product.stock_quantity = 0

    await shop_dp.feed_update(shop_bot_instance, make_callback_update(1, data=f"cart_add:{product1_id}", user_id=CUSTOMER_TG_ID))

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert not sent.sent_messages
    assert sent.answered_callbacks[0]["text"] == shop_texts.ITEM_OUT_OF_STOCK
    assert sent.answered_callbacks[0]["show_alert"] is True

    async with session_scope() as session:
        cart = await cart_service.get_or_create_cart(session, shop_bot_id, customer_id=await _customer_id(session, shop_bot_id))
        items = await cart_service.get_items_with_products(session, cart.id)
        assert items == []

    print("✅ test_out_of_stock_add_shows_alert PASSED")


# =============================================================================
# ۳. تاییدِ/ردِ گروهیِ فروشگاه‌دار
# =============================================================================
async def test_owner_group_confirm_deducts_stock_for_all_items(shop_dp, main_dp, bot_manager) -> None:
    shop_bot_id, product1_id, product2_id = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)
    owner_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await _quick_checkout(shop_dp, shop_bot_instance, [product1_id, product2_id])

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        assert len(orders) == 2
        group_id = orders[0].cart_checkout_group_id
        assert group_id is not None

    await main_dp.feed_update(owner_bot, make_callback_update(1, data=f"confirm_cart_group:{group_id}", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        assert all(o.status == OrderStatus.CONFIRMED for o in orders), "هر دو سفارشِ گروه باید تایید شده باشن"

        product1 = await product_service.get_by_id(session, product1_id)
        assert product1.stock_quantity == 1, f"موجودی باید از ۲ به ۱ کسر بشه، شد {product1.stock_quantity}"
        assert product1.reserved_quantity == 0, "رزرو باید به کسرِ قطعی تبدیل بشه، نه اینکه رزرو بمونه"

    print("✅ test_owner_group_confirm_deducts_stock_for_all_items PASSED")


async def test_owner_group_reject_releases_reservation(shop_dp, main_dp, bot_manager) -> None:
    shop_bot_id, product1_id, product2_id = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)
    owner_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await _quick_checkout(shop_dp, shop_bot_instance, [product1_id, product2_id])

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        group_id = orders[0].cart_checkout_group_id

    await main_dp.feed_update(owner_bot, make_callback_update(1, data=f"reject_cart_group:{group_id}", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        assert all(o.status == OrderStatus.REJECTED for o in orders)

        product1 = await product_service.get_by_id(session, product1_id)
        assert product1.stock_quantity == 2, "رد کردن نباید موجودی رو کم کنه"
        assert product1.reserved_quantity == 0, "رزرو باید آزاد بشه"

    print("✅ test_owner_group_reject_releases_reservation PASSED")


async def test_cross_shop_cannot_confirm_others_cart_group(shop_dp, main_dp, bot_manager) -> None:
    """ایزوله‌بودنِ چندمستاجری: فروشگاه‌دارِ ۲ نباید بتونه با حدس‌زدنِ
    group_id، سفارشِ سبدِ فروشگاهِ ۱ رو تایید کنه."""
    shop_bot_id, product1_id, _p2 = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)

    other_owner_tg_id = 999011
    other_shop_bot_tg_id = 999012
    await seed_usable_shop(other_owner_tg_id, other_shop_bot_tg_id)
    other_owner_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await _quick_checkout(shop_dp, shop_bot_instance, [product1_id])

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        group_id = orders[0].cart_checkout_group_id

    await main_dp.feed_update(other_owner_bot, make_callback_update(1, data=f"confirm_cart_group:{group_id}", user_id=other_owner_tg_id))

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        assert all(o.status == OrderStatus.PENDING for o in orders), "فروشگاه‌دارِ دیگه نباید بتونه این گروه رو تایید کنه"

    print("✅ test_cross_shop_cannot_confirm_others_cart_group PASSED")


# =============================================================================
# ۴. تنظیماتِ سوال‌هایِ چک‌اوت (پنلِ فروشگاه‌دار)
# =============================================================================
async def test_owner_can_set_and_reset_checkout_questions(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(owner_bot, make_message_update(1, text="📝 سوال‌هایِ چک‌اوتِ سبد", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(2, text="کدِ پستی\nساعتِ تحویل", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.checkout_questions == "کدِ پستی\nساعتِ تحویل"

    await main_dp.feed_update(owner_bot, make_message_update(3, text="📝 سوال‌هایِ چک‌اوتِ سبد", user_id=OWNER_TG_ID))
    await main_dp.feed_update(owner_bot, make_message_update(4, text="حذف", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        shop_bot = await session.get(ShopBot, shop_bot_id)
        assert shop_bot.checkout_questions is None

    print("✅ test_owner_can_set_and_reset_checkout_questions PASSED")


# =============================================================================
# ۵. بله‌پی برایِ کلِ سبد
# =============================================================================
async def test_bale_pay_offered_for_cart_when_configured(shop_dp, bot_manager) -> None:
    shop_bot_id, product1_id, product2_id = await _seed_shop_with_products()
    register_fake_shop_bot(bot_manager, shop_bot_id, _new_shop_bot_instance())
    shop_bot_instance = bot_manager.get_bot(shop_bot_id)

    settings.bale_bot_token = "TEST-PLATFORM-BALE-BOT-TOKEN"
    _created_invoices.clear()
    bale_service.create_invoice_link = _fake_create_invoice_link

    async with session_scope() as session:
        await update_setting(session, "bale_pay_enabled", True)
        # P23: قالبِ لینک لازم است، وگرنه هیچ پیشنهادِ پرداختِ بله‌پی‌ای ساخته نمی‌شود.
        # P26: لینکِ پرداخت = چتِ رباتِ پرداخت؛ نامِ کاربری را به‌جایِ getMe می‌گذاریم (تست به شبکه نمی‌زند).
        bale_credentials_service.remember_pay_bot_username('platform_pay_bot')
        shop_bot = await session.get(ShopBot, shop_bot_id)
        shop_bot.bale_provider_token = "SHOP-OWN-PROVIDER-TOKEN"
        # P41: پیشنهادِ پرداختِ سفارش فقط با «رباتِ بلهٔ خودش + درگاهِ خودش» ساخته می‌شود.
        shop_bot.bale_encrypted_token = "222222:SHOP-OWN-BALE-BOT-TOKEN"
        shop_bot.bale_bot_id = 222222
        shop_bot.bale_bot_username = "shop_own_bale_bot"
        shop_bot.bale_bot_enabled = True

    await _quick_checkout(shop_dp, shop_bot_instance, [product1_id, product2_id])

    sent: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    # W5/C3: _quick_checkout پیام‌هایِ مرحله‌ایِ چک‌اوت را می‌فرستد (نام، موبایل، آدرس، کدپستی، توضیح، پیش‌نمایش).
    # P22: پرسشِ «ارسال» هم اضافه شد (با «هماهنگیِ ارسال» وقتی روشی نیست) ⇒ ۷ تا، و با بله‌پی +۱ = ۸.
    # پ۶۸: استان و شهر پیش‌فرض پرسیده نمی‌شوند (دو پیامِ کمتر).
    assert len(sent.sent_messages) == 8, f"باید ۷ تایِ چک‌اوتِ مرحله‌ای + ۱ پیشنهادِ پرداخت بره، شد {len(sent.sent_messages)}"
    offer_text = sent.sent_messages[-1]["text"]
    assert offer_text == shop_texts.online_payment_offer(250_000)  # ۲۰۰٬۰۰۰ + ۵۰٬۰۰۰

    assert len(_created_invoices) == 1
    assert _created_invoices[0]["provider_token"] == "SHOP-OWN-PROVIDER-TOKEN"
    assert _created_invoices[0]["amount_rial"] == 2_500_000
    assert _created_invoices[0]["payload"].startswith("cartgroup-")

    print("✅ test_bale_pay_offered_for_cart_when_configured PASSED")


async def test_cartgroup_webhook_marks_all_orders_paid(shop_dp, bot_manager, main_bot) -> None:
    from app import main as app_main

    shop_bot_id, product1_id, product2_id = await _seed_shop_with_products()
    shop_bot_instance = _new_shop_bot_instance()
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    app_main._state["bot_manager"] = bot_manager
    app_main._state["main_bot"] = main_bot
    main_bot.session.sent_messages.clear()

    await _quick_checkout(shop_dp, shop_bot_instance, [product1_id, product2_id])

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        group_id = orders[0].cart_checkout_group_id
        assert all(o.bale_paid_at is None for o in orders)

    async def fake_inquire_ok(bot_token, transaction_id):
        return {"status": "successful"}

    bale_service.inquire_transaction = fake_inquire_ok

    # چک‌اوت خودش یه اعلانِ «سفارشِ جدید» برایِ فروشگاه‌دار فرستاده؛ قبل از وب‌هوک
    # پاکش می‌کنیم تا فقط پیام‌هایِ خودِ وب‌هوک شمرده بشن.
    main_bot.session.sent_messages.clear()

    invoice_payload = f"cartgroup-{group_id}-abcdef1234"
    await app_main._handle_bale_successful_payment({"invoice_payload": invoice_payload, "telegram_payment_charge_id": "chg_cart_1"})

    async with session_scope() as session:
        orders = await _orders_for_shop(session, shop_bot_id)
        assert all(o.bale_paid_at is not None for o in orders), "همه‌ی ردیف‌هایِ گروه باید پرداخت‌شده علامت بخورن"
        assert all(o.bale_transaction_id == "chg_cart_1" for o in orders)
        # P39 · باگِ ۳: پرداختِ بله‌پی گروه را خودکار به «پرداخت‌شده» می‌برد (نه فقط مهرِ زمان)
        assert all(o.status in (OrderStatus.PAID, OrderStatus.PROCESSING) for o in orders), [o.status for o in orders]
        assert all(o.payment_method == "bale" for o in orders), [o.payment_method for o in orders]

    owner_texts = [m["text"] for m in main_bot.session.sent_messages]
    assert len(owner_texts) == 1, owner_texts
    assert "بله‌پی" in owner_texts[0], owner_texts
    customer_session: FakeSession = shop_bot_instance.session  # type: ignore[assignment]
    assert customer_session.sent_documents, "فاکتور هم برایِ مشتری می‌رود"
    assert any("بله‌پی" in m["text"] for m in customer_session.sent_messages), customer_session.sent_messages
    messages_after_first_webhook = len(customer_session.sent_messages)

    # وب‌هوکِ تکراری idempotent باشه — نباید دوباره اطلاع‌رسانی کنه:
    await app_main._handle_bale_successful_payment({"invoice_payload": invoice_payload, "telegram_payment_charge_id": "chg_cart_1"})
    assert len(main_bot.session.sent_messages) == 1
    assert len(customer_session.sent_messages) == messages_after_first_webhook

    print("✅ test_cartgroup_webhook_marks_all_orders_paid PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, main_bot = build_test_dispatchers()

    await test_add_item_respects_stock_cap()
    await test_add_item_out_of_stock_new_item_returns_none()
    await test_full_cart_flow_creates_grouped_orders_and_notifies_owner(shop_dp, main_bot, bot_manager)
    await test_checkout_uses_owner_configured_questions(shop_dp, main_bot, bot_manager)
    await test_out_of_stock_add_shows_alert(shop_dp, bot_manager)
    await test_owner_group_confirm_deducts_stock_for_all_items(shop_dp, main_dp, bot_manager)
    await test_owner_group_reject_releases_reservation(shop_dp, main_dp, bot_manager)
    await test_cross_shop_cannot_confirm_others_cart_group(shop_dp, main_dp, bot_manager)
    await test_owner_can_set_and_reset_checkout_questions(main_dp)
    await test_bale_pay_offered_for_cart_when_configured(shop_dp, bot_manager)
    await test_cartgroup_webhook_marks_all_orders_paid(shop_dp, bot_manager, main_bot)


if __name__ == "__main__":
    asyncio.run(main())
