"""
تست: سیستمِ رزروِ خودکارِ موجودی + وضعیت‌های رسمیِ سفارش (بخشِ ۲ — مسترپرامپت).

اجرا: python3 tests_manual/test_order_reservation.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.database.models import Customer, OrderStatus, OrderType, Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_service  # noqa: E402

OWNER_TG_ID = 999701
SHOP_BOT_TG_ID = 999702
CUSTOMER_TG_ID = 999703


async def _seed_product(shop_bot_id: int, stock: int | None) -> int:
    async with session_scope() as session:
        product = Product(shop_bot_id=shop_bot_id, name="محصولِ محدود", price_toman=100000, stock_quantity=stock)
        session.add(product)
        await session.flush()
        return product.id


async def _seed_customer(shop_bot_id: int, telegram_id: int) -> int:
    async with session_scope() as session:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=telegram_id, first_name="مشتری")
        session.add(customer)
        await session.flush()
        return customer.id


async def test_create_order_reserves_stock() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۲ عدد محصولِ محدود", 200000, product_id=product_id, quantity=2
        )
        assert order.status == OrderStatus.PENDING
        assert order.stock_reserved is True
        assert order.reservation_expires_at is not None

        product = await session.get(Product, product_id)
        assert product.reserved_quantity == 2, f"باید ۲ واحد رزرو بشه، شد: {product.reserved_quantity}"
        assert product.stock_quantity == 5, "موجودیِ واقعی نباید تا قبل از تایید کم بشه"

    print("✅ test_create_order_reserves_stock PASSED")


async def test_second_order_without_enough_available_gets_no_reservation() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=3)
    customer_a = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)
    customer_b = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID + 1)

    async with session_scope() as session:
        await order_service.create_order(
            session, shop_bot_id, customer_a, OrderType.ORDER, "۳ عدد", 300000, product_id=product_id, quantity=3
        )

    async with session_scope() as session:
        order_b = await order_service.create_order(
            session, shop_bot_id, customer_b, OrderType.ORDER, "۱ عدد", 100000, product_id=product_id, quantity=1
        )
        assert order_b.stock_reserved is False, "وقتی موجودیِ آزاد کافی نیست، نباید رزرو بشه"
        assert order_b.status == OrderStatus.PENDING, "سفارش بازم باید ساخته بشه تا فروشگاه‌دار ببینتش"

        product = await session.get(Product, product_id)
        assert product.reserved_quantity == 3, "رزروِ مشتریِ اول نباید دست‌نخورده بمونه"

    print("✅ test_second_order_without_enough_available_gets_no_reservation PASSED")


async def test_confirm_converts_reservation_to_permanent_deduction() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۲ عدد", 200000, product_id=product_id, quantity=2
        )
        order_id = order.id

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        confirmed = await order_service.confirm_order(session, order)
        assert confirmed is True
        assert order.status == OrderStatus.CONFIRMED
        assert order.stock_reserved is False

        product = await session.get(Product, product_id)
        assert product.stock_quantity == 3, f"باید موجودیِ واقعی ۲ واحد کم بشه (۵→۳)، شد: {product.stock_quantity}"
        assert product.reserved_quantity == 0, "بعدِ تایید، رزرو باید صفر بشه (چون قطعی شد)"

    print("✅ test_confirm_converts_reservation_to_permanent_deduction PASSED")


async def test_reject_releases_reservation_without_deducting_stock() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۲ عدد", 200000, product_id=product_id, quantity=2
        )
        order_id = order.id

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        rejected = await order_service.reject_order(session, order)
        assert rejected is True
        assert order.status == OrderStatus.REJECTED
        assert order.stock_reserved is False

        product = await session.get(Product, product_id)
        assert product.stock_quantity == 5, "ردِ سفارش نباید موجودیِ واقعی رو کم کنه"
        assert product.reserved_quantity == 0, "ردِ سفارش باید رزرو رو کامل آزاد کنه"

        rejected_again = await order_service.reject_order(session, order)
        assert rejected_again is False

    print("✅ test_reject_releases_reservation_without_deducting_stock PASSED")


async def test_expire_stale_reservations_releases_stock() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۲ عدد", 200000, product_id=product_id, quantity=2
        )
        order_id = order.id
        order.reservation_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
        await session.flush()

    async with session_scope() as session:
        expired = await order_service.expire_stale_reservations(session)
        assert len(expired) == 1
        assert expired[0].id == order_id
        assert expired[0].status == OrderStatus.EXPIRED

        product = await session.get(Product, product_id)
        assert product.reserved_quantity == 0, "بعدِ انقضا، رزرو باید آزاد بشه"
        assert product.stock_quantity == 5, "انقضا نباید موجودیِ واقعی رو کم کنه"

        expired_again = await order_service.expire_stale_reservations(session)
        assert len(expired_again) == 0

    print("✅ test_expire_stale_reservations_releases_stock PASSED")


async def test_advance_status_sequence_stops_after_completed() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۱ عدد", 100000, product_id=product_id, quantity=1
        )
        order_id = order.id

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert await order_service.advance_status(session, order) is None

        await order_service.confirm_order(session, order)
        assert await order_service.advance_status(session, order) == OrderStatus.PROCESSING
        assert await order_service.advance_status(session, order) == OrderStatus.SHIPPED
        assert await order_service.advance_status(session, order) == OrderStatus.COMPLETED
        assert await order_service.advance_status(session, order) is None
        assert order.status == OrderStatus.COMPLETED

    print("✅ test_advance_status_sequence_stops_after_completed PASSED")


async def test_reject_order_handler_end_to_end(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    product_id = await _seed_product(shop_bot_id, stock=5)
    customer_id = await _seed_customer(shop_bot_id, CUSTOMER_TG_ID)

    async with session_scope() as session:
        order = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "۲ عدد", 200000, product_id=product_id, quantity=2
        )
        order_id = order.id

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    await main_dp.feed_update(main_bot, make_callback_update(1, data=f"reject_order:{order_id}", user_id=OWNER_TG_ID))

    async with session_scope() as session:
        order = await order_service.get_by_id(session, order_id)
        assert order.status == OrderStatus.REJECTED, f"باید از طریقِ هندلرِ واقعی رد بشه، وضعیت: {order.status}"
        product = await session.get(Product, product_id)
        assert product.reserved_quantity == 0, "هندلرِ ردکردن باید رزرو رو آزاد کنه"

    print("✅ test_reject_order_handler_end_to_end PASSED")


async def main() -> None:
    main_dp, shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    await test_create_order_reserves_stock()
    await test_second_order_without_enough_available_gets_no_reservation()
    await test_confirm_converts_reservation_to_permanent_deduction()
    await test_reject_releases_reservation_without_deducting_stock()
    await test_expire_stale_reservations_releases_stock()
    await test_advance_status_sequence_stops_after_completed()
    await test_reject_order_handler_end_to_end(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
