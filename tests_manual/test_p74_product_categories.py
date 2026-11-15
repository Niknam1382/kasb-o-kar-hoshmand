"""پ۷۴ · خواستهٔ مالک (۲۰۲۶-۱۱-۱۵): «امکانِ دسته‌بندیِ محصولات در حالتِ فروشگاهی، تا کاربر بتواند
محصولات را دسته‌به‌دسته ببیند».

پوششِ داده‌شده:
۱. `normalize_category` و `category_view`: نرمال‌سازیِ ورودیِ متنی (فاصله‌هایِ اضافه، «خالی»، برشِ
   ۶۴ نویسه) و ساختنِ دسته‌ها از خودِ ردیف‌ها با ترتیبِ ثابتِ الفبایی (شمارهٔ دسته در callback).
۲. **هیچ‌چیز برایِ فروشگاهِ بی‌دسته عوض نمی‌شود:** کارتِ محصول، پرامپتِ AI و کیبوردِ کاتالوگِ مشتری
   بدونِ دسته دقیقاً مثلِ قبلند (نه خطِ «بی‌دسته»، نه ردیفِ فیلتر).
۳. پنلِ فروشگاه‌دار: اختصاصِ دسته از کارتِ محصول (نوشتن ⇒ ساخت/انتخاب، «خالی» ⇒ برداشتن)، فهرستِ
   دسته‌ها با شمار، صفحهٔ یکِ دسته، تغییرِ نامِ دسته (bulk)، برداشتنِ دسته با تایید، افزودنِ
   محصولِ بی‌دسته به دسته (bulk) و فهرستِ بی‌دسته‌ها با صفحه‌گردانی.
۴. سلامتِ ورودی: شمارهٔ دستهٔ بیرونِ فهرست و شناسهٔ محصولِ فروشگاهِ دیگر ⇒ توست، صفر ویرایش، صفر
   تغییرِ دیتابیس؛ «انصراف» حالت را پاک می‌کند و چیزی نمی‌نویسد.
۵. دروازۀ مود: فروشگاهِ مشاوره‌ای هیچ‌کدام از این صفحه‌ها را نمی‌بیند (کاتالوگ ندارد).
۶. کاتالوگِ مشتری: ردیفِ فیلتر فقط وقتی دسته هست می‌آید، «🏷 همه» برمی‌گرداند، فیلتر بینِ دو صفحه
   می‌ماند، و «➕ به سبد» رویِ محصولِ فیلترشده مثلِ قبل کار می‌کند.
۷. کیبورد: بودجهٔ ۶۴ بایتیِ همهٔ `category_*`/`cart_cat*`، ارقامِ جلالی در متن‌ها، و ثبتِ دکمه‌ها.

اجرا: python3 tests_manual/run_one.py test_p74_product_categories.py
"""
from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402

from app.bots.main_bot import keyboards as main_keyboards, texts as main_texts  # noqa: E402
from app.bots.shop_bot import keyboards as shop_keyboards, texts as shop_texts  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import ai_context, product_service, shop_owner_service  # noqa: E402
from harness import (  # noqa: E402
    FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database,
)
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_A = 997_501
SHOP_A = 997_502
OWNER_B = 997_503
SHOP_B = 997_504
CUSTOMER = 997_510
IDS: dict[str, int] = {}


async def _seed() -> None:
    """یکِ فروشگاهِ فروشگاهی با سه محصول (چای/پیراشکی/شیر) و یکِ فروشگاهِ مشاوره‌ای برایِ دروازه."""
    await reset_database()
    IDS["shop_a"] = await seed_usable_shop(OWNER_A, SHOP_A)
    IDS["shop_b"] = await seed_usable_shop(OWNER_B, SHOP_B)
    async with session_scope() as session:
        owner_b = await shop_owner_service.get_by_telegram_id(session, OWNER_B)
        await shop_owner_service.set_business_mode(session, owner_b, "consultation")
        for shop_bot_id, name, price in (
            (IDS["shop_a"], "چای", 20_000),
            (IDS["shop_a"], "پیراشکی", 35_000),
            (IDS["shop_a"], "شیر", 15_000),
            (IDS["shop_b"], "مشاورهٔ مالی", 100_000),
        ):
            product = await product_service.create_product(session, shop_bot_id, name, None, price, None)
            IDS[f"{name}"] = product.id
        await session.commit()


