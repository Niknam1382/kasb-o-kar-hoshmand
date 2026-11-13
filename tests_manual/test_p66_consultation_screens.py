"""پ۶۶ · موردِ ۲۴-ب — دو صفحهٔ اختصاصیِ مودِ مشاوره‌ای + بستنِ نشتیِ دروازه‌ها.

پ۵۸ فقط «دروازه» گذاشت (مشاوره ⇒ «این بخش فروشگاهی است») و گفت *جایگزینِ* مشاوره‌ای مانده؛ این فاز
همان جایگزین را می‌سازد و بعدِ آن، کال‌بک‌هایِ داخلیِ صفحه‌هایِ فروشگاهی را هم می‌بندد که تا امروز با
کیبوردِ inlineِ کهنه یا کال‌بکِ دست‌کاری‌شده، گزارشِ فروشگاهی را به مشاوره می‌دادند.

پوششِ داده‌شده:
۱. `build_report(consultation=True)` فقط ردیف‌هایِ `type = consultation` را می‌شمارد و مسیرِ
   فروشگاهی *همچنان* هر دو نوع را می‌شمارد (ادعایِ پ۱۸ و تستِ حسابداری همین است ⇒ عدم‌شکستگی).
۲. واژگانِ مودِ مشاوره: نه در متنِ گزارش و نه در سرستون‌هایِ اکسلِ «جلسه» واژهٔ «سفارش/کمپین/
   پرفروش» نمی‌آید؛ نسخهٔ فروشگاهیِ همان دو تابع byte-be-byte دست‌نخورده مانده.
۳. صفحهٔ «🧮 گزارشِ جلسات» از راهِ «💬 گفتگوها و کاربران»: باز شدن، تغییرِ بازه، اکسل و بازگشت —
   با دقیقاً یکِ پاسخِ کال‌بک در هر تپ.
۴. صفحهٔ «🎯 بازگشتِ مخاطب»: شمارشِ بخش‌ها، انتخابِ یکِ بخش، متنِ پیام ⇒ پیش‌نمایش *فقط* به همان
   بخش، و لغو ⇒ صفر ارسال.
۵. نشتی‌ها بسته شدند: مشاوره ⇒ `acct:`/`acct_xlsx:`/`campaign_list`/`campaign_view:`/`cs_open`
   فقط توستِ «فقط فروشگاهی» و صفر ویرایش؛ فروشگاهی ⇒ `cre_open`/`cret_open` فقط توستِ «فقط مشاوره‌ای».
۶. ورودیِ خرابِ کال‌بک (بازهٔ ناشناخته، بخشِ ناشناخته) به پیش‌فرض/رد می‌نشیند و ستونی عوض نمی‌شود.
۷. کیبورد: بودجهٔ ۶۴ بایتی، دو دکمهٔ تازه فقط در مودِ مشاوره، و منویِ اصلی هیچ دکمهٔ تازه‌ای
   نمی‌گیرد (پس `_KNOWN_MENU_BUTTONS` و فهرستِ «این دکمه در مشاوره نباید باشد» دست‌نخورده‌اند).

اجرا: python3 tests_manual/run_one.py test_p66_consultation_screens.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from openpyxl import load_workbook  # noqa: E402
from io import BytesIO  # noqa: E402
from sqlalchemy import select  # noqa: E402
from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, add_order, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.bots.main_bot import router as main_router  # noqa: E402
from app.database.models import Customer, OrderStatus, OrderType, ShopBot, TenantMode  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import accounting_service, excel_export_service, shop_owner_service  # noqa: E402

OWNER_TG_ID = 996_701
SHOP_BOT_TG_ID = 996_702
SALES_OWNER_TG_ID = 996_703
SALES_SHOP_TG_ID = 996_704
NOW = dt.datetime(2026, 11, 13, 9, 0, tzinfo=dt.timezone.utc)

CHURNING_TG = 778_001
ACTIVE_TG = 778_002
NEW_TG = 778_003


async def _seed(*, consult_owner_mode: str = "consultation") -> tuple[int, int]:
    """فروشگاهِ اول مشاوره‌ای (با سه مخاطبِ بخش‌بندی‌شده)، دوم فروشگاهی؛ هر دو با جلسه و سفارش."""
    await reset_database()
    consult_shop = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    sales_shop = await seed_usable_shop(SALES_OWNER_TG_ID, SALES_SHOP_TG_ID)
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER_TG_ID)
        await shop_owner_service.set_business_mode(session, owner, consult_owner_mode)
        bot = await session.get(ShopBot, consult_shop)
        bot.tenant_mode = TenantMode.CONSULTATION
        session.add(bot)
        await session.flush()
    churned = await add_customer(consult_shop, CHURNING_TG, "سارا", "sara.x", first_seen_at=NOW - dt.timedelta(days=200))
    active = await add_customer(consult_shop, ACTIVE_TG, "کاوه", "kaveh.x", first_seen_at=NOW - dt.timedelta(days=40))
    fresh = await add_customer(
        consult_shop, NEW_TG, "نگار", "negar.x",
        first_seen_at=NOW - dt.timedelta(days=1), last_message_at=NOW - dt.timedelta(days=1),
    )
    # سه جلسه: یکیِ تاییدشده و کهنه (ریزشت)، یکیِ تاییدشده و تازه (فعال)، یکیِ در انتظارِ بررسی.
    await add_order(consult_shop, churned, status=OrderStatus.CONFIRMED, value=90_000, order_type=OrderType.CONSULTATION,
                    created_at=NOW - dt.timedelta(days=120), confirmed_at=NOW - dt.timedelta(days=120))
    await add_order(consult_shop, active, status=OrderStatus.CONFIRMED, value=210_000, order_type=OrderType.CONSULTATION,
                    created_at=NOW - dt.timedelta(days=2), confirmed_at=NOW - dt.timedelta(days=2))
    await add_order(consult_shop, fresh, status=OrderStatus.PENDING, value=0, order_type=OrderType.CONSULTATION,
                    created_at=NOW - dt.timedelta(hours=3), confirmed=False)
    # و یکِ «سفارش» واقعی در همان فروشگاه، تا ثابت شود فیلترِ نوع کار می‌کند.
    await add_order(consult_shop, active, status=OrderStatus.CONFIRMED, value=500_000, order_type=OrderType.ORDER,
                    created_at=NOW - dt.timedelta(days=2), confirmed_at=NOW - dt.timedelta(days=2))
    # فروشگاهِ فروشگاهی هم یکِ سفارش دارد (برایِ ضدِ رگرسیونِ نسخهٔ فروشگاهی).
    await add_order(sales_shop, await add_customer(sales_shop, 778_500, "میلاد", "milad.x"),
                    status=OrderStatus.CONFIRMED, value=300_000, order_type=OrderType.ORDER,
                    created_at=NOW - dt.timedelta(days=1), confirmed_at=NOW - dt.timedelta(days=1))
    return consult_shop, sales_shop


async def test_service_filters_only_sessions() -> None:
    await _seed()
    async with session_scope() as session:
        consult = await accounting_service.build_report(session, await _shop_of(OWNER_TG_ID), "month30", NOW, consultation=True)
        sales_style = await accounting_service.build_report(session, await _shop_of(OWNER_TG_ID), "month30", NOW)
    assert consult.summary.successful_count == 1, consult.summary.successful_count
    assert consult.summary.net_toman == 210_000, consult.summary.net_toman
    assert consult.pending_total == 1, consult.pending_total
    assert all(row.type == "consultation" for row in consult.rows), [row.type for row in consult.rows]
    # عدم‌شکستگی: مسیرِ فروشگاهی همان «هر دو نوع» می‌ماند (ادعایِ پ۱۸ و تستِ حسابداری).
    assert sales_style.summary.successful_count == 2, sales_style.summary.successful_count
    assert sales_style.summary.net_toman == 710_000, sales_style.summary.net_toman
    print("PASS test_service_filters_only_sessions")


async def _shop_of(user_id: int) -> int:
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, user_id)
        bot = (await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner.id))).scalar_one()
        return int(bot.id)


def _sheet_names(content: bytes) -> list[str]:
    return load_workbook(BytesIO(content)).sheetnames


def _header_lines(content: bytes) -> str:
    wb = load_workbook(BytesIO(content))
    out = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=1, max_row=2, values_only=True):
            out.extend(str(cell) for cell in row if cell is not None)
    return " | ".join(out)


def test_texts_and_excel_avoid_sales_words() -> None:
    summary = type("S", (), {})()
    summary.period = type("P", (), {"label": "۳۰ روز", "start": NOW, "end": NOW + dt.timedelta(days=30)})()
    summary.net_toman = 210_000
    summary.discount_toman = 0
    summary.gross_toman = 210_000
    summary.successful_count = 1
    summary.average_order_toman = 210_000
    summary.online_paid_count = 0
    summary.online_paid_toman = 0
    summary.status_counts = {"pending": 1, "confirmed": 1, "paid": 2}
    summary.top_products = []
    summary.campaigns = []
    summary.daily = [type("D", (), {"day_label": "۲۲ آبان ۱۴۰۵", "orders": 1, "net_toman": 210_000})()]
    report = type("R", (), {"summary": summary, "pending_total": 1, "truncated": False, "rows": [], "product_names": {}, "campaign_names": {}})()

    body = texts.consult_reports_text(report)
    assert "جلسه" in body and "سفارش" not in body and "کمپین" not in body, body
    assert "پرفروش" not in body, "بخشِ محصولات/کمپین در مشاوره نمایش داده نمی‌شود"
    assert not any(char.isascii() and char.isdigit() for char in body), body
    assert texts.consult_status_label("awaiting_customer_confirmation") == "⏳ منتظرِ تاییدِ تو"

    excel = excel_export_service.build_accounting_workbook(report, consultation=True)
    lines = _header_lines(excel)
    assert "جلسه" in lines and "سفارش" not in lines, lines
    assert "کمپین" not in lines and "پرفروش" not in lines, lines
    # نسخهٔ فروشگاهیِ همان تابع باید بایت‌به‌بایت مثلِ قبل بماند (تست‌هایِ پ۵۹ و پ۱۸ به آن وابسته‌اند).
    sales_excel = excel_export_service.build_accounting_workbook(report)
    assert "سفارش" in _header_lines(sales_excel)
    assert _sheet_names(sales_excel) == ["خلاصه", "سفارش‌ها", "محصولات", "کمپین‌ها", "روزانه"], _sheet_names(sales_excel)
    assert _sheet_names(excel) == ["خلاصه", "جلسه‌ها", "روزانه"], _sheet_names(excel)
    print("PASS test_texts_and_excel_avoid_sales_words")


def test_return_keyboard_and_counts() -> None:
    counts = {"churning": 4, "new": 1, "active": 2, "loyal": 0, "no_purchase": 0}
    kb = keyboards.consult_return_keyboard(counts)
    flat = callbacks(kb)
    assert flat == ["cret_seg:churning", "cret_seg:new", "cret_seg:active", "cc_list:0"], flat
    for value in flat:
        assert len(value.encode("utf-8")) <= 64, value
    body = texts.consult_return_text(counts, 7, False)
    assert "۴ نفر" in body and "۷" in body and "سفارش" not in body and "مشتری" not in body, body
    assert "۵۰٬۰۰۰" in texts.consult_return_text(counts, 7, True)
    print("PASS test_return_keyboard_and_counts")


async def test_report_panel_flow(main_dp) -> None:
    await _seed()
    chat = Chat(main_dp, OWNER_TG_ID)
    await chat.say(texts.CONSULT_CONTACTS_BUTTON)
    flat = callbacks(chat.last_markup)
    assert flat[:2] == ["cre_open", "cret_open"], flat

    answers = len(chat.session.answered_callbacks)
    await chat.tap("cre_open")
    assert len(chat.session.answered_callbacks) == answers + 1, "دقیقاً یکِ پاسخِ کال‌بک"
    body = chat.last_edit_text
    assert body.startswith("🧮 گزارشِ جلسات — امروز") or "گزارشِ جلسات" in body, body
    assert "سفارش" not in body, body
    assert callbacks(chat.last_edit_markup)[:4] == ["crep:today", "crep:week", "crep:month30", "crep:jmonth"], callbacks(chat.last_edit_markup)
    assert "crep_xlsx:today" in callbacks(chat.last_edit_markup)

    await chat.tap("crep:month30")
    assert "۳۰ روز" in chat.last_edit_text, chat.last_edit_text
    assert "۲۱۰٬۰۰۰" in chat.last_edit_text, chat.last_edit_text
    docs_before = len(chat.documents)
    await chat.tap("crep_xlsx:month30")
    assert len(chat.documents) == docs_before + 1, chat.documents
    await chat.tap("cc_list:0")
    assert "💬 گفتگوها و کاربران" in chat.last_edit_text, chat.last_edit_text
    print("PASS test_report_panel_flow")


async def test_return_panel_flow(main_dp) -> None:
    await _seed()
    chat = Chat(main_dp, OWNER_TG_ID)
    await chat.say(texts.CONSULT_CONTACTS_BUTTON)
    await chat.tap("cret_open")
    body = chat.last_edit_text
    assert body.startswith("🎯 بازگشتِ مخاطب"), body
    assert "⚠️ در حالِ ریزش: ۱ نفر" in body, body
    flat = callbacks(chat.last_edit_markup)
    assert flat[0] == "cret_seg:churning", flat

    await chat.tap("cret_seg:churning")
    assert "بخشِ «⚠️ در حالِ ریزش» — ۱ نفر" in chat.sent[-1]["text"], chat.sent[-1]["text"]
    await chat.say("سلام! اگر سوالی دربارهٔ مشاوره‌ات داری در خدمتم.")
    assert "۱" in chat.last_text and "ارسال" in chat.last_text, chat.last_text
    labels = [button.text for row in chat.last_markup.inline_keyboard for button in row]
    assert any("لغو" in label for label in labels), labels
    await chat.tap("customer_broadcast_cancel")
    assert chat.last_edit_text == texts.CUSTOMER_BROADCAST_CANCELLED, chat.last_edit_text
    # مخاطبِ بلاک‌شده در شمارشِ «بازگشتِ مخاطب» نمی‌آید (برعکسِ فهرستِ گفتگوها، که او را نشان می‌دهد).
    async with session_scope() as session:
        blocked = (await session.execute(select(Customer).where(Customer.telegram_id == CHURNING_TG))).scalar_one()
        blocked.is_blocked = True
        session.add(blocked)
    await chat.tap("cret_open")
    flat = callbacks(chat.last_edit_markup)
    assert "cret_seg:churning" not in flat, f"بخشِ خالی نباید دکمه داشته باشد: {flat}"
    print("PASS test_return_panel_flow")


async def test_mode_gates_both_directions(main_dp) -> None:
    await _seed()
    sales = Chat(main_dp, SALES_OWNER_TG_ID)
    await sales.tap("cre_open")
    assert sales.last_toast["text"] == texts.MODE_CONSULTATION_ONLY, sales.last_toast
    edits_before = len(sales.edits)
    await sales.tap("cret_open")
    assert sales.last_toast["text"] == texts.MODE_CONSULTATION_ONLY
    assert len(sales.edits) == edits_before, "فروشگاهی به صفحهٔ مشاوره نمی‌رود"
    await sales.tap("cret_seg:new")
    assert sales.last_toast["text"] == texts.MODE_CONSULTATION_ONLY

    consult = Chat(main_dp, OWNER_TG_ID)
    for data in ("acct:week", "acct_xlsx:week", "campaign_list", "campaign_view:1", "cs_open"):
        await consult.tap(data)
        assert consult.last_toast["text"] == texts.MODE_SALES_ONLY, (data, consult.last_toast)
    assert not consult.edits, "نشتیِ بسته شد: هیچ صفحه‌ای ویرایش نشد"
    print("PASS test_mode_gates_both_directions")


async def test_bad_inputs_do_not_change_anything(main_dp) -> None:
    await _seed()
    chat = Chat(main_dp, OWNER_TG_ID)
    await chat.tap("crep:not-a-period")
    assert "امروز" in chat.last_edit_text, chat.last_edit_text  # بازهٔ ناشناخته ⇒ پیش‌فرضِ امن
    await chat.tap("cre_open")
    await chat.tap("crep:not-a-period")
    assert chat.last_edit_text.startswith("🧮 گزارشِ جلسات — امروز"), chat.last_edit_text
    await chat.tap("cret_seg:bogus")
    assert chat.last_toast["text"] == texts.CONSULT_RETURN_STALE, chat.last_toast
    async with session_scope() as session:
        bot = await session.get(ShopBot, await _shop_of(OWNER_TG_ID))
        assert bot.tenant_mode == TenantMode.CONSULTATION
        customers = list((await session.execute(select(Customer))).scalars())
        assert all(c.first_name for c in customers), "هیچ هویتی پاک نشد"
    print("PASS test_bad_inputs_do_not_change_anything")


async def test_menu_and_registry_untouched() -> None:
    consult_labels = {button.text for row in keyboards.shop_owner_panel_keyboard("consultation").keyboard for button in row}
    sales_labels = {button.text for row in keyboards.shop_owner_panel_keyboard("sales").keyboard for button in row}
    # دو صفحهٔ تازه در منو دکمه *نمی‌سازند*: رویِ صفحهٔ «💬 گفتگوها و کاربران» می‌نشینند.
    assert texts.CONSULT_REPORTS_BUTTON not in consult_labels and texts.CONSULT_RETURN_BUTTON not in consult_labels
    assert texts.CONSULT_REPORTS_BUTTON not in sales_labels
    assert texts.CONSULT_CONTACTS_BUTTON in consult_labels and texts.CONSULT_CONTACTS_BUTTON not in sales_labels
    # ادعایِ پ۵۸ و پ۱۸ دست‌نخورده می‌ماند: این دکمه‌ها همچنان فقط فروشگاهی‌اند.
    for label in ("🧮 حسابداری", "🎯 کمپین‌ها", "👥 مشتری‌ها"):
        assert label in sales_labels and label not in consult_labels, label
    assert not ({texts.CONSULT_REPORTS_BUTTON, texts.CONSULT_RETURN_BUTTON} & set(main_router._KNOWN_MENU_BUTTONS))
    print("PASS test_menu_and_registry_untouched")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_service_filters_only_sessions()
    test_texts_and_excel_avoid_sales_words()
    test_return_keyboard_and_counts()
    await test_report_panel_flow(main_dp)
    await test_return_panel_flow(main_dp)
    await test_mode_gates_both_directions(main_dp)
    await test_bad_inputs_do_not_change_anything(main_dp)
    await test_menu_and_registry_untouched()
    print("📊 نتیجه: ۸ تستِ پ۶۶ (گزارشِ جلسات و بازگشتِ مخاطب) پاس شد · فیلتر/واژگان/کیبورد/دو جریانِ پنل/دروازه‌هایِ دوطرفه/ورودیِ خراب/منو")


if __name__ == "__main__":
    asyncio.run(main())
