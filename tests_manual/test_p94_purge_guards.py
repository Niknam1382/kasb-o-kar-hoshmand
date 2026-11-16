"""پ۹۴ · آزمونِ قفل‌هایِ اسکریپتِ پاک‌سازیِ دادهٔ دیجیتال (هیچ‌وقت بی‌تایید چیزی پاک نشود).

پنج ادعا:
۱. حالتِ پیش‌فرض dry-run است: با وجودِ داده، صفر ردیف حذف می‌شود.
۲. `--execute` بدونِ عبارتِ تایید ⇒ کدِ خروج ۲ و صفر حذف.
۳. `--execute --confirm` بدونِ `PURGE_BACKUP_CONFIRMED=1` ⇒ کدِ ۲ و صفر حذف.
۴. اگر حتی یکِ سفارش به محصولِ دیجیتال وصل باشد ⇒ کدِ ۲ و **صفر حذف** (تاریخچهٔ مالی نمی‌شکند).
۵. تنها در شرایطِ کامل (بدونِ سفارش + بکاپِ تأییدشده + عبارتِ درست) کدها و محصولات می‌روند و
   ستون‌ها/جدول‌ها سرِ جایشان می‌مانند (قاعدهٔ ۴).

اجرا: python3 tests_manual/run_one.py test_p94_purge_guards.py
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import select  # noqa: E402

from app.database.models import Customer, DigitalCode, OrderConsultation, OrderStatus, OrderType, Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from scripts import digital_products_purge as purge  # noqa: E402
from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 999_981
SHOP_BOT_TG_ID = 999_982


async def _seed_digital(with_order: bool = False) -> int:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID, initial_balance_toman=100_000)
    async with session_scope() as session:
        product = Product(shop_bot_id=shop_bot_id, name="دوره‌یِ پایتون", price_toman=200_000, kind="digital",
                          digital_delivery="code_pool", is_active=True)
        session.add(product)
        await session.flush()
        session.add(DigitalCode(product_id=product.id, code="ABC-123", code_hash="hash-1", status="available"))
        if with_order:
            customer = Customer(shop_bot_id=shop_bot_id, telegram_id=777_001, first_name="مشتری")
            session.add(customer)
            await session.flush()
            session.add(
                OrderConsultation(
                    shop_bot_id=shop_bot_id, customer_id=customer.id, product_id=product.id,
                    type=OrderType.ORDER, status=OrderStatus.COMPLETED, summary="دوره‌یِ پایتون",
                    quantity=1, confirmed=True,
                )
            )
        await session.commit()
    return shop_bot_id


async def _counts() -> tuple[int, int]:
    async with session_scope() as session:
        products = len((await session.execute(select(Product.id).where(Product.kind == "digital"))).all())
        codes = len((await session.execute(select(DigitalCode.id))).all())
    return products, codes


async def test_dry_run_deletes_nothing() -> None:
    await _seed_digital()
    code = await purge.run(execute=False, confirm="")
    assert code == 0, code
    assert await _counts() == (1, 1), "dry-run نباید چیزی را کم کند"
    print("PASS test_dry_run_deletes_nothing")


async def test_guards_refuse() -> None:
    await _seed_digital()
    assert await purge.run(execute=True, confirm="") == 2, "اجرا بدونِ عبارتِ تایید مجاز نیست"
    assert await purge.run(execute=True, confirm=purge.CONFIRM_PHRASE) == 2, "اجرا بدونِ تأییدِ بکاپ مجاز نیست"
    assert await _counts() == (1, 1)
    previous = os.environ.get("PURGE_BACKUP_CONFIRMED")
    os.environ["PURGE_BACKUP_CONFIRMED"] = "1"
    try:
        await _seed_digital(with_order=True)
        assert await purge.run(execute=True, confirm=purge.CONFIRM_PHRASE) == 2, "سفارشِ وصل‌شده ⇒ توقف"
        assert await _counts() == (1, 1), "با وجودِ سفارش، هیچ ردیفی حذف نمی‌شود"
    finally:
        if previous is None:
            os.environ.pop("PURGE_BACKUP_CONFIRMED", None)
        else:
            os.environ["PURGE_BACKUP_CONFIRMED"] = previous
    print("PASS test_guards_refuse")


async def test_full_conditions_purge_catalog_rows() -> None:
    await _seed_digital()
    previous = os.environ.get("PURGE_BACKUP_CONFIRMED")
    os.environ["PURGE_BACKUP_CONFIRMED"] = "1"
    try:
        code = await purge.run(execute=True, confirm=purge.CONFIRM_PHRASE)
    finally:
        if previous is None:
            os.environ.pop("PURGE_BACKUP_CONFIRMED", None)
        else:
            os.environ["PURGE_BACKUP_CONFIRMED"] = previous
    assert code == 0, code
    assert await _counts() == (0, 0), "با شرایطِ کامل، کاتالوگِ دیجیتال می‌رود"
    async with session_scope() as session:
        from sqlalchemy import text

        columns = (await session.execute(text(
            "select count(*) from information_schema.columns where table_name='products' and column_name='kind'"
        ))).scalar_one()
        tables = (await session.execute(text(
            "select count(*) from information_schema.tables where table_name='digital_codes'"
        ))).scalar_one()
    assert columns == 1 and tables == 1, "ساختار حذف نمی‌شود (داده بله، اسکیما نه)"
    print("PASS test_full_conditions_purge_catalog_rows")


async def main() -> None:
    await test_dry_run_deletes_nothing()
    await test_guards_refuse()
    await test_full_conditions_purge_catalog_rows()


if __name__ == "__main__":
    asyncio.run(main())
