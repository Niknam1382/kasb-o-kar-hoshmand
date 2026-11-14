"""پ۷۲ · خواستهٔ مالک (۲۰۲۶-۱۱-۱۲): آستانه‌هایِ عیب‌یابِ سرور تنظیم‌شدنی شوند + شمارنده‌ها در
پنجرهٔ زمانی قضاوت شوند.

پوششِ داده‌شده:
۱. `THRESHOLD_SPECS`: هر یازده کلید پیش‌فرض + کرانِ پایین/بالا + نوع دارد؛ کرانِ خودش معتبر است
   و نوعِ «درصد» فقط رویِ کلیدهایِ `_percent` می‌نشیند.
۲. سریال‌سازیِ مقاوم: `None`/JSONِ خراب/کلیدِ ناشناخته ⇒ پیش‌فرضِ نسخه، عددهایِ بیرونِ کران
   ⇒ به نزدیک‌ترین کران می‌چسبند، و `dump` فقطِ تفاوت‌ها را نگه می‌دارد (همه‌پیش‌فرض ⇒ ستونِ خالی).
۳. ورودیِ ادمین: ارقامِ جلالی/عربی و جداکنندهٔ هزار پذیرفته می‌شوند؛ واحدِ درصد، حرفِ لاتین و
   عددِ بیرونِ کران ⇒ None.
۴. `window_deltas`: اولین خواندن ⇒ جمعِ کل با برچسبِ «از شروعِ این پروسه»، خواندنِ بعد ⇒ تفاضل،
   snapshotِ کهنه‌تر از دو پنجره ⇒ دوباره جمعِ کل، و ری‌استارتِ پروسه (شمارنده پایین‌تر از
   snapshot) ⇒ عددِ منفی نمی‌سازد.
۵. تشخیص واقعاً از آستانهٔ *ذخیره‌شده* می‌خواند: همان عددِ رم با آستانهٔ پایین‌تر شعله می‌شود و
   دیسکِ ۹۰٪ با آستانهٔ ۹۵٪ خاموش می‌ماند (ثابتِ کد جایِ مقدارِ پنل را نمی‌گیرد).
۶. پنلِ سوپرادمین: فهرستِ آستانه‌ها ⇒ ویرایشِ یکِ کلید (FSM) ⇒ عددِ بیرونِ کران state را نگه
   می‌دارد و چیزی نمی‌نویسد ⇒ عددِ درست ذخیره + ممیزی ⇒ فهرستِ تازه با برچسبِ «(خودت)» ⇒
   بازگشتِ همه به پیش‌فرض (ستون NULL)؛ کلیدِ دست‌کاری‌شده ⇒ توستِ «دیگر معتبر نیست».
۷. `inspect` همان آستانه‌ها را مصرف می‌کند و هنوز فقط‌خواندنی است؛ اپراتورِ عملاتی هیچ‌کدام از
   صفحه‌هایِ آستانه را نمی‌بیند.

اجرا: python3 tests_manual/run_one.py test_p72_doctor_thresholds.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import observability  # noqa: E402
from app.bots.main_bot import texts as main_texts  # noqa: E402
from app.database.models import AuditEventType, AuditLogEntry  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service, server_doctor  # noqa: E402
from harness import (  # noqa: E402
    FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database,
)
from phase4_helpers import Chat, callbacks  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 996655
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P72_TESTING"
_LIM = server_doctor.defaults()


def _keys(findings) -> set[str]:
    return {finding.key for finding in findings}


def _system(disk=None, memory=None, load_percent=None, cores=4) -> dict:
    return {
        "cores": cores, "load1": None, "load_percent": load_percent,
        "memory_used_percent": memory, "disk_used_percent": disk, "disk_label": "بکاپ‌ها",
    }


def _db(percent=10.0, checked_out=1, capacity=10, overflow=0) -> dict:
    return {"size": capacity, "checked_out": checked_out, "overflow": overflow, "capacity": capacity, "percent": percent}


def _ai(percent=0.0, inflight=0, usable=20) -> dict:
    return {
        "keys": [object()], "sum_caps": 20, "platform_ceiling": 40, "usable": usable,
        "inflight_total": inflight, "percent": percent, "bottleneck": "keys",
        "voice": {"count": 0, "sum_caps": 0, "inflight": 0},
    }


async def _raw_column() -> str | None:
    async with session_scope() as session:
        return (await admin_settings_service.get_admin_settings(session)).doctor_thresholds


async def _audit_details(event_type: AuditEventType) -> list[str]:
    async with session_scope() as session:
        rows = (
            await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == event_type))
        ).scalars().all()
    return [row.details or "" for row in rows]


# ============================================================================= ۱ و ۲ — آستانه‌ها و سریال‌سازی
def test_specs_are_self_consistent() -> None:
    base = server_doctor.defaults()
    assert set(base) == set(server_doctor.THRESHOLD_KEYS) == set(server_doctor.THRESHOLD_SPECS)
    assert len(base) == 11, len(base)
    for key, (default, low, high, kind, label) in server_doctor.THRESHOLD_SPECS.items():
        assert low <= default <= high, key
        assert kind in {"percent", "count"}, key
        assert (kind == "percent") == key.endswith("_percent"), key
        assert label and label[0].isprintable(), key
    # پیش‌فرضِ نسخه همان عددِ پ۶۲ است تا پنلِ ظرفیت و عیب‌یاب یکی بمانند
    assert base["disk_percent"] == server_doctor.DISK_ALERT_PERCENT == 85.0
    assert base["memory_percent"] == server_doctor.MEMORY_ALERT_PERCENT == 90.0
    assert base["window_minutes"] == float(server_doctor.WINDOW_MINUTES_DEFAULT)
    print("PASS test_specs_are_self_consistent")


def test_threshold_serialisation_is_defensive() -> None:
    base = server_doctor.defaults()
    assert server_doctor.parse_thresholds(None) == base
    for junk in ("", "   ", "نه JSON", "[]", "null", '{"memory_percent": "پنجاه"}', '{"memory_percent": null}'):
        assert server_doctor.parse_thresholds(junk) == base, junk
    # کلیدِ ناشناخته نادیده گرفته می‌شود (نه خطا، نه نوشتنِ چیزِ بی‌معنی در ستون)
    assert server_doctor.parse_thresholds('{"memory_percent": 70, "made_up": 1}') == {**base, "memory_percent": 70.0}
    # بیرونِ کران ⇒ به نزدیکِ‌ترین کران می‌چسبد (نه ردِ کاملِ فایلِ تنظیمات)
    clamped = server_doctor.parse_thresholds('{"memory_percent": 5, "load_percent": 5000, "window_minutes": 99999}')
    assert clamped["memory_percent"] == 50.0 and clamped["load_percent"] == 500.0, clamped
    assert clamped["window_minutes"] == 1440.0, clamped
    assert server_doctor.dump_thresholds(base) is None, "همه‌پیش‌فرض ⇒ ستونِ خالی"
    stored = server_doctor.dump_thresholds(clamped)
    assert json.loads(stored) == {"load_percent": 500.0, "memory_percent": 50.0, "window_minutes": 1440.0}, stored
    assert server_doctor.parse_thresholds(stored) == clamped, "رفت و برگشتِ کامل"
    print("PASS test_threshold_serialisation_is_defensive")


def test_admin_input_parsing() -> None:
    parse = server_doctor.parse_input
    assert parse("memory_percent", "۸۰") == 80.0
    assert parse("memory_percent", " ٨٠ ") == 80.0, "ارقامِ عربی هم پذیرفته می‌شود"
    assert parse("memory_percent", "۸۰.۵") == 80.5 and parse("memory_percent", "۸۰٫۵") == 80.5
    assert parse("webhook_rejected", "۱٬۲۰۰") == 1200.0
    assert parse("webhook_rejected", "1,200") == 1200.0, "ویرگولِ لاتین هم جداکنندهٔ هزار است"
    for bad in ("", "   ", None, "پنجاه", "80abc", "۸۰٪", "۸۰ درصد", "--", "٭"):
        assert parse("memory_percent", bad) is None, bad
    assert parse("memory_percent", "-۱۰") is None and parse("memory_percent", "۹۹٫۹") is None
    assert parse("memory_percent", "۹۹") == 99.0 and parse("memory_percent", "۵۰") == 50.0
    assert parse("memory_percent", "۱۰۰") is None, "کرانِ بالایِ درصدِ مصرف ۹۹ است"
    assert parse("log_errors", "۵") == 5.0 and parse("log_errors", "۰") is None, "شمارِ صفر معنی ندارد"
    assert parse("window_minutes", "۴") is None and parse("window_minutes", "۵") == 5.0
    print("PASS test_admin_input_parsing")


# ============================================================================= ۳ — پنجرهٔ شمارنده‌ها
def test_window_deltas_labels_and_guards() -> None:
    server_doctor.reset_alert_clock_for_tests()
    totals, label = server_doctor.window_deltas({"webhook.rejected": 40}, 60)
    assert totals == {"webhook.rejected": 40} and label == "از شروعِ این پروسه", (totals, label)
    deltas, second = server_doctor.window_deltas({"webhook.rejected": 46}, 60)
    assert deltas == {"webhook.rejected": 6}, deltas
    assert second.startswith("در ") and "دقیقهٔ گذشته" in second, second
    # ری‌استارتِ پروسه: شمارنده از snapshotِ قبلی کمتر ⇒ تفاضلِ منفی ساخته نمی‌شود
    assert server_doctor.window_deltas({"webhook.rejected": 3}, 60)[0] == {"webhook.rejected": 0}
    server_doctor._counter_state["at"] = time.monotonic() - 3 * 3600  # noqa: SLF001
    stale_totals, third = server_doctor.window_deltas({"webhook.rejected": 90}, 60)
    assert stale_totals == {"webhook.rejected": 90} and third == "از شروعِ این پروسه", (stale_totals, third)
    print("PASS test_window_deltas_labels_and_guards")


# ============================================================================= ۴ — تشخیص از آستانهٔ موثر
def test_verdict_follows_the_stored_threshold() -> None:
    row = _system(memory=78.0)
    assert "memory" not in _keys(server_doctor._thresholds(row, _db(), _ai(), _LIM))  # noqa: SLF001
    softer = server_doctor._thresholds(row, _db(), _ai(), {**_LIM, "memory_percent": 75.0})  # noqa: SLF001
    assert "memory" in _keys(softer), "آستانهٔ پایین‌تر ⇒ همان عدد شعله می‌شود"
    detail = [f for f in softer if f.key == "memory"][0].detail
    assert "آستانه" in detail and "۷۵" in detail, detail

    # ثابتِ کد نباید جایِ مقدارِ پنل را بگیرد (دیسک در پ۶۲ سخت‌کد بود)
    assert "disk" in _keys(server_doctor._thresholds(_system(disk=80.0), _db(), _ai(), {**_LIM, "disk_percent": 70.0})), (  # noqa: SLF001
        "آستانهٔ ۷۰٪ ⇒ دیسکِ ۸۰٪ باید پیدا شود"
    )
    assert "disk" not in _keys(server_doctor._thresholds(_system(disk=90.0), _db(), _ai(), {**_LIM, "disk_percent": 95.0})), (  # noqa: SLF001
        "آستانهٔ ۹۵٪ ⇒ دیسکِ ۹۰٪ (که با پیش‌فرضِ ۸۵٪ شعله می‌شد) باید خاموش بماند"
    )
    assert "db_pool" in _keys(server_doctor._thresholds(_system(), _db(percent=92.0), _ai(), _LIM))  # noqa: SLF001
    assert "db_pool" not in _keys(server_doctor._thresholds(_system(), _db(percent=92.0), _ai(), {**_LIM, "db_pool_percent": 95.0})), (  # noqa: SLF001
        "استخرِ دیتابیس هم از همان ستون می‌خواند"
    )
    assert "ai_pressure" in _keys(server_doctor._thresholds(_system(), _db(), _ai(percent=70.0, inflight=14), {**_LIM, "ai_pressure_percent": 60.0})), (  # noqa: SLF001
        "فشارِ AI هم تنظیم‌شدنی است"
    )

    counters = {"webhook.rejected": 12, "webhook.rate_limited": 4, "wallet.deduct_denied": 2}
    assert "webhook_rejected" not in _keys(server_doctor._counter_findings(counters, _LIM, "در ۵ دقیقهٔ گذشته")), (  # noqa: SLF001
        "پیش‌فرض ۲۰ است"
    )
    assert "webhook_rejected" in _keys(server_doctor._counter_findings(counters, {**_LIM, "webhook_rejected": 10.0}, "در ۵ دقیقهٔ گذشته")), (  # noqa: SLF001
        "با آستانهٔ ۱۰ باید بیاید"
    )
    assert "wallet_denied" in _keys(server_doctor._counter_findings(counters, {**_LIM, "wallet_denied": 2.0}, "در ۵ دقیقهٔ گذشته"))  # noqa: SLF001
    assert _keys(server_doctor._log_findings(0, 0, 3, {**_LIM, "log_errors": 3.0})) == {"log_errors"}  # noqa: SLF001
    assert _keys(server_doctor._log_findings(2, 0, 0, {**_LIM, "ai_failures": 2.0})) == {"ai_failures"}  # noqa: SLF001
    print("PASS test_verdict_follows_the_stored_threshold")


# ============================================================================= ۵ — پنلِ ادمین
async def test_threshold_panel_flow(main_dp) -> None:
    await reset_database()
    server_doctor.reset_alert_clock_for_tests()
    admin = Chat(main_dp, ADMIN_TG_ID)

    await admin.say(main_texts.DOCTOR_BUTTON)
    assert "doctor_thr_open" in callbacks(admin.last_markup), callbacks(admin.last_markup)

    await admin.tap("doctor_thr_open")
    body = admin.last_edit_text
    flat = callbacks(admin.last_edit_markup)
    assert set(flat) >= {f"doctor_thr:{key}" for key in server_doctor.THRESHOLD_KEYS} | {"doctor_thr_reset", "doctor_refresh"}, flat
    assert all(len(value.encode("utf-8")) <= 64 for value in flat), flat
    for _key, (_default, _low, _high, _kind, label) in server_doctor.THRESHOLD_SPECS.items():
        assert label in body, (label, body)
    assert not any(char.isascii() and char.isdigit() for char in body), "ارقامِ جلالی در فهرستِ آستانه‌ها"
    assert "خودت" not in body and await _raw_column() is None, "هیچ آستانه‌ای عوض نشده ⇒ بی‌برچسب و ستونِ خالی"

    await admin.tap("doctor_thr:memory_percent")
    ask = admin.last_text
    assert "بینِ ۵۰ تا ۹۹" in ask, ask

    sent_before_invalid = len(admin.sent)
    await admin.say("۵۰۰")
    assert "قابلِ استفاده نیست" in admin.last_text, admin.last_text
    assert len(admin.sent) == sent_before_invalid + 1, "فقط پیامِ خطا، نه ذخیره"
    assert await _raw_column() is None, "بیرونِ کران ذخیره نمی‌شود"
    await admin.say("۸۰")
    saved = admin.sent[-2]["text"]
    assert "تنظیم شد" in saved and "۸۰" in saved and "رمِ سرور" in saved, saved
    assert "🧠 رمِ سرور: ۸۰٪ (خودت)" in admin.last_text, admin.last_text
    assert json.loads(await _raw_column()) == {"memory_percent": 80.0}, await _raw_column()
    async with session_scope() as session:
        limits = await server_doctor.thresholds(session)
    assert limits["memory_percent"] == 80.0 and limits["disk_percent"] == 85.0, limits
    audits = await _audit_details(AuditEventType.ADMIN_SETTING_CHANGED)
    assert any("رمِ سرور" in text and "۸۰" in text for text in audits), audits

    await admin.tap("doctor_thr_reset")
    assert await _raw_column() is None, "بازگشتِ همه ⇒ ستونِ خالی (نه صفرها)"
    assert "خودت" not in admin.last_edit_text, admin.last_edit_text
    assert any("بازگشت همهٔ آستانه" in text or "پیش‌فرضِ نسخه" in text for text in await _audit_details(AuditEventType.ADMIN_SETTING_CHANGED))

    edits_before = len(admin.edits)
    await admin.tap("doctor_thr:made_up")
    assert admin.last_toast["text"] == main_texts.DOCTOR_THRESH_STALE, admin.last_toast
    assert admin.last_toast.get("show_alert") is True, admin.last_toast
    assert len(admin.edits) == edits_before and await _raw_column() is None, "کلیدِ دست‌کاری‌شده چیزی نمی‌نویسد"
    print("PASS test_threshold_panel_flow")


async def test_cancel_and_operator_access(main_dp) -> None:
    await reset_database()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.tap("doctor_thr:log_errors")
    before_cancel = len(admin.sent)
    await admin.say("انصراف")
    assert admin.last_text == main_texts.OPERATION_CANCELLED, admin.last_text
    assert len(admin.sent) == before_cancel + 1
    after_cancel = len(admin.sent)
    await admin.say("۷")
    assert all("تنظیم شد" not in row["text"] for row in admin.sent[after_cancel:]), "بعد ازِ انصراف عددی ذخیره نمی‌شود"
    assert await _raw_column() is None

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(20, data="doctor_thr_open", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_callback_update(21, data="doctor_thr:log_errors", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(22, text="۷", user_id=OPERATOR_TG_ID))
    assert not bot.session.sent_messages and not bot.session.edited_texts, "فقط سوپرادمین"
    await bot.session.close()
    assert await _raw_column() is None
    print("PASS test_cancel_and_operator_access")


# ============================================================================= ۶ — inspect همان‌ها را مصرف می‌کند
async def test_inspect_reads_stored_thresholds() -> None:
    await reset_database()
    observability.reset_recent_logs_for_tests()
    observability.reset_counters()
    server_doctor.reset_alert_clock_for_tests()
    observability._recent_buffer.rows.append(  # noqa: SLF001
        {"t": "11-14 10:00:00", "level": "ERROR", "where": "app.test", "msg": "خطایِ ساختگیِ تستِ پ۷۲", "exc": ""}
    )
    async with session_scope() as session:
        default_keys = _keys(await server_doctor.inspect(session))
    assert "log_errors" not in default_keys, "یکِ ERROR با آستانهٔ ۵ پیدا نمی‌شود"

    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        row.doctor_thresholds = server_doctor.dump_thresholds({**_LIM, "log_errors": 1.0})
        await session.commit()
    async with session_scope() as session:
        lowered_keys = _keys(await server_doctor.inspect(session))
    assert "log_errors" in lowered_keys, "همان بازرسی با آستانهٔ ۱ ⇒ پیدا می‌شود"
    print("PASS test_inspect_reads_stored_thresholds")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    test_specs_are_self_consistent()
    test_threshold_serialisation_is_defensive()
    test_admin_input_parsing()
    test_window_deltas_labels_and_guards()
    test_verdict_follows_the_stored_threshold()
    await test_threshold_panel_flow(main_dp)
    await test_cancel_and_operator_access(main_dp)
    await test_inspect_reads_stored_thresholds()
    print("📊 نتیجه: ۸ تستِ پ۷۲ (آستانه‌هایِ عیب‌یاب + پنجرهٔ زمانی) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
