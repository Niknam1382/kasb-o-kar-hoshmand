"""
تست: P18 · ج (پنلِ مشاوره‌ای) — C1/C2/C3/C4.

پوشش:
۱. دامنه‌یِ منو: مشاوره بدونِ «📦 محصولات/🗂 خدمات و بسته‌ها»، بدونِ «👥 مشتری‌ها» (CRMِ فروش) و بدونِ
   «🧮 حسابداری»؛ به‌جایش «💬 گفتگوها و کاربران». فروشگاهی هر سه را دارد.
۲. آمار و گزارش‌هایِ مشاوره هیچ‌جا واژه‌یِ «سفارش» ندارند (شبانه، دوره‌ای و «📊 آمار»).
۳. خروجیِ اکسلِ مشاوره: برچسبِ دکمه‌ها، نامِ شیت و ستون‌ها بدونِ «سفارش»؛ مودِ فروشگاهی دست‌نخورده.
۴. افزودنِ محصول در مشاوره بسته است (هم کیبورد، هم هندلرِ کالبک — حتی با دکمه‌یِ کهنه).
۵. «💬 گفتگوها و کاربران»: فهرستِ مخاطبان + صفحه‌بندی + دیدنِ گفتگو + بلاک/رفعِ بلاک + ممیزی +
   اثرِ بلاک رویِ رباتِ مشتری + ایزولاسیونِ فروشگاه‌ها + راهنمایِ درست برایِ مودِ فروشگاهی.

اجرا: python3 tests_manual/test_p18_consultation_panel.py
"""
from __future__ import annotations

import asyncio
import io
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts as main_texts  # noqa: E402
from app.bots.shop_bot import middlewares as shop_middlewares  # noqa: E402
from app.bots.shop_bot import texts as shop_texts  # noqa: E402
from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    Customer,
    Product,
    ShopBot,
    ShopOwner,
    TenantMode,
)
from app.database.session import session_scope  # noqa: E402
from app.services import conversation_service, customer_service, excel_export_service, product_service  # noqa: E402

OWNER_TG_ID = 999_891
SHOP_BOT_TG_ID = 999_892
VISITOR_TG_ID = 999_893
VISITOR2_TG_ID = 999_894
OTHER_OWNER_TG_ID = 999_901
OTHER_SHOP_BOT_TG_ID = 999_902
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
CONTACTS_BUTTON = "💬 گفتگوها و کاربران"

STATS = {
    "messages_today": 3, "messages_week": 10, "messages_month": 40,
    "orders_count": 2, "consultations_count": 5, "top_products": [], "success_rate": None,
}
NIGHTLY = {
    "new_orders_today": 2, "new_consultations_today": 5, "new_customers_today": 1,
    "confirmed_revenue_today_toman": 100_000, "pending_orders_count": 2, "new_knowledge_gaps": 1,
}


def _labels(markup) -> set[str]:
    return {button.text for row in markup.keyboard for button in row}


def _datas(markup) -> list[str]:
    return [b.callback_data for row in markup.inline_keyboard for b in row if b.callback_data] if markup else []


async def _mode(shop_bot_id: int, mode: TenantMode) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        row.tenant_mode = mode


async def _customer(customer_id: int) -> Customer:
    async with session_scope() as session:
        return await session.get(Customer, customer_id)


# ============================================================================= ۱ — دامنه‌یِ منو
def test_panel_scope_per_mode() -> None:
    sales = _labels(keyboards.shop_owner_panel_keyboard(TenantMode.SALES))
    consult = _labels(keyboards.shop_owner_panel_keyboard(TenantMode.CONSULTATION))
    assert {"📦 محصولات", "👥 مشتری‌ها", "🧮 حسابداری", "🎯 کمپین‌ها", "💳 پرداختِ آنلاینِ سفارش‌ها"} <= sales
    assert CONTACTS_BUTTON not in sales, "صفحه‌یِ مشاوره در پنلِ فروشگاهی نیست"
    for gone in ("📦 محصولات", "🗂 خدمات و بسته‌ها", "👥 مشتری‌ها", "🧮 حسابداری", "🎯 کمپین‌ها", "📝 سوال‌هایِ چک‌اوتِ سبد"):
        assert gone not in consult, gone
    assert CONTACTS_BUTTON in consult
    # C4: تنظیماتِ per-shop در هر دو مود هست (پنلِ مشاوره هم «⚙️ تنظیماتِ ربات فروشگاه» دارد)
    assert "⚙️ تنظیماتِ ربات فروشگاه" in consult and "🧩 سوال‌هایِ بی‌جواب" in consult
    # هر دو مود هنوز مشترکاتِ لازم را دارند
    assert {"🔑 ثبت/ویرایش توکن ربات", "📊 آمار", "💰 کیف‌پول", "📤 خروجی اکسل", "💬 دستیارِ مدیریتی"} <= (sales & consult)
    print("✅ test_panel_scope_per_mode PASSED")


