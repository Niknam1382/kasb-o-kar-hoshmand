"""
تست: افزودنِ گروهیِ محصول از اکسل (فازِ ۲-ب، زیربخشِ ۲).

پوششِ دو لایه:
۱) excel_import_service.parse_workbook مستقیم (اعتبارسنجیِ ردیف‌به‌ردیف، فایلِ خراب، سقفِ تعدادِ ردیف)
۲) فلوِ کاملِ ربات با دیسپچرِ واقعی (دکمه → قالب → آپلود → پیش‌نمایش → تایید/انصراف)

اجرا: python3 tests_manual/run_all_tests.py
"""
from __future__ import annotations

import asyncio
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from openpyxl import Workbook  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.bots.main_bot import texts as main_bot_texts  # noqa: E402
from app.database.models import Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import excel_import_service  # noqa: E402

OWNER_TG_ID = 999900
SHOP_TG_ID = 999950


def _build_workbook(rows: list[tuple]) -> bytes:
    """یه فایلِ xlsxِ ساده — دقیقاً مثلِ چیزی که یه فروشگاه‌دار پرکرده — می‌سازه،
    برایِ شبیه‌سازیِ آپلود توسطِ کاربر."""
    wb = Workbook()
    ws = wb.active
    ws.append(list(excel_import_service.TEMPLATE_HEADERS))
    for row in rows:
        ws.append(list(row))
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# =============================================================================
# لایه‌ی سرویس — parse_workbook مستقیم
# =============================================================================
async def test_parse_workbook_validates_rows() -> None:
    content = _build_workbook(
        [
            ("لپ‌تاپ", "توضیحِ کامل", "15,000,000", 5),  # معتبر
            ("ماوس", None, 250_000, None),  # معتبر — توضیح/موجودی خالی = None
            (None, "توضیح", 100_000, None),  # نامِ خالی → خطا
            ("کیبورد", None, None, None),  # قیمتِ خالی → خطا
            ("هدفون", None, "قیمت نامشخص", None),  # قیمتِ نامعتبر → خطا
            ("اسپیکر", None, 50_000, -3),  # موجودیِ منفی → خطا
            (None, None, None, None),  # ردیفِ کاملاً خالی → نادیده گرفته می‌شه
            ("مانیتور", "توضیح مانیتور", 2_500_000.0, 10.0),  # سلولِ عددیِ float → معتبر
        ]
    )

    result = excel_import_service.parse_workbook(content)

    assert len(result.valid_rows) == 3, f"باید ۳ ردیفِ معتبر باشه، نه {len(result.valid_rows)}: {result.valid_rows}"
    assert result.valid_rows[0] == {"name": "لپ‌تاپ", "description": "توضیحِ کامل", "price_toman": 15_000_000, "stock_quantity": 5}
    assert result.valid_rows[1] == {"name": "ماوس", "description": None, "price_toman": 250_000, "stock_quantity": None}
    assert result.valid_rows[2] == {"name": "مانیتور", "description": "توضیح مانیتور", "price_toman": 2_500_000, "stock_quantity": 10}

    assert len(result.errors) == 4, f"باید ۴ ردیفِ خطادار باشه، نه {len(result.errors)}: {result.errors}"
    assert "ردیف 4" in result.errors[0] and "نامِ محصول خالیه" in result.errors[0]
    assert "ردیف 5" in result.errors[1] and "قیمت خالیه" in result.errors[1]
    assert "ردیف 6" in result.errors[2] and "قیمت نامعتبره" in result.errors[2]
    assert "ردیف 7" in result.errors[3] and "موجودی نامعتبره" in result.errors[3]
    assert result.too_many_rows is False
    print("✅ test_parse_workbook_validates_rows PASSED")


