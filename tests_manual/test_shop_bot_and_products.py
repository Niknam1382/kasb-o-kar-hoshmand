"""
تست: مدیریتِ محصولات توسط فروشگاه‌دار (افزودن با موجودی، ویرایش، حذف).

نکته درباره‌ی محدودیتِ محیطِ تست: هندلرِ save_shop_bot_token برای اعتبارسنجیِ
توکنِ وارد‌شده یه Bot() واقعی می‌سازه و get_me() واقعی می‌زنه که نیاز به دسترسیِ
شبکه به api.telegram.org داره (که توی سندباکس مجاز نیست). به‌جاش این تست مستقیم
از لایه‌ی سرویس (shop_owner_service + shop_bot_service) برای ساختِ رکوردهای اولیه
استفاده می‌کنه و از اونجا به بعد، مسیرِ واقعیِ هندلرهای aiogram رو تست می‌کنه.

اجرا: python3 tests_manual/test_shop_bot_and_products.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402

from app.database.models import Customer, OrderConsultation, OrderType, Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_service, shop_bot_service, shop_owner_service  # noqa: E402
from app.utils.encryption import encrypt_token  # noqa: E402

OWNER_TG_ID = 777001
OTHER_OWNER_TG_ID = 777002


async def _seed_owner_and_shop_bot() -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OWNER_TG_ID)
        owner = await shop_owner_service.complete_registration(session, owner, "فروشنده", "تست", "09120000000", "seller@example.com", True, True)
        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, "999999:FAKE_SHOP_TOKEN", 999999, "test_shop_bot")
        shop_bot.encrypted_token = encrypt_token("999999:FAKE_SHOP_TOKEN")
        await session.flush()
        return shop_bot.id


async def test_add_product_with_stock(main_dp) -> None:
    await reset_database()
    shop_bot_id = await _seed_owner_and_shop_bot()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_message_update(1, text="📦 محصولات", user_id=OWNER_TG_ID))
    assert any("محصول" in m["text"] for m in session_obj.sent_messages), "لیستِ محصولات (خالی) نمایش داده نشد"

    await main_dp.feed_update(main_bot, make_callback_update(2, data="product_add", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(3, text="کیف چرم دست‌دوز", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(4, text="رد شدن", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(5, text="450,000", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(6, text="رد شدن", user_id=OWNER_TG_ID))  # رد کردنِ عکس
    await main_dp.feed_update(main_bot, make_message_update(7, text="12", user_id=OWNER_TG_ID))  # موجودی

    async with session_scope() as session:
        result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))
        products = list(result.scalars().all())
        assert len(products) == 1, f"باید دقیقاً یه محصول ساخته بشه، تعداد: {len(products)}"
        product = products[0]
        assert product.name == "کیف چرم دست‌دوز"
        assert product.price_toman == 450000, f"قیمت درست پارس نشد: {product.price_toman}"
        assert product.stock_quantity == 12, f"موجودی درست ذخیره نشد: {product.stock_quantity}"
        assert product.is_active is True

    print("✅ test_add_product_with_stock PASSED")


async def test_add_product_skip_stock(main_dp) -> None:
    await reset_database()
    shop_bot_id = await _seed_owner_and_shop_bot()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_add", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="محصولِ نامحدود", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(3, text="توضیحاتِ محصول", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(4, text="100000", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(5, text="رد شدن", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(6, text="رد شدن", user_id=OWNER_TG_ID))  # رد کردنِ موجودی → نامحدود

    async with session_scope() as session:
        result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))
        product = result.scalars().first()
        assert product is not None
        assert product.stock_quantity is None, "با رد کردنِ موجودی، باید None (نامحدود) ذخیره بشه"
        assert product.description == "توضیحاتِ محصول"

    print("✅ test_add_product_skip_stock PASSED")


async def test_invalid_price_rejected(main_dp) -> None:
    await reset_database()
    await _seed_owner_and_shop_bot()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    session_obj: FakeSession = main_bot.session  # type: ignore[assignment]

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_add", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(2, text="محصولِ تست", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(3, text="رد شدن", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_message_update(4, text="این یه عدد نیست", user_id=OWNER_TG_ID))

    assert any("نامعتبر" in m["text"] or "معتبر" in m["text"] for m in session_obj.sent_messages[-1:]), (
        "قیمتِ نامعتبر باید پیامِ خطا بده"
    )
    print("✅ test_invalid_price_rejected PASSED")


async def test_delete_product(main_dp) -> None:
    await reset_database()
    shop_bot_id = await _seed_owner_and_shop_bot()
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    async with session_scope() as session:
        product = Product(shop_bot_id=shop_bot_id, name="محصولِ حذف‌شدنی", price_toman=1000, stock_quantity=5)
        session.add(product)
        await session.flush()
        product_id = product.id

    await main_dp.feed_update(main_bot, make_callback_update(1, data=f"product_delete:{product_id}", user_id=OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data=f"product_delete_confirm:{product_id}", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        product = await session.get(Product, product_id)
        assert product is not None, "محصول نباید از دیتابیس پاک بشه (soft delete)"
        assert product.is_active is False, "محصول باید غیرفعال (soft-deleted) بشه"

    print("✅ test_delete_product PASSED")


async def _seed_second_owner_and_shop_bot() -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_or_create_shop_owner(session, OTHER_OWNER_TG_ID)
        owner = await shop_owner_service.complete_registration(session, owner, "فروشنده۲", "تست۲", "09121111111", "seller2@example.com", True, True)
        shop_bot = await shop_bot_service.upsert_shop_bot(session, owner, "888888:FAKE_SHOP_TOKEN", 888888, "test_shop_bot_2")
        shop_bot.encrypted_token = encrypt_token("888888:FAKE_SHOP_TOKEN")
        await session.flush()
        return shop_bot.id


async def test_cross_shop_product_access_denied(main_dp) -> None:
    """
    رگرسیونِ امنیتی: فروشگاه‌دارِ B نباید بتونه با فرستادنِ callback_data
    دستی (شبیه‌سازیِ یه اسکریپت، نه کلیکِ واقعی روی دکمه) محصولِ
    فروشگاه‌دارِ A رو ببینه، ویرایش کنه، یا حذف کنه.
    """
    await reset_database()
    shop_bot_a_id = await _seed_owner_and_shop_bot()
    await _seed_second_owner_and_shop_bot()

    async with session_scope() as session:
        product = Product(shop_bot_id=shop_bot_a_id, name="محصولِ فروشگاهِ A", price_toman=99000, stock_quantity=3)
        session.add(product)
        await session.flush()
        product_id = product.id

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data=f"product_view:{product_id}", user_id=OTHER_OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(2, data=f"product_delete_confirm:{product_id}", user_id=OTHER_OWNER_TG_ID))
    await main_dp.feed_update(main_bot, make_callback_update(3, data=f"product_edit_field:{product_id}:price", user_id=OTHER_OWNER_TG_ID))

    async with session_scope() as session:
        product = await session.get(Product, product_id)
        assert product is not None, "محصولِ A نباید حذف بشه"
        assert product.is_active is True, "محصولِ A نباید توسطِ فروشگاه‌دارِ B غیرفعال بشه"
        assert product.name == "محصولِ فروشگاهِ A", "محصولِ A نباید تغییر کنه"
        assert product.price_toman == 99000, "قیمتِ محصولِ A نباید توسطِ فروشگاه‌دارِ B تغییر کنه"

    print("✅ test_cross_shop_product_access_denied PASSED")


async def test_cross_shop_order_confirm_denied(main_dp) -> None:
    """
    رگرسیونِ امنیتی: فروشگاه‌دارِ B نباید بتونه سفارشِ فروشگاه‌دارِ A رو
    تایید کنه (که باعثِ کسرِ موجودیِ محصولِ A می‌شد).
    """
    await reset_database()
    shop_bot_a_id = await _seed_owner_and_shop_bot()
    await _seed_second_owner_and_shop_bot()

    async with session_scope() as session:
        product = Product(shop_bot_id=shop_bot_a_id, name="محصولِ سفارشیِ A", price_toman=50000, stock_quantity=10)
        session.add(product)
        await session.flush()
        product_id = product.id

        customer = Customer(shop_bot_id=shop_bot_a_id, telegram_id=999999999, first_name="مشتریِ تست")
        session.add(customer)
        await session.flush()

        order = await order_service.create_order(
            session,
            shop_bot_id=shop_bot_a_id,
            customer_id=customer.id,
            order_type=OrderType.ORDER,
            summary="سفارشِ تستی",
            estimated_value_toman=50000,
            product_id=product_id,
            quantity=2,
        )
        order_id = order.id

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data=f"confirm_order:{order_id}", user_id=OTHER_OWNER_TG_ID))

    async with session_scope() as session:
        order = await session.get(OrderConsultation, order_id)
        product = await session.get(Product, product_id)
        assert order.confirmed is False, "سفارشِ A نباید توسطِ فروشگاه‌دارِ B تایید بشه"
        assert product.stock_quantity == 10, "موجودیِ محصولِ A نباید توسطِ فروشگاه‌دارِ B کم بشه"

    print("✅ test_cross_shop_order_confirm_denied PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_add_product_with_stock(main_dp)
    await test_add_product_skip_stock(main_dp)
    await test_invalid_price_rejected(main_dp)
    await test_delete_product(main_dp)
    await test_cross_shop_product_access_denied(main_dp)
    await test_cross_shop_order_confirm_denied(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