# ============================================================================= ۲ — آمار و گزارش‌ها
def test_no_order_word_in_consultation_reports() -> None:
    assert "سفارش" in main_texts.shop_stats_text(STATS)
    consult_stats = main_texts.shop_stats_text(STATS, consultation=True)
    assert "سفارش" not in consult_stats, consult_stats
    assert "💬 مشاوره‌ها: ۵" in consult_stats and "مخاطب" in consult_stats

    assert "سفارش" not in main_texts.periodic_report_text(STATS, 7, consultation=True)
    assert "سفارش" in main_texts.periodic_report_text(STATS, 7)

    nightly = main_texts.nightly_report_text(NIGHTLY, consultation=True)
    assert "سفارش" not in nightly, nightly
    assert "👥 مخاطبان جدید: ۱" in nightly and "💬 مشاوره‌های جدید: ۵" in nightly
    assert "سفارش" in main_texts.nightly_report_text(NIGHTLY)

    kb = keyboards.excel_export_choice_keyboard(consultation=True)
    labels = [b.text for row in kb.inline_keyboard for b in row]
    assert labels == ["👥 فهرست مخاطبان", "🧾 فهرست مشاوره‌ها"], labels
    sales_labels = [b.text for row in keyboards.excel_export_choice_keyboard().inline_keyboard for b in row]
    assert sales_labels == ["👥 فهرست مشتریان", "🧾 سفارش‌ها و مشاوره‌ها"], sales_labels
    print("✅ test_no_order_word_in_consultation_reports PASSED")


# ============================================================================= ۳ — اکسل
async def test_excel_headers_per_mode() -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        customer = await customer_service.get_or_create_customer(session, shop_bot_id, VISITOR_TG_ID, "مریم", "mary")
        await product_service.create_product(session, shop_bot_id, "مشاوره‌یِ رایگان", None, 0, None)
        customer_id = customer.id

    async with session_scope() as session:
        customers_bytes = await excel_export_service.build_customers_workbook(session, shop_bot_id, consultation=True)
        sales_bytes = await excel_export_service.build_customers_workbook(session, shop_bot_id)
        orders_bytes = await excel_export_service.build_orders_workbook(session, shop_bot_id, consultation=True)

    consult_sheet = load_workbook(io.BytesIO(customers_bytes)).active
    assert consult_sheet.title == "مخاطبان", consult_sheet.title
    headers = [cell.value for cell in consult_sheet[1]]
    assert "تعدادِ سفارش" not in headers and "تعدادِ مشاوره" in headers, headers
    assert headers[0] == "نام"

    sales_sheet = load_workbook(io.BytesIO(sales_bytes)).active
    assert sales_sheet.title == "مشتریان"
    assert "تعدادِ سفارش" in [cell.value for cell in sales_sheet[1]], "مودِ فروشگاهی دست‌نخورده"

    orders_sheet = load_workbook(io.BytesIO(orders_bytes)).active
    assert orders_sheet.title == "مشاوره‌ها" and "سفارش" not in orders_sheet.title
    assert customer_id > 0
    print("✅ test_excel_headers_per_mode PASSED")