async def test_parse_workbook_rejects_corrupt_file() -> None:
    try:
        excel_import_service.parse_workbook(b"this is not a real xlsx file at all")
    except excel_import_service.InvalidExcelFileError:
        print("✅ test_parse_workbook_rejects_corrupt_file PASSED")
        return
    raise AssertionError("فایلِ خراب باید InvalidExcelFileError پرتاب می‌کرد")


async def test_parse_workbook_too_many_rows() -> None:
    rows = [(f"محصولِ {i}", None, 10_000, None) for i in range(excel_import_service.MAX_IMPORT_ROWS + 1)]
    content = _build_workbook(rows)

    result = excel_import_service.parse_workbook(content)

    assert result.too_many_rows is True, "باید too_many_rows=True برگرده"
    assert result.valid_rows == [] and result.errors == [], "وقتی too_many_rows بود نباید هیچ ردیفی توی نتیجه بمونه"
    print("✅ test_parse_workbook_too_many_rows PASSED")


# =============================================================================
# فلوِ کامل — دیسپچرِ واقعی
# =============================================================================
async def test_bulk_import_button_appears_and_sends_template(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_TG_ID)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_message_update(1, text="📦 محصولات", user_id=OWNER_TG_ID))
    markup = main_bot.session.sent_messages[-1]["reply_markup"]
    buttons = {btn.text for row in markup.inline_keyboard for btn in row}
    assert "📥 افزودن گروهی از اکسل" in buttons, "دکمه‌ی افزودنِ گروهی باید توی فهرستِ محصولات باشه"

    await main_dp.feed_update(main_bot, make_callback_update(2, data="product_bulk_import", user_id=OWNER_TG_ID))
    assert len(main_bot.session.sent_documents) == 1, "با زدنِ دکمه باید فایلِ قالب فرستاده بشه"
    print("✅ test_bulk_import_button_appears_and_sends_template PASSED")


async def test_bulk_import_full_flow_creates_products(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 1, SHOP_TG_ID + 1)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_bulk_import", user_id=OWNER_TG_ID + 1))

    content = _build_workbook(
        [
            ("لپ‌تاپ", "۱۶ گیگ رم", 25_000_000, 3),
            ("ماوس", None, 300_000, None),
            ("کیبوردِ خراب", None, "نامشخص", None),  # قیمتِ نامعتبر → این یکی رد می‌شه
        ]
    )
    main_bot.session.set_downloaded_file("import_file_1", content)
    await main_dp.feed_update(
        main_bot,
        make_message_update(2, document_file_id="import_file_1", document_file_name="my-products.xlsx", user_id=OWNER_TG_ID + 1),
    )

    preview = main_bot.session.sent_messages[-1]
    assert "2 ردیفِ معتبر" in preview["text"], f"پیامِ پیش‌نمایش: {preview['text']}"
    assert "قیمت نامعتبره" in preview["text"], "خطایِ ردیفِ سوم باید توی پیش‌نمایش دیده بشه"
    assert preview["reply_markup"] is not None, "باید کیبوردِ تایید/انصراف نشون داده بشه"

    await main_dp.feed_update(main_bot, make_callback_update(3, data="product_bulk_import_confirm", user_id=OWNER_TG_ID + 1))

    async with session_scope() as session:
        result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id).order_by(Product.id))
        products = result.scalars().all()

    assert len(products) == 2, f"باید فقط ۲ محصولِ معتبر ساخته بشه، نه {len(products)}"
    names = {p.name for p in products}
    assert names == {"لپ‌تاپ", "ماوس"}, f"اسم‌هایِ ساخته‌شده: {names}"
    laptop = next(p for p in products if p.name == "لپ‌تاپ")
    assert laptop.price_toman == 25_000_000 and laptop.stock_quantity == 3 and laptop.description == "۱۶ گیگ رم"
    mouse = next(p for p in products if p.name == "ماوس")
    assert mouse.price_toman == 300_000 and mouse.stock_quantity is None and mouse.description is None

    assert "2 محصول" in main_bot.session.answered_callbacks[-1]["text"]
    print("✅ test_bulk_import_full_flow_creates_products PASSED")


