"""
تست: P48 · موردِ ۱۳ (لاگِ حرفه‌ای + پنل)، ۳۹ و ۴۸ (ممیزیِ بهتر + بازهٔ زمانیِ دلخواه).

پوششِ داده‌شده:
۱. بافرِ حافظهٔ لاگ: یکِ هشدار و یکِ خطا را می‌گیرد، پیامِ بلند را می‌بُرد و رازِ داخلِ پیام را
   ماسک می‌کند (توکنِ ربات هرگز در `recent_logs()` باقی نمی‌ماند).
۲. نمای «فقط خطاها» ردیف‌هایِ WARNING را بیرون می‌گذارد.
۳. پنل: دکمهٔ «🧾 لاگِ سرور» صفحه را با کیبوردِ درست باز می‌کند، نما عوض می‌شود،
   «🔄 تازه‌کردن» نمایِ انتخابی را نگه می‌دارد، نمایِ ناشناخته بی‌ویرایش می‌ماند و
   ادمینِ عملیاتی اصلاً آن را باز نمی‌کند (قاعدهٔ §۲-۶).
۴. `audit_log_service.query(since=…, until=…)`: هر دو سرِ بازه رعایت می‌شوند (until شامل نیست).
۵. `audit_log_service.count_rows()`: «total» با تعدادِ ردیف‌ها یکی است و جمعِ دسته‌ها هم.
۶. جریانِ پنلِ ممیزی: «🗓 بازهٔ دلخواه» ← تاریخِ بد (خطا + همان سوال دوباره) ← بازهٔ درست ←
   سرِصفحه بازهٔ شمسی و خلاصهٔ شمارش را نشان می‌دهد و خروجیِ CSV همان فیلتر را می‌دهد.

اجرا: python3 tests_manual/test_p48_logs_and_audit_range.py
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from aiogram import Bot  # noqa: E402

from app import observability  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AuditEventType  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_role_service, ai_service, audit_log_service  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 999_843
OWNER_TG_ID = 999_841
SHOP_BOT_TG_ID = 999_842
MAIN_TOKEN = "000000:MAIN_BOT_FAKE_TOKEN_FOR_TESTS"
UTC = datetime.timezone.utc
# توکنِ جعلیِ ربات (قاعدهٔ aiogram: رقم‌ها، دونقطه، ≥۳۰ نویسه بعد از دونقطه) که نباید نشت کند.
FAKE_BOT_TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

RESULTS: list[str] = []


def _install_log_buffer() -> None:
    """بافرِ لاگ فقط پس ازِ `install()` به root logger می‌چسبد؛ در تست خودمان صداش می‌کنیم."""
    observability.install("INFO")
    observability.reset_recent_logs_for_tests()


# ============================================================================= ۱ — بافر: گرفتن، برش، ماسک
def test_buffer_captures_clips_and_masks() -> None:
    _install_log_buffer()
    logging.getLogger("app.services.ai_service").warning("پاسخِ کلیدِ AI نگرفته شد · توکن=%s", FAKE_BOT_TOKEN)
    try:
        raise RuntimeError("ساختِ فاکتورِ PDF شکست")
    except RuntimeError:
        logging.getLogger("app.utils.invoice").exception("خطایِ فاکتور")
    logging.getLogger("app.services.long").warning("پیامِ خیلی‌بلند " + "بسیارطویل " * 200)

    rows = observability.recent_logs(view="warnings", limit=20)
    assert len(rows) == 3, rows
    assert rows[0]["level"] == "WARNING" and rows[0]["where"] == "long", "تازه‌ترین‌ها اول"
    assert len(rows[0]["msg"]) <= observability.MAX_RECENT_LOG_LINE, "پیامِ بلند بریده می‌شود"

    token_row = next(row for row in rows if FAKE_BOT_TOKEN[:3] in row["msg"])
    dumped = json.dumps(rows, ensure_ascii=False)
    assert FAKE_BOT_TOKEN not in dumped, "رازِ توکن نباید در بافرِ قابلِ نمایش بماند"
    assert "ABCdef" not in dumped, "بخشِ حساسِ توکن ماسک نشده است"
    assert "●●●●" in token_row["msg"], token_row["msg"]

    error_row = next(row for row in rows if row["level"] == "ERROR")
    assert "ساختِ فاکتورِ PDF شکست" in error_row["exc"], error_row.get("exc")
    counts = observability.recent_log_counts()
    assert counts == {"warnings": 2, "errors": 1, "stored": 3}, counts

    observability.reset_recent_logs_for_tests()
    assert observability.recent_log_counts()["stored"] == 0
    print("✅ test_buffer_captures_clips_and_masks PASSED")
    RESULTS.append("بافرِ لاگ: گرفتن/برش/ماسک")


# ============================================================================= ۲ — نمای «فقط خطاها»
def test_errors_view_excludes_warnings() -> None:
    _install_log_buffer()
    logging.getLogger("app.a").warning("فقط‌هشدار")
    logging.getLogger("app.b").error("فقط‌خطا")

    errors = observability.recent_logs(view="errors", limit=20)
    assert [row["level"] for row in errors] == ["ERROR"], errors
    assert "فقط‌هشدار" not in json.dumps(errors, ensure_ascii=False)
    assert len(observability.recent_logs(view="warnings", limit=20)) == 2
    print("✅ test_errors_view_excludes_warnings PASSED")
    RESULTS.append("نمایِ فقط-خطا")


# ============================================================================= ۳ — صفحهٔ «🧾 لاگِ سرور»
async def test_server_log_panel(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    _install_log_buffer()
    logging.getLogger("app.services.ai_service").warning("کلیدِ AI دوم پاسخ نداد")
    logging.getLogger("app.handlers.admin").error("فاکتورِ PDF ساخته نشد")

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.SERVER_LOG_BUTTON)
    screen = admin.last_text
    assert "لاگ" in screen, screen
    assert "فقطِ همین پروسهٔ سرور" in screen, "صراحتِ لازم: بافرِ همین پروسه، نه لاگِ کاملِ سرور"
    assert "کلیدِ AI دوم" in screen and "فاکتورِ PDF" in screen, screen
    markup_buttons = callbacks(admin.last_markup)
    assert "logs_refresh" in markup_buttons and "logs_view:errors" in markup_buttons, markup_buttons
    assert "main_menu" in markup_buttons, "دکمهٔ بازگشت باید همان مصرف‌کنندهِٔ قبلی را داشته باشد"

    await admin.tap("logs_view:errors")
    edited = admin.last_edit_text
    assert "فاکتورِ PDF" in edited and "کلیدِ AI دوم" not in edited, edited
    assert "✅ " in admin.last_edit_markup.inline_keyboard[0][1].text

    await admin.tap("logs_refresh")
    assert "🔴 خطا" in admin.last_edit_text and "کلیدِ AI دوم" not in admin.last_edit_text

    before = len(admin.edits)
    await admin.tap("logs_view:bogus")
    assert len(admin.edits) == before, "نمایِ ناشناخته نباید پیامی را ویرایش کند"
    assert admin.last_toast["text"] == main_texts.GENERIC_ERROR, admin.last_toast

    # رازِ توکن حتی از مسیرِ پنل هم بیرون نمی‌آید
    logging.getLogger("app.bale").warning("وب‌هوک با توکنِ %s رد شد", FAKE_BOT_TOKEN)
    await admin.tap("logs_view:warnings")
    assert FAKE_BOT_TOKEN not in admin.last_edit_text, "لاگِ پنل نباید توکن خام نشان دهد"

    # قاعدهٔ §۲-۶: دکمهٔ تازهٔ منو فقط سوپرادمین است (همان گاردِ super_routerِ بقیهٔ صفحات)
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    operator_bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    operator_session = operator_bot.session
    await main_dp.feed_update(operator_bot, make_message_update(900, text=main_texts.SERVER_LOG_BUTTON, user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(operator_bot, make_callback_update(901, data="logs_refresh", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(operator_bot, make_callback_update(902, data="logs_view:errors", user_id=OPERATOR_TG_ID))
    assert not operator_session.sent_messages and not operator_session.edited_texts, "فقط سوپرادمین"
    print("✅ test_server_log_panel PASSED")
    RESULTS.append("صفحهٔ لاگِ سرور")


# ============================================================================= ۴ — مرزهایِ since/until
async def test_audit_query_honours_range() -> None:
    await reset_database()
    now = datetime.datetime.now(UTC)
    async with session_scope() as session:
        await audit_log_service.log(session, AuditEventType.PAYMENT_APPROVED, actor_telegram_id=ADMIN_TG_ID, details="تاییدِ تازه")
        await audit_log_service.log(session, AuditEventType.SHOP_SUSPENDED, actor_telegram_id=ADMIN_TG_ID, details="تعلیقِ تازه")
        await session.commit()

    async with session_scope() as session:
        inside = await audit_log_service.query(session, since=now - datetime.timedelta(hours=1), until=now + datetime.timedelta(hours=1))
        future = await audit_log_service.query(session, since=now + datetime.timedelta(hours=1))
        past = await audit_log_service.query(session, until=now - datetime.timedelta(hours=1))
        exclusive = await audit_log_service.query(session, until=now - datetime.timedelta(minutes=30))
        no_range = await audit_log_service.query(session)

    assert len(inside) == 2, [entry.details for entry in inside]
    assert future == [] and past == [], "بیرونِ بازه نباید ردیفی بدهد"
    assert exclusive == [], "مرزِ بازِ قدیمی هم فیلتر می‌شود"
    assert len(no_range) == 2, "بازهِ بدونِ since/until مثلِ قبل بدونِ فیلترِ زمان است"
    print("✅ test_audit_query_honours_range PASSED")
    RESULTS.append("مرزهایِ بازهٔ دلخواه")


# ============================================================================= ۵ — شمارشِ حرفه‌ای
async def test_audit_count_rows_total_and_buckets() -> None:
    await reset_database()
    now = datetime.datetime.now(UTC)
    seeded = [
        (AuditEventType.PAYMENT_APPROVED, "money"),
        (AuditEventType.PAYMENT_REJECTED, "money"),
        (AuditEventType.OWNER_GIFT_GRANTED, "money"),
        (AuditEventType.ADMIN_SETTING_CHANGED, "settings"),
        (AuditEventType.KILL_SWITCH_TOGGLED, "settings"),
        (AuditEventType.SHOP_SUSPENDED, "shops"),
    ]
    async with session_scope() as session:
        for event, _ in seeded:
            await audit_log_service.log(session, event, actor_telegram_id=ADMIN_TG_ID, details=f"رویدادِ {event.value}")
        await session.commit()

    async with session_scope() as session:
        counts = await audit_log_service.count_rows(session, since=now - datetime.timedelta(hours=1), until=now + datetime.timedelta(hours=1))
        empty = await audit_log_service.count_rows(session, since=now + datetime.timedelta(hours=1))

    assert counts["total"] == len(seeded), counts
    assert counts["payment_approved"] == 1 and counts["admin_setting_changed"] == 1, counts
    buckets = dict(main_texts.AUDIT_FILTER_GROUPS)
    grouped = {code: sum(counts.get(value, 0) for value in events) for code, events in audit_log_service.FILTER_GROUPS.items()}
    assert sum(grouped.values()) == counts["total"], "جمعِ دسته‌ها باید با کلِ ردیف‌ها بخواند (دسته‌ای جا نمی‌افتد)"
    assert grouped["money"] == 3 and grouped["settings"] == 2 and grouped["shops"] == 1, grouped
    assert buckets["money"] == "💰 پول"
    summary = main_texts.audit_counts_summary_line(counts["total"], ((buckets[code], grouped[code]) for code in ("money", "settings", "shops")))
    assert "۶ ردیف" in summary and "💰 پول: ۳" in summary, summary
    assert empty == {"total": 0}, empty
    print("✅ test_audit_count_rows_total_and_buckets PASSED")
    RESULTS.append("شمارشِ ردیف‌هایِ ممیزی")


# ============================================================================= ۶ — جریانِ بازهٔ دلخواه در پنل
async def test_audit_range_flow_and_csv(main_dp) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    now = datetime.datetime.now(UTC)
    async with session_scope() as session:
        await audit_log_service.log(session, AuditEventType.PAYMENT_APPROVED, actor_telegram_id=ADMIN_TG_ID, details="تاییدِ پرداختِ تست")
        await audit_log_service.log(session, AuditEventType.ADMIN_SETTING_CHANGED, actor_telegram_id=ADMIN_TG_ID, details="نرخِ تست")
        await session.commit()

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say("📜 گزارشِ ممیزی")
    assert "📜 گزارشِ ممیزی" in admin.last_text, admin.last_text
    assert "🗓 بازهٔ دلخواه" in "".join(b.text for row in admin.last_markup.inline_keyboard for b in row)

    await admin.tap("audit_range_from")
    assert "شروعِ بازه" in admin.last_text, admin.last_text

    # ورودیِ بد ⇒ پیامِ خطا و همان سوال دوباره (state می‌ماند)
    before = len(admin.sent)
    await admin.say("۱۴۰۴/۰۱/۱۵")
    assert main_texts.AUDIT_RANGE_INVALID in admin.last_text, admin.last_text
    assert len(admin.sent) == before + 1, "ورودیِ بد فقط همان سوال را دوباره می‌پرسد"
    await admin.say("2026-13-01")
    assert main_texts.AUDIT_RANGE_INVALID in admin.last_text, "تاریخِ بی‌معنا هم رد می‌شود"

    # ارقامِ فارسی هم پذیرفته می‌شوند؛ سپس پایانِ «خالی» ⇒ بازهٔ یک‌سرَباز
    start = now - datetime.timedelta(days=1)
    await admin.say(start.strftime("%Y-%m-%d").translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")))
    assert "پایانِ بازه" in admin.last_text, admin.last_text
    await admin.say("خالی")

    screen = admin.last_text
    assert "جایِ بازهٔ آماده" in screen and "بی‌حد" in screen, screen
    assert "📊 در این بازه" in screen, screen
    assert "تاییدِ پرداختِ تست" in screen, screen
    labels = [b.text for row in admin.last_markup.inline_keyboard for b in row]
    assert any("حذفِ بازه" in label for label in labels), labels

    # خروجیِ CSV همان بازه را رعایت می‌کند
    before_docs = len(admin.documents)
    await admin.tap("audit_csv")
    assert len(admin.documents) == before_docs + 1, "با بازهٔ شاملِ امروز باید فایلِ CSV برود"
    async with session_scope() as session:
        exported = await audit_log_service.get_recent(session, limit=1)
    assert "بازهٔ دلخواه" in (exported[0].details or ""), exported[0].details

    # حذفِ بازه ⇒ دکمه هم می‌رود و دفترِ کامل برمی‌گردد
    await admin.tap("audit_range_clear")
    after = admin.last_text
    assert "جایِ بازهٔ آماده" not in after, after
    assert not any("حذفِ بازه" in b.text for row in admin.last_markup.inline_keyboard for b in row)
    print("✅ test_audit_range_flow_and_csv PASSED")
    RESULTS.append("جریانِ بازهٔ دلخواه + CSV")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    ai_service.reset_all_circuits_for_tests()
    try:
        test_buffer_captures_clips_and_masks()
        test_errors_view_excludes_warnings()
        await test_server_log_panel(main_dp)
        await test_audit_query_honours_range()
        await test_audit_count_rows_total_and_buckets()
        await test_audit_range_flow_and_csv(main_dp)
    finally:
        observability.reset_recent_logs_for_tests()
        ai_service.reset_all_circuits_for_tests()
    print(f"📊 نتیجه: {len(RESULTS)} از ۶ تستِ P48 (لاگِ زنده + بازهٔ ممیزی) پاس شد · " + " · ".join(RESULTS))


if __name__ == "__main__":
    asyncio.run(main())