# ============================================================================= ۴ — افزودنِ محصول بسته
async def test_cannot_add_products_in_consultation(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _mode(shop_bot_id, TenantMode.CONSULTATION)
    owner = Chat(main_dp, OWNER_TG_ID)

    await owner.say(CONTACTS_BUTTON)  # فقط برایِ این که state تمیز باشد
    await owner.say("🗂 خدمات و بسته‌ها")
    assert owner.last_text == main_texts.CONSULT_NO_CATALOG, owner.last_text
    await owner.say("📦 محصولات")
    assert owner.last_text == main_texts.CONSULT_NO_CATALOG

    # دکمه‌یِ کهنه/دستکاری‌شده هم چیزی نمی‌سازد
    async with session_scope() as session:
        before = len(list((await session.execute(select(Product))).scalars().all()))
    await owner.tap("product_add")
    assert owner.last_toast["text"] == main_texts.CONSULT_NO_CATALOG
    await owner.say("محصولِ مشکوک")
    async with session_scope() as session:
        after = len(list((await session.execute(select(Product))).scalars().all()))
    assert before == after, "با ورودیِ متنی هم محصولی ساخته نشد"

    await owner.tap("product_bulk_import")
    assert owner.last_toast["text"] == main_texts.CONSULT_NO_CATALOG

    # مودِ فروشگاهی همان مسیر را دارد
    await _mode(shop_bot_id, TenantMode.SALES)
    await owner.say("📦 محصولات")
    assert "➕ افزودن محصول جدید" in [b.text for row in owner.last_markup.inline_keyboard for b in row], _datas(owner.last_markup)
    print("✅ test_cannot_add_products_in_consultation PASSED")


# ============================================================================= ۵ — گفتگوها و کاربران
async def test_consult_contacts_screen_and_block(main_dp, shop_dp) -> None:
    await reset_database()
    shop_middlewares.reset_notice_cache()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _mode(shop_bot_id, TenantMode.CONSULTATION)
    async with session_scope() as session:
        visitor = await customer_service.get_or_create_customer(session, shop_bot_id, VISITOR_TG_ID, "زهرا", None)
        visitor2 = await customer_service.get_or_create_customer(session, shop_bot_id, VISITOR2_TG_ID, "کاوه", None)
        visitor_id, visitor2_id = visitor.id, visitor2.id
    async with session_scope() as session:
        for index in range(1, 9):
            await conversation_service.save_turn(session, visitor_id, f"سوالِ {index}", f"جوابِ {index}")

    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say(CONTACTS_BUTTON)
    assert "زهرا" in owner.last_text and "کاوه" in owner.last_text, owner.last_text
    data = _datas(owner.last_markup)
    assert f"cc_card:{visitor_id}:0" in data and f"cc_card:{visitor2_id}:0" in data, data

    await owner.tap(f"cc_card:{visitor_id}:0")
    assert "💬 گفتگو با" in owner.last_edit_text and "در مجموع ۱۶ پیام" in owner.last_edit_text, owner.last_edit_text
    assert "✅ فعال" in owner.last_edit_text
    card = _datas(owner.last_edit_markup)
    assert f"cc_block:{visitor_id}" in card and f"cc_card:{visitor_id}:1" in card and "cc_list:0" in card, card

    await owner.tap(f"cc_card:{visitor_id}:1")
    assert "صفحه‌یِ ۲ از ۲" in owner.last_edit_text, owner.last_edit_text

    await owner.tap(f"cc_block:{visitor_id}")
    assert owner.last_toast["text"] == main_texts.CONSULT_BLOCK_DONE
    assert "🚫 بلاک است" in owner.last_edit_text and f"cc_unblock:{visitor_id}" in _datas(owner.last_edit_markup)
    async with session_scope() as session:
        rows = list((await session.execute(select(Customer).where(Customer.id.in_([visitor_id, visitor2_id])))).scalars().all())
        by_id = {row.id: row for row in rows}
        assert by_id[visitor_id].is_blocked is True and by_id[visitor2_id].is_blocked is False, "فقط همانی که بلاک کردی"
        entries = list((await session.execute(select(AuditLogEntry).where(
            AuditLogEntry.event_type == AuditEventType.CUSTOMER_BLOCK_CHANGED.value
        ))).scalars().all())
        assert entries and entries[0].shop_bot_id == shop_bot_id

    # اثرِ واقعی رویِ رباتِ مشتریِ مشاوره‌ای: یک پیامِ ادبی، بدونِ هزینه
    visitor_bot = Bot(token=f"{SHOP_BOT_TG_ID}:FAKE", session=FakeSession())
    session_obj: FakeSession = visitor_bot.session  # type: ignore[assignment]
    async with session_scope() as session:
        owner_row = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        balance = owner_row.wallet_balance_toman
    await shop_dp.feed_update(visitor_bot, make_message_update(1, text="سلام، وقتت بخیر", user_id=VISITOR_TG_ID))
    assert [m["text"] for m in session_obj.sent_messages] == [shop_texts.CUSTOMER_BLOCKED_NOTICE]
    await shop_dp.feed_update(visitor_bot, make_message_update(2, text="چرا جواب نمی‌دی؟", user_id=VISITOR_TG_ID))
    assert len(session_obj.sent_messages) == 1, "حداکثر یک پیامِ ادبی"
    async with session_scope() as session:
        owner_row = (await session.execute(select(ShopOwner).where(ShopOwner.telegram_id == OWNER_TG_ID))).scalar_one()
        assert owner_row.wallet_balance_toman == balance, "هیچ هزینه‌ای نباید کسر شود"

    await owner.tap(f"cc_unblock:{visitor_id}")
    assert owner.last_toast["text"] == main_texts.CONSULT_UNBLOCK_DONE

    # کلیدهایِ دستکاری‌شده و ایزولاسیون
    for bad in (f"cc_card:{visitor_id}:x", "cc_card:abc:0", "cc_card:999999:0", f"cc_block:{visitor2_id + 10_000}"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == main_texts.CONSULT_CONTACTS_STALE, bad

    stranger = Chat(main_dp, OTHER_OWNER_TG_ID)
    other_shop_id = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await stranger.say(CONTACTS_BUTTON)
    assert stranger.last_text == main_texts.CONSULT_CONTACTS_SALES_HINT, "فروشگاهی ⇒ راهنما به «👥 مشتری‌ها»"
    await _mode(other_shop_id, TenantMode.CONSULTATION)
    await stranger.say(CONTACTS_BUTTON)
    assert stranger.last_text == main_texts.CONSULT_CONTACTS_EMPTY, "پنلِ خودش، مخاطبانِ خودش (خالی)"
    await stranger.tap(f"cc_card:{visitor_id}:0")
    assert stranger.last_toast["text"] == main_texts.CONSULT_CONTACTS_STALE, "فروشگاهِ دیگر گفتگویِ من را نمی‌بیند"
    await stranger.tap(f"cc_block:{visitor_id}")
    assert stranger.last_toast["text"] == main_texts.CONSULT_CONTACTS_STALE
    assert (await _customer(visitor_id)).is_blocked is False, "تلاشِ بیگانه برایِ بلاک، مخاطبِ من را بلاک نکرد"
    print("✅ test_consult_contacts_screen_and_block PASSED")


async def test_consult_contacts_empty_shop(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _mode(shop_bot_id, TenantMode.CONSULTATION)
    owner = Chat(main_dp, OWNER_TG_ID)
    await owner.say(CONTACTS_BUTTON)
    # P22 (لایهٔ ناوبری): صفحهٔ خالی دیگر بی‌دکمه نیست ⇒ «بازگشت به پنل» هست تا کاربر گیر نکند
    assert owner.last_text == main_texts.CONSULT_CONTACTS_EMPTY
    assert any("بازگشت به پنل" in btn.text for row in owner.last_markup.inline_keyboard for btn in row), owner.last_markup

    # مخاطبی بدونِ گفتگو
    async with session_scope() as session:
        lonely = await customer_service.get_or_create_customer(session, shop_bot_id, 555_001, "تنها", None)
        lonely_id = lonely.id
    await owner.say(CONTACTS_BUTTON)
    await owner.tap(f"cc_card:{lonely_id}:0")
    assert main_texts.CRM_CONVERSATION_EMPTY in owner.last_edit_text, owner.last_edit_text
    assert "✅ فعال" in owner.last_edit_text
    print("✅ test_consult_contacts_empty_shop PASSED")


async def main() -> None:
    main_dp, shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_panel_scope_per_mode()
    test_no_order_word_in_consultation_reports()
    await test_excel_headers_per_mode()
    await test_cannot_add_products_in_consultation(main_dp)
    await test_consult_contacts_screen_and_block(main_dp, shop_dp)
    await test_consult_contacts_empty_shop(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