async def _products(shop_key: str = "shop_a"):
    async with session_scope() as session:
        return await product_service.get_active_by_shop_bot(session, IDS[shop_key])


async def _category_of(product_id: int) -> str:
    async with session_scope() as session:
        product = await session.get(product_service.Product, product_id)
        return product.category if product else "«ردیف نیست»"


async def _assign(product_key: str, name: str) -> None:
    async with session_scope() as session:
        product = await session.get(product_service.Product, IDS[product_key])
        await product_service.set_category(session, product, name)
        await session.commit()


# ============================================================================= ۱ — سرویس
def test_service_helpers() -> None:
    normalize = product_service.normalize_category
    assert normalize("  پیراشکی   سرد   ") == "پیراشکی سرد", "فاصله‌هایِ اضافه یکی می‌شوند"
    for empty in ("", "   ", "خالی", "-", "پاک کن", "بی‌دسته", None):
        assert normalize(empty) is None, empty
    assert normalize("دسته‌ای که خیلی بلند است " * 8) == ("دسته‌ای که خیلی بلند است " * 8).strip()[:64]
    assert len(normalize("دسته‌ای که خیلی بلند است " * 8)) == 64, "برش، نه رد"

    class _P:
        def __init__(self, pid, name, category):
            self.id, self.name, self.category = pid, name, category

    names, groups, unassigned = product_service.category_view([
        _P(1, "چای", "نوشیدنی"), _P(2, "پیراشکی", ""), _P(3, "آب", "نوشیدنی"), _P(4, "کاپ‌کیک", "شیرینی"),
    ])
    assert names == ("شیرینی", "نوشیدنی"), names  # ترتیبِ پایدارِ پایتون (کدپوینت)، نه الفبایِ فارسی
    assert [p.id for p in groups["نوشیدنی"]] == [1, 3] and [p.id for p in unassigned] == [2], (groups, unassigned)
    assert product_service.category_view([]) == ((), {}, [])
    print("PASS test_service_helpers")


# ============================================================================= ۲ — بی‌دسته ⇒ مثلِ قبل
async def test_uncategorized_shop_is_untouched() -> None:
    await _seed()
    products = await _products()
    assert all(p.category == "" for p in products), "سیدِ تازه بی‌دسته است (رفتارِ قبلِ پ۷۴)"
    for product in products:
        assert "🗂 دسته" not in main_texts.product_detail_text(product), product.name
    prompt = ai_context.build_system_prompt(
        await _shop_row(), products, None, None, learned_answers=None, gap_detection=False, bot_tools=[]
    )
    assert "[دسته:" not in prompt, prompt[:200]
    kb = shop_keyboards.products_browse_keyboard(products)
    flat = callbacks(kb)
    assert not any(item.startswith("cart_cat") for item in flat), flat
    assert any(item.startswith("cart_add:") for item in flat), flat
    print("PASS test_uncategorized_shop_is_untouched")


async def _shop_row():
    from app.services import shop_bot_service  # noqa: PLC0415

    async with session_scope() as session:
        return await shop_bot_service.get_by_id(session, IDS["shop_a"])