async def test_bulk_import_cancel_creates_nothing(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 2, SHOP_TG_ID + 2)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_bulk_import", user_id=OWNER_TG_ID + 2))
    content = _build_workbook([("محصولِ تستی", None, 100_000, None)])
    main_bot.session.set_downloaded_file("import_file_2", content)
    await main_dp.feed_update(
        main_bot, make_message_update(2, document_file_id="import_file_2", document_file_name="p.xlsx", user_id=OWNER_TG_ID + 2)
    )

    await main_dp.feed_update(main_bot, make_callback_update(3, data="product_bulk_import_cancel", user_id=OWNER_TG_ID + 2))

    async with session_scope() as session:
        result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))
        assert result.scalars().all() == [], "انصراف نباید هیچ محصولی بسازه"

    assert main_bot.session.answered_callbacks[-1]["text"] == main_bot_texts.PRODUCT_IMPORT_CANCELLED
    print("✅ test_bulk_import_cancel_creates_nothing PASSED")


async def test_bulk_import_rejects_non_xlsx_file(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID + 3, SHOP_TG_ID + 3)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_bulk_import", user_id=OWNER_TG_ID + 3))
    main_bot.session.set_downloaded_file("import_file_3", b"irrelevant content")
    await main_dp.feed_update(
        main_bot, make_message_update(2, document_file_id="import_file_3", document_file_name="notes.txt", user_id=OWNER_TG_ID + 3)
    )

    assert main_bot.session.sent_messages[-1]["text"] == main_bot_texts.PRODUCT_IMPORT_WRONG_FILE_TYPE

    async with session_scope() as session:
        result = await session.execute(select(Product).where(Product.shop_bot_id == shop_bot_id))
        assert result.scalars().all() == [], "فایلِ با پسوندِ اشتباه نباید هیچ محصولی بسازه"
    print("✅ test_bulk_import_rejects_non_xlsx_file PASSED")


async def test_bulk_import_all_invalid_rows_allows_retry(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID + 4, SHOP_TG_ID + 4)
    main_bot = Bot(token="000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS", session=FakeSession())

    await main_dp.feed_update(main_bot, make_callback_update(1, data="product_bulk_import", user_id=OWNER_TG_ID + 4))

    bad_content = _build_workbook([(None, "بدونِ اسم", 100_000, None)])
    main_bot.session.set_downloaded_file("import_bad", bad_content)
    await main_dp.feed_update(
        main_bot, make_message_update(2, document_file_id="import_bad", document_file_name="bad.xlsx", user_id=OWNER_TG_ID + 4)
    )
    assert "هیچ ردیفِ معتبری" in main_bot.session.sent_messages[-1]["text"]

    good_content = _build_workbook([("محصولِ خوب", None, 50_000, None)])
    main_bot.session.set_downloaded_file("import_good", good_content)
    await main_dp.feed_update(
        main_bot, make_message_update(3, document_file_id="import_good", document_file_name="good.xlsx", user_id=OWNER_TG_ID + 4)
    )
    assert "1 ردیفِ معتبر" in main_bot.session.sent_messages[-1]["text"], "بعدِ یه فایلِ خراب، باید بشه دوباره فایلِ درست فرستاد"
    print("✅ test_bulk_import_all_invalid_rows_allows_retry PASSED")


async def main() -> None:
    await test_parse_workbook_validates_rows()
    await test_parse_workbook_rejects_corrupt_file()
    await test_parse_workbook_too_many_rows()

    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_bulk_import_button_appears_and_sends_template(main_dp)
    await test_bulk_import_full_flow_creates_products(main_dp)
    await test_bulk_import_cancel_creates_nothing(main_dp)
    await test_bulk_import_rejects_non_xlsx_file(main_dp)
    await test_bulk_import_all_invalid_rows_allows_retry(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
