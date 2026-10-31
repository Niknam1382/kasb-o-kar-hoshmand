"""
تست: صفحه‌بندیِ لیست‌ها — محصولات و فروشگاه‌دارها (فازِ ۱-ب).

قبلِ این پچ، لیستِ فروشگاه‌دارها بی‌سروصدا به ۳۰ تای اول truncate می‌شد (بدونِ
هیچ راهی برای دیدنِ بقیه) و لیستِ محصولات اصلاً محدودیتی نداشت (با چند صد
محصول، یه کیبوردِ غیرقابل‌استفاده می‌ساخت).

اجرا: python3 tests_manual/test_pagination.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app.bots.main_bot import keyboards  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import product_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 999901
SHOP_BOT_TG_ID = 999902


def test_paginate_helper_edge_cases() -> None:
    items = list(range(25))

    page_items, page, total_pages = keyboards._paginate(items, 0)
    assert page_items == list(range(10)) and page == 0 and total_pages == 3

    page_items, page, total_pages = keyboards._paginate(items, 2)
    assert page_items == list(range(20, 25)) and page == 2 and total_pages == 3

    # صفحه‌ی خارج از بازه باید snap بشه، نه خطا بده
    page_items, page, total_pages = keyboards._paginate(items, 99)
    assert page == 2 and page_items == list(range(20, 25))

    page_items, page, total_pages = keyboards._paginate([], 0)
    assert page_items == [] and page == 0 and total_pages == 1

    empty_row = keyboards._pagination_row(0, 1, "x")
    assert empty_row == [], "با یه صفحه‌ی تنها نباید دکمه‌ی ناوبری نشون داده بشه"

    middle_row = keyboards._pagination_row(1, 3, "x")
    labels = [b.text for b in middle_row]
    assert "◀️ قبلی" in labels[0] and "بعدی ▶️" in labels[-1]

    print("✅ test_paginate_helper_edge_cases PASSED")


async def test_products_list_keyboard_has_at_most_page_size_products_plus_nav() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        for i in range(15):
            await product_service.create_product(session, shop_bot_id, f"محصولِ {i}", None, 10_000, None)

    async with session_scope() as session:
        products = await product_service.get_active_by_shop_bot(session, shop_bot_id)
        assert len(products) == 15

        kb = keyboards.products_list_keyboard(products, page=0)
        product_rows = [r for r in kb.inline_keyboard if r and r[0].callback_data and r[0].callback_data.startswith("product_view:")]
        assert len(product_rows) == 10, "صفحه‌ی اول باید دقیقاً ۱۰ محصول نشون بده، نه هر ۱۵ تا رو"

        kb_page2 = keyboards.products_list_keyboard(products, page=1)
        product_rows_2 = [r for r in kb_page2.inline_keyboard if r and r[0].callback_data and r[0].callback_data.startswith("product_view:")]
        assert len(product_rows_2) == 5, "صفحه‌ی دوم باید ۵ محصولِ باقی‌مونده رو نشون بده"

    print("✅ test_products_list_keyboard_has_at_most_page_size_products_plus_nav PASSED")


async def test_product_list_next_button_navigates_via_real_handler(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID + 1)
    async with session_scope() as session:
        for i in range(12):
            await product_service.create_product(session, shop_bot_id, f"محصولِ {i}", None, 10_000, None)

    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())
    # از دکمه‌ی «بعدی» صفحه‌ی اول به دوم — مسیرِ واقعیِ هندلر، نه صدازدنِ مستقیمِ تابع
    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_list:1", user_id=OWNER_TG_ID))
    print("✅ test_product_list_next_button_navigates_via_real_handler PASSED (بدونِ استثنا اجرا شد)")


async def test_admin_owners_list_paginates_beyond_old_hardcoded_30() -> None:
    await reset_database()
    async with session_scope() as session:
        for i in range(35):
            owner = await shop_owner_service.get_or_create_shop_owner(session, 900000 + i)
            await shop_owner_service.complete_registration(
                session, owner, "فروشنده", "تست", f"0912{i:07d}", f"owner{i}@example.com", True, True
            )

    async with session_scope() as session:
        owners = await shop_owner_service.get_all_registered(session)
        assert len(owners) == 35

        kb_page4 = keyboards.admin_owners_list_keyboard(owners, page=3)
        owner_rows = [r for r in kb_page4.inline_keyboard if r and r[0].callback_data and r[0].callback_data.startswith("admin_owner_view:")]
        assert len(owner_rows) == 5, "صفحه‌ی چهارم (اندیس ۳) باید ۵ فروشگاه‌دارِ باقی‌مونده (۳۱ تا ۳۵) رو نشون بده — قبلاً اصلاً دیده نمی‌شدن"

    print("✅ test_admin_owners_list_paginates_beyond_old_hardcoded_30 PASSED")


async def async_main() -> None:
    await test_products_list_keyboard_has_at_most_page_size_products_plus_nav()
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_product_list_next_button_navigates_via_real_handler(main_dp)
    await test_admin_owners_list_paginates_beyond_old_hardcoded_30()


def main() -> None:
    test_paginate_helper_edge_cases()
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