# ============================================================================= ۳ — پنلِ فروشگاه‌دار
async def test_owner_assign_and_remove(main_dp) -> None:
    await _seed()
    owner = Chat(main_dp, OWNER_A)
    await owner.say("📦 محصولات")
    labels = [b.text for row in owner.last_markup.inline_keyboard for b in row]
    assert main_texts.CATEGORY_BUTTON in labels, labels

    await owner.tap(f"product_view:{IDS['چای']}")
    labels = [b.text for row in owner.last_edit_markup.inline_keyboard for b in row]
    assert main_texts.CATEGORY_ASSIGN_BUTTON in labels, labels
    assert "🗂 دسته" not in owner.last_edit_text, "محصولِ بی‌دسته همان کارتِ قبلی است" 

    await owner.tap(f"product_category:{IDS['چای']}")
    assert "نامِ دسته را بنویس" in owner.last_text, owner.last_text
    await owner.say("  نوشیدنی   سرد  ")
    assert "«نوشیدنی سرد»" in owner.sent[-2]["text"], owner.sent[-2]["text"]
    assert "🗂 دسته: نوشیدنی سرد" in owner.last_text, owner.last_text
    assert await _category_of(IDS["چای"]) == "نوشیدنی سرد"

    await owner.tap(f"product_category:{IDS['چای']}")
    await owner.say("خالی")
    assert "بی‌دسته شد" in owner.sent[-2]["text"], owner.sent[-2]["text"]
    assert await _category_of(IDS["چای"]) == ""

    # انصراف ⇒ بی‌نوشتن
    await owner.tap(f"product_category:{IDS['چای']}")
    before = len(owner.sent)
    await owner.say("انصراف")
    assert owner.last_text == main_texts.OPERATION_CANCELLED, owner.last_text
    assert len(owner.sent) == before + 1
    assert await _category_of(IDS["چای"]) == ""
    print("PASS test_owner_assign_and_remove")


async def test_owner_category_screens_and_bulk(main_dp) -> None:
    await _seed()
    await _assign("چای", "نوشیدنی")
    await _assign("شیر", "نوشیدنی")
    owner = Chat(main_dp, OWNER_A)

    await owner.tap("category_list")
    body = owner.last_edit_text
    assert "۱ دسته · ۲ محصول دسته‌دار از ۳" in body, body
    assert "• نوشیدنی — ۲ محصول" in body and "محصولاتِ بی‌دسته: ۱" in body, body
    flat = callbacks(owner.last_edit_markup)
    assert flat == ["category_view:0", "category_unassigned", "product_list"], flat

    await owner.tap("category_view:0")
    body = owner.last_edit_text
    assert "🗂 نوشیدنی — ۲ محصول" in body and "چای" in body and "شیر" in body, body
    assert callbacks(owner.last_edit_markup) == [
        "category_rename:0", "category_clear:0", "category_attach:0", "category_list",
    ], callbacks(owner.last_edit_markup)

    await owner.tap("category_rename:0")
    assert "دستهٔ فعلی: «نوشیدنی»" in owner.last_text, owner.last_text
    await owner.say("نوشیدنی‌ها")
    assert "به «نوشیدنی‌ها» تغییر نام یافت (۲ محصول)" in owner.last_text, owner.last_text
    assert await _category_of(IDS["چای"]) == "نوشیدنی‌ها" and await _category_of(IDS["شیر"]) == "نوشیدنی‌ها"

    await owner.tap("category_list")
    await owner.tap("category_view:0")
    await owner.tap("category_clear:0")
    assert "مطمئنی" in owner.last_edit_text, owner.last_edit_text
    await owner.tap("category_clear_confirm:0")
    assert "دسته از ۲ محصول برداشته شد" in str([row.get("text") for row in owner.session.answered_callbacks]), owner.session.answered_callbacks[-1]
    assert await _category_of(IDS["چای"]) == "" and await _category_of(IDS["شیر"]) == ""

    # افزودنِ گروهی: بی‌دسته‌ها را داخلِ دسته می‌کند و همان صفحه می‌ماند
    await _assign("پیراشکی", "غذا")
    await owner.tap("category_list")
    await owner.tap("category_list")
    await owner.tap("category_view:0")  # «غذا» تنها دستهٔ باقی‌مانده ⇒ ایندکسِ ۰
    assert "🗂 غذا — ۱ محصول" in owner.last_edit_text, owner.last_edit_text
    await owner.tap("category_attach:0")
    flat = callbacks(owner.last_edit_markup)
    assert "category_assign:0:{}".format(IDS["چای"]) in flat, flat
    await owner.tap(f"category_assign:0:{IDS['چای']}")
    assert await _category_of(IDS["چای"]) == "غذا", await _category_of(IDS["چای"])
    assert "به دستهٔ «غذا» اضافه شد" in str([row.get("text") for row in owner.session.answered_callbacks])

    await owner.tap("category_unassigned")
    body = owner.last_edit_text
    assert "محصولاتِ بی‌دسته — ۱" in body, body
    assert callbacks(owner.last_edit_markup) == [f"product_category:{IDS['شیر']}", "category_list"], owner.last_edit_markup
    print("PASS test_owner_category_screens_and_bulk")


