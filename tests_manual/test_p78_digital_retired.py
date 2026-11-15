"""پ۷۸ · موردِ ۲۵ (مالکِ محصول): «محصولِ دیجیتال» از دسترسِ ساخته‌شدن خارج می‌شود.

سه ادعا، همه سنجیدنی:
۱. پرچمِ درِ ساختنِ تازه به‌طورِ پیش‌فرض خاموش است و تنها چیزی است که بسته شده — مدل، انبارِ کد،
   مسیرِ تحویل و ویرایشِ محصول‌هایِ موجود دست‌نخورده‌اند (هیچ ستون/جدولی حذف نشده).
۲. کیبوردِ «محصولات» در مودِ فروشگاهی دیگر دکمهٔ «💾 افزودنِ محصولِ دیجیتال» ندارد، ولی دکمه‌هایِ
   دیگر (➕ محصولِ جدید، 🚚 ارسال، 📥 اکسل، 🗂 دسته) سرِ جایشان‌اند.
۳. کال‌بکِ دستکاری‌شده/کهنهٔ `product_add_digital` فقط یکِ توستِ صادقانه می‌دهد: نه state می‌نشیند،
   نه پیامی می‌فرستد، نه ردیفی می‌سازد. با پرچمِ روشن (حالتِ آزمایشی) همان جادوگر باز می‌شود، پس
   ادعایِ «فقطِ در بسته شده» دروغ نیست.

اجرا: python3 tests_manual/run_one.py test_p78_digital_retired.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import Product  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import digital_service  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

OWNER_TG_ID = 998_801
SHOP_BOT_TG_ID = 998_802


def test_flag_is_off_by_default() -> None:
    assert digital_service.NEW_DIGITAL_ALLOWED is False
    # هیچ چیزِ دیگری از این قابلیت حذف نشده (ادعایِ «فقطِ در»):
    for name in ("deliver_order", "is_digital", "add_codes", "sync_pool_stock", "validate_link"):
        assert callable(getattr(digital_service, name)), name
    assert digital_service.DELIVERY_MODES == ("file", "link", "text", "code_pool")
    assert "دیجیتال" in texts.DG_RETIRED and "متوقف" in texts.DG_RETIRED
    print("PASS test_flag_is_off_by_default")


_MAIN_DP = None


async def _chat() -> Chat:
    global _MAIN_DP
    if _MAIN_DP is None:
        _MAIN_DP = build_test_dispatchers()[0]  # راوترها singleton‌اند: فقط یکِ بار در هر پروسه
    await reset_database()
    digital_service.NEW_DIGITAL_ALLOWED = False
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    return Chat(_MAIN_DP, OWNER_TG_ID)


def test_button_is_gone_but_others_remain() -> None:
    flat = callbacks(keyboards.products_list_keyboard([], sales_mode=True))
    assert "product_add_digital" not in flat, flat
    assert {"product_add", "shipping_list", "product_bulk_import", "category_list"} <= set(flat), flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    print("PASS test_button_is_gone_but_others_remain")


async def test_stale_callback_is_refused_without_side_effects() -> None:
    chat = await _chat()
    messages_before = len(chat.session.sent_messages)
    await chat.tap("product_add_digital")
    assert chat.last_toast["text"] == texts.DG_RETIRED, chat.last_toast
    assert chat.last_toast["show_alert"] is True
    assert len(chat.session.sent_messages) == messages_before, "پیامی فرستاده نمی‌شود"
    async with session_scope() as session:
        assert (await session.execute(select(func.count()).select_from(Product))).scalar_one() == 0
    print("PASS test_stale_callback_is_refused_without_side_effects")


async def test_wizard_still_works_when_flag_is_on() -> None:
    chat = await _chat()
    digital_service.NEW_DIGITAL_ALLOWED = True
    try:
        await chat.tap("product_add_digital")
        assert texts.DG_ASK_NAME in chat.last_text, chat.last_text
    finally:
        digital_service.NEW_DIGITAL_ALLOWED = False
    print("PASS test_wizard_still_works_when_flag_is_on")


async def main() -> None:
    test_flag_is_off_by_default()
    test_button_is_gone_but_others_remain()
    await test_stale_callback_is_refused_without_side_effects()
    await test_wizard_still_works_when_flag_is_on()


if __name__ == "__main__":
    asyncio.run(main())
