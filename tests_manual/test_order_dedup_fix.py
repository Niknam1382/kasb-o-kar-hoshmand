"""
تست: رفعِ باگِ dedup سفارش (فازِ ۱-ب).

باگِ قبلی: هر سفارشِ اخیرِ یه مشتری (بدونِ توجه به نوع/محصول) باعثِ بلاک‌شدنِ
سفارشِ بعدی می‌شد — یعنی مشتری‌ای که واقعاً می‌خواست ظرفِ چند دقیقه دو محصولِ
متفاوت سفارش بده، سفارشِ دومش نادیده گرفته می‌شد. این تست‌ها هم رفعِ این باگ
رو تایید می‌کنن، هم اینکه dedupِ واقعی (همون محصول، ظرفِ چند دقیقه) هنوز کار می‌کنه.

اجرا: python3 tests_manual/test_order_dedup_fix.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import Customer, OrderType, Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import order_service  # noqa: E402

OWNER_TG_ID = 999801
SHOP_BOT_TG_ID = 999802
CUSTOMER_TG_ID = 999803


async def _seed(with_two_products: bool = False) -> tuple[int, int, int | None]:
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        customer = Customer(shop_bot_id=shop_bot_id, telegram_id=CUSTOMER_TG_ID, first_name="مشتری")
        session.add(customer)
        product_a = Product(shop_bot_id=shop_bot_id, name="محصولِ الف", price_toman=100_000)
        session.add(product_a)
        product_b_id = None
        if with_two_products:
            product_b = Product(shop_bot_id=shop_bot_id, name="محصولِ ب", price_toman=200_000)
            session.add(product_b)
        await session.flush()
        product_b_id = product_b.id if with_two_products else None
        return shop_bot_id, customer.id, product_a.id, product_b_id


async def test_same_product_ordered_twice_quickly_is_blocked() -> None:
    await reset_database()
    shop_bot_id, customer_id, product_a_id, _ = await _seed()

    async with session_scope() as session:
        await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "دو تا محصولِ الف", 200_000, product_a_id, 2
        )
        dup = await order_service.get_recent_duplicate(session, customer_id, OrderType.ORDER, product_a_id, minutes=10)
        assert dup is not None, "سفارشِ همون محصول ظرفِ چند دقیقه باید duplicate تشخیص داده بشه"

    print("✅ test_same_product_ordered_twice_quickly_is_blocked PASSED")


async def test_different_products_ordered_quickly_are_not_blocked() -> None:
    """این دقیقاً همون باگیه که رفع شد: دو سفارشِ واقعاً متفاوت نباید بهم بخورن."""
    await reset_database()
    shop_bot_id, customer_id, product_a_id, product_b_id = await _seed(with_two_products=True)

    async with session_scope() as session:
        await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "محصولِ الف", 100_000, product_a_id, 1
        )
        dup = await order_service.get_recent_duplicate(session, customer_id, OrderType.ORDER, product_b_id, minutes=10)
        assert dup is None, "سفارشِ یه محصولِ کاملاً متفاوت نباید به‌خاطرِ سفارشِ قبلی بلاک بشه"

        order_b = await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "محصولِ ب", 200_000, product_b_id, 1
        )
        assert order_b.id is not None

        all_orders = await order_service.count_by_type(session, shop_bot_id)
        assert all_orders.get("order", 0) == 2, "هر دو سفارشِ متفاوت باید واقعاً ذخیره شده باشن"

    print("✅ test_different_products_ordered_quickly_are_not_blocked PASSED")


async def test_order_vs_consultation_type_mismatch_not_blocked() -> None:
    await reset_database()
    shop_bot_id, customer_id, product_a_id, _ = await _seed()

    async with session_scope() as session:
        await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.ORDER, "یه سفارش", 100_000, product_a_id, 1
        )
        dup = await order_service.get_recent_duplicate(session, customer_id, OrderType.CONSULTATION, None, minutes=10)
        assert dup is None, "سفارش و مشاوره نباید duplicateِ همدیگه حساب بشن"

    print("✅ test_order_vs_consultation_type_mismatch_not_blocked PASSED")


async def test_no_product_orders_only_dedup_against_other_no_product_orders() -> None:
    await reset_database()
    shop_bot_id, customer_id, _product_a_id, _ = await _seed()

    async with session_scope() as session:
        await order_service.create_order(
            session, shop_bot_id, customer_id, OrderType.CONSULTATION, "یه مشاوره‌ی کلی", None, None, None
        )
        dup = await order_service.get_recent_duplicate(session, customer_id, OrderType.CONSULTATION, None, minutes=10)
        assert dup is not None, "دو مشاوره‌ی بدونِ محصولِ مشخص، ظرفِ چند دقیقه، باید duplicate باشن"

    print("✅ test_no_product_orders_only_dedup_against_other_no_product_orders PASSED")


async def main() -> None:
    await test_same_product_ordered_twice_quickly_is_blocked()
    await test_different_products_ordered_quickly_are_not_blocked()
    await test_order_vs_consultation_type_mismatch_not_blocked()
    await test_no_product_orders_only_dedup_against_other_no_product_orders()


if __name__ == "__main__":
    asyncio.run(main())