async def test_owner_stale_and_foreign_inputs(main_dp) -> None:
    await _seed()
    await _assign("چای", "نوشیدنی")
    owner = Chat(main_dp, OWNER_A)
    await owner.tap("category_list")

    edits_before = len(owner.edits)
    await owner.tap("category_view:7")
    assert owner.last_toast["text"] == main_texts.CATEGORY_STALE, owner.last_toast
    await owner.tap("category_rename:9")
    assert owner.last_toast["text"] == main_texts.CATEGORY_STALE
    await owner.tap("category_clear:9")
    assert owner.last_toast["text"] == main_texts.CATEGORY_STALE
    await owner.tap("category_clear_confirm:9")
    assert owner.last_toast["text"] == main_texts.CATEGORY_STALE
    await owner.tap("category_assign:0:999999")
    assert owner.last_toast["text"] == main_texts.CATEGORY_UNASSIGNED_STALE, owner.last_toast
    await owner.tap(f"category_assign:0:{IDS['مشاورهٔ مالی']}")  # محصولِ فروشگاهِ دیگر
    assert owner.last_toast["text"] == main_texts.CATEGORY_UNASSIGNED_STALE
    await owner.tap(f"product_category:{IDS['مشاورهٔ مالی']}")
    assert owner.last_toast["text"] == main_texts.GENERIC_ERROR, owner.last_toast
    assert len(owner.edits) == edits_before, "هیچ صفحه‌ای با ورودیِ دست‌کاری‌شده عوض نشد"
    assert await _category_of(IDS["چای"]) == "نوشیدنی" and await _category_of(IDS["مشاورهٔ مالی"]) == ""

    await owner.tap("product_category:999999")
    assert owner.last_toast["text"] == main_texts.GENERIC_ERROR
    print("PASS test_owner_stale_and_foreign_inputs")


async def test_consultation_gate(main_dp) -> None:
    await _seed()
    owner = Chat(main_dp, OWNER_B)
    before = len(owner.sent)
    await owner.tap("category_list")
    assert owner.last_toast["text"] == main_texts.CONSULT_NO_CATALOG, owner.last_toast
    await owner.tap(f"product_category:{IDS['مشاورهٔ مالی']}")
    assert owner.last_toast["text"] == main_texts.CONSULT_NO_CATALOG
    assert len(owner.edits) == 0 and len(owner.sent) == before, "مودِ مشاوره هیچ صفحهٔ تازه‌ای نمی‌بیند"
    assert await _category_of(IDS["مشاورهٔ مالی"]) == ""
    print("PASS test_consultation_gate")


# ============================================================================= ۶ — کاتالوگِ مشتری
async def test_customer_catalog_filter(shop_dp) -> None:
    await _seed()
    await _assign("چای", "نوشیدنی")
    await _assign("شیر", "نوشیدنی")
    bot = Bot(token=f"{SHOP_A}:FAKE_SHOP_BOT_TOKEN_FOR_P74_TESTS", session=FakeSession())
    uid = 0

    async def tap(data: str) -> None:
        nonlocal uid
        uid += 1
        await shop_dp.feed_update(bot, make_callback_update(uid, data=data, user_id=CUSTOMER))

    async def say(text: str) -> None:
        nonlocal uid
        uid += 1
        await shop_dp.feed_update(bot, make_message_update(uid, text=text, user_id=CUSTOMER))

    await say(shop_texts.BTN_PRODUCTS)
    sent = bot.session.sent_messages
    assert sent, "مشتری فهرستِ محصولات را گرفت"
    flat = callbacks(sent[-1]["reply_markup"])
    assert "cart_cat:" in flat and "cart_cat:0" in flat, flat
    first_row = [b.text for b in sent[-1]["reply_markup"].inline_keyboard[0]]
    assert first_row[0].startswith("✅") and "همه" in first_row[0], first_row
    assert any(item.startswith("cart_add:") for item in flat), flat

    await tap("cart_cat:0")
    edited = bot.session.edited_texts[-1]
    assert "🏷 دسته: نوشیدنی" in edited["text"], edited["text"]
    labels = [b.text for row in edited["reply_markup"].inline_keyboard for b in row]
    assert any("چای" in label for label in labels) and not any("پیراشکی" in label for label in labels), labels
    assert any("✅ نوشیدنی" in label for label in labels), labels

    await tap("cart_cat:")
    assert "🏷 دسته:" not in bot.session.edited_texts[-1]["text"], bot.session.edited_texts[-1]["text"]

    # ➕ به سبد، از داخلِ نمایِ فیلترشده
    await tap("cart_cat:0")
    await tap(f"cart_add:{IDS['چای']}")
    assert "سبد" in bot.session.sent_messages[-1]["text"] or "چای" in bot.session.sent_messages[-1]["text"]

    # دستهٔ بیرونِ فهرست ⇒ همان «همه»، بی‌خطا و بی‌صفحهٔ خالیِ ساختگی
    await tap("cart_cat:9")
    assert "🏷 دسته:" not in bot.session.edited_texts[-1]["text"], bot.session.edited_texts[-1]["text"]
    await bot.session.close()
    print("PASS test_customer_catalog_filter")


async def test_ai_prompt_and_paging_keyboard() -> None:
    await _seed()
    await _assign("چای", "نوشیدنی")
    products = await _products()
    prompt = ai_context.build_system_prompt(
        await _shop_row(), products, None, None, learned_answers=None, gap_detection=False, bot_tools=[]
    )
    assert "[دسته: نوشیدنی]" in prompt, prompt
    assert prompt.count("[دسته:") == 1, "فقطِ محصولِ دسته‌دار برچسب می‌گیرد"

    names, groups, unassigned = product_service.category_view(products)
    kb = shop_keyboards.products_browse_keyboard(groups[names[0]], 0, categories=names, active=names[0])
    flat = callbacks(kb)
    assert any(item.startswith("cart_cat:") for item in flat) and any(item.startswith("cart_add:") for item in flat), flat
    many = [SimpleNamespace(id=index, name=f"محصولِ {index}", price_toman=10_000, photo_file_id=None, category="نوشیدنی") for index in range(20)]
    kb2 = shop_keyboards.products_browse_keyboard(many, 0, categories=names, active=names[0])
    nav = [b.callback_data for row in kb2.inline_keyboard for b in row if b.callback_data and "catpage" in b.callback_data]
    assert nav == ["cart_catpage:0:1"], nav
    assert all(len(item.encode("utf-8")) <= 64 for row in main_keyboards.category_list_keyboard([("نوشیدنی", 3)], 2).inline_keyboard for b in row for item in [b.callback_data or ""]), "category_list_keyboard"
    assert all(
        len(item.encode("utf-8")) <= 64
        for row in main_keyboards.category_attach_keyboard(0, [], 0).inline_keyboard
        for b in row
        for item in [b.callback_data or ""]
    )
    print("PASS test_ai_prompt_and_paging_keyboard")


async def main() -> None:
    main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_service_helpers()
    await test_uncategorized_shop_is_untouched()
    await test_owner_assign_and_remove(main_dp)
    await test_owner_category_screens_and_bulk(main_dp)
    await test_owner_stale_and_foreign_inputs(main_dp)
    await test_consultation_gate(main_dp)
    await test_customer_catalog_filter(shop_dp)
    await test_ai_prompt_and_paging_keyboard()
    print("📊 نتیجه: ۸ تستِ پ۷۴ (دسته‌بندیِ محصولات) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
