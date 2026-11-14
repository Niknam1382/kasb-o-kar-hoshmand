"""پ۶۲ · خواستهٔ مالکِ محصول: ایجنتِ عملیاتیِ سرور (لاگ → تشخیص → پیشنهاد).

پوششِ داده‌شده:
۱. قوانینِ آستانه **فقط** بالایِ خطِ خودشان شعله می‌شوند (دیسک/رم/بار/استخرِ دیتابیس/فشارِ AI)،
   استخرِ کلیدِ خالی ⇒ خطایِ قرمز، و اگر `/proc` خوانده نشود «صفر» گزارش نمی‌شود بلکه صریح
   «خوانده نشد» می‌آید.
۲. قوانینِ شمارنده‌ها و لاگ: رد شدنِ وب‌هوک، سقفِ نرخ، ردِ برداشتِ کیف‌پول، خطاهایِ شبکهٔ
   تلگرام/بله (از پیام و استک‌تریس)، شکستِ پیاپیِ کلیدِ AI و شمارِ خطاهایِ ERROR در بافر.
۳. `inspect`: فقط‌خواندنی — یکِ `SELECT` رویِ استخرِ کلیدها، بی‌هیچ نوشتنی جزِ ساختِ خودِ ردیفِ
   تنظیمات (که پ۷۲ برایِ آستانه‌ها می‌خواندش)، و عددِ زندهٔ همان پنلِ ظرفیت (نه نسخهٔ دومِ حقیقت).
۴. `run`: خنک‌کردنِ یک‌ساعته برایِ هرِ یافته (دوباره‌ارسال نمی‌شود)، ارسالِ خلاصه به ادمین‌ها،
   بی‌ارسال وقتی هیچ موردی نیست، و بی‌سقوط اگر ارسالِ تلگرام خطا داد.
۵. صفحهٔ پنل: دکمه ⇒ یکِ پیام با سرِصفحهٔ جلالی، شمارشِ شدت‌ها و یادداشتِ «هیچ اقدامی نمی‌کند»؛
   «تازه‌سازیِ بازرسی» ⇒ یکِ ویرایش و دقیقاً یکِ پاسخِ کال‌بک.
۶. دروازهٔ جاب («doctor» در `job_gate_service.GROUPS`) ⇒ ادمین می‌تواند هشدارهایِ دوره‌ای را
   خاموش کند؛ دسترسی: اپراتور ⇒ صفر پیام و صفر ویرایش؛ دکمه در `_KNOWN_MENU_BUTTONS` و فقط در
   کیبوردِ سوپرادمین.

اجرا: python3 tests_manual/run_one.py test_p62_server_doctor.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import event, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402

from app import observability  # noqa: E402
from app.bots.main_bot import keyboards, router as main_router, texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import AiApiKeyPoolEntry, AiKeyCapability  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import admin_role_service, admin_settings_service, ai_service, job_gate_service, server_doctor  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 997766
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P62_TESTING"
UTC = dt.timezone.utc


@contextlib.contextmanager
def _counted():
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


def _system(disk=None, memory=None, load_percent=None, cores=4) -> dict:
    return {
        "cores": cores, "load1": None, "load_percent": load_percent,
        "memory_used_percent": memory, "disk_used_percent": disk, "disk_label": "بکاپ‌ها",
    }


def _db(percent=10.0, checked_out=1, capacity=10, overflow=0) -> dict:
    return {"size": capacity, "checked_out": checked_out, "overflow": overflow, "capacity": capacity, "percent": percent}


def _ai(keys=True, percent=0.0, inflight=0, usable=20, bottleneck="keys", sum_caps=20, ceiling=40) -> dict:
    return {
        "keys": [object()] if keys else [], "sum_caps": sum_caps, "platform_ceiling": ceiling,
        "usable": usable, "inflight_total": inflight, "percent": percent, "bottleneck": bottleneck,
        "voice": {"count": 0, "sum_caps": 0, "inflight": 0},
    }


def _keys(findings) -> set[str]:
    return {finding.key for finding in findings}


def _log_rows(*rows: tuple[str, str, str]) -> None:
    """ردیفِ خام داخلِ بافرِ لاگ می‌گذارد (همان شکلِ RecentLogBuffer)."""
    observability.reset_recent_logs_for_tests()
    observability._recent_buffer.rows.extend(  # noqa: SLF001
        {"t": "11-12 10:00:00", "level": level, "where": "ai_service", "msg": msg, "exc": exc}
        for (level, msg, exc) in rows
    )


_LIM = server_doctor.defaults()  # پ۷۲: توابعِ تشخیص حالا آستانه می‌گیرند (پیش‌فرض = عددِ پ۶۲)


async def test_threshold_rules_fire_only_past_the_line() -> None:
    assert _keys(server_doctor._thresholds(_system(disk=80.0), _db(), _ai(), _LIM)) == {"proc"}  # noqa: SLF001
    findings = server_doctor._thresholds(  # noqa: SLF001
        _system(disk=90.0, memory=95.0, load_percent=200.0), _db(percent=95.0), _ai(percent=90.0, inflight=18, usable=20), _LIM
    )
    keys = _keys(findings)
    assert {"disk", "memory", "load", "db_pool", "ai_pressure"} <= keys, keys
    by_key = {finding.key: finding for finding in findings}
    assert by_key["disk"].severity == server_doctor.ERROR
    assert by_key["memory"].severity == server_doctor.WARN
    assert "٪۹۰" in by_key["disk"].detail or "۹۰٪" in by_key["disk"].detail, by_key["disk"].detail
    assert "گلوگاه" in by_key["ai_pressure"].detail
    assert "استخرِ کلیدهایِ AI" in by_key["ai_pressure"].suggestion, "پیشنهاد باید بگوید کجا اقدام شود"
    # استخرِ خالی ⇒ قرمز، و «فشار» نمی‌گوید (چون چیزی برایِ پر شدن نیست)
    empty = server_doctor._thresholds(_system(), _db(), _ai(keys=False, usable=0, sum_caps=0), _LIM)  # noqa: SLF001
    assert _keys(empty) == {"ai_keys", "proc"}, _keys(empty)
    assert [f.severity for f in empty if f.key == "ai_keys"][0] == server_doctor.ERROR
    # آستانه‌ها مرزِ بازه‌اند: دقیقاً رویِ خط هم شعله می‌شود (نه یکِ واحد بالاتر)
    assert "disk" in _keys(server_doctor._thresholds(_system(disk=server_doctor.DISK_ALERT_PERCENT), _db(), _ai(), _LIM))  # noqa: SLF001
    print("PASS test_threshold_rules_fire_only_past_the_line")


async def test_counter_and_log_rules() -> None:
    findings = server_doctor._counter_findings({  # noqa: SLF001
        "webhook.rejected": 25, "webhook.rate_limited": 60, "wallet.deduct_denied": 7,
    }, _LIM, "از شروعِ این پروسه")
    assert _keys(findings) == {"webhook_rejected", "webhook_rate_limited", "wallet_denied"}, _keys(findings)
    quiet = server_doctor._counter_findings({"webhook.rejected": 1, "webhook.rate_limited": 2, "wallet.deduct_denied": 1}, _LIM, "از شروعِ این پروسه")  # noqa: SLF001
    assert quiet == [], quiet

    _log_rows(
        ("ERROR", "پاسخِ کلیدِ AI نگرفته شد · توکن=123●●●●", ""),
        ("ERROR", "TelegramNetworkError", "httpx.ConnectError: [Errno -1] no address associated with hostname"),
        ("WARNING", "یه کلیدِ AI در استخر شکست خورد", ""),
        ("WARNING", "صفِ درخواست‌هایِ اینِ کلیدِ AI شلوغ بود (سقفِ آن: ۵).", ""),
    )
    rows = observability.recent_logs(view="warnings", limit=300)
    assert server_doctor._log_matches(rows, server_doctor._AI_FAILURE_MARKERS) == 3, rows  # noqa: SLF001
    assert server_doctor._log_matches(rows, server_doctor._TELEGRAM_MARKERS) == 1, "خطا از استک‌تریس هم گرفته می‌شود"
    logged = server_doctor._log_findings(3, 1, 1, _LIM)  # noqa: SLF001
    assert _keys(logged) == {"telegram_network", "ai_failures"}, _keys(logged)
    assert _keys(server_doctor._log_findings(1, 0, 9, _LIM)) == {"log_errors"}  # noqa: SLF001
    print("PASS test_counter_and_log_rules")


async def test_inspect_is_read_only_and_uses_live_numbers() -> None:
    original = settings.ai_max_concurrent_calls
    settings.ai_max_concurrent_calls = 2
    try:
        await reset_database()
        ai_service.reset_pool_state_for_tests()
        observability.reset_recent_logs_for_tests()
        observability.reset_counters()
        async with session_scope() as session:
            with _counted() as seen:
                findings = await server_doctor.inspect(session)
        assert _keys(findings) >= {"ai_keys"}, _keys(findings)
        # پ۷۲: عیب‌یاب اول آستانه‌ها را از `admin_settings` می‌خواند و اولینِ خواندنِ دیتابیسِ تازه
        # همان ردیف را می‌سازد (INSERTِ سطرِ تنظیمات، نه نوشتنِ یافته). جزِ آن، هیچ نوشتنی مجاز نیست.
        writes = [s for s in seen if s.upper().startswith(("INSERT", "UPDATE", "DELETE"))]
        assert all(w.upper().startswith("INSERT INTO ADMIN_SETTINGS") for w in writes), writes
        pool_reads = [s for s in seen if "ai_api_key_pool" in s]
        assert len(pool_reads) == 1, "کوئریِ استخرِ کلیدها همان یکی است که پنلِ ظرفیت می‌زند"

        async with session_scope() as session:
            session.add(
                AiApiKeyPoolEntry(
                    label="کلیدِ پرمصرف", api_key="k", model="m", base_url="https://example.test/v1",
                    capability=AiKeyCapability.CHAT, is_active=True, max_concurrent=1,
                )
            )
        async with session_scope() as session:
            entry_id = (await session.execute(select(AiApiKeyPoolEntry.id))).scalars().one()
        ai_service.slots_for(entry_id).inflight = 1
        async with session_scope() as session:
            findings = await server_doctor.inspect(session)
        keys = _keys(findings)
        assert "ai_pressure" in keys and "ai_keys" not in keys, keys
        pressure = [f for f in findings if f.key == "ai_pressure"][0]
        assert "۱۰۰٪" in pressure.detail, pressure.detail
    finally:
        settings.ai_max_concurrent_calls = original
    print("PASS test_inspect_is_read_only_and_uses_live_numbers")


async def test_run_cooldown_and_recipients() -> None:
    await reset_database()
    ai_service.reset_pool_state_for_tests()
    server_doctor.reset_alert_clock_for_tests()
    observability.reset_recent_logs_for_tests()
    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    try:
        async with session_scope() as session:
            first = await server_doctor.run(session, bot)
        assert first["findings"] >= 1 and first["sent"] == len(settings.admin_ids), first
        bodies = [row["text"] for row in bot.session.sent_messages]
        assert bodies and bodies[0].startswith("🩺 عیب‌یابِ سرور:"), bodies
        assert "موردِ تازه" in bodies[0] and "🔴" in bodies[0], bodies[0]
        assert not any(char.isascii() and char.isdigit() for char in bodies[0]), "ارقامِ جلالی در هشدار"

        async with session_scope() as session:
            second = await server_doctor.run(session, bot)
        assert second["sent"] == 0 and second["findings"] >= 1, "خنک‌کردنِ یک‌ساعته: دوباره‌ارسال نیست"
        assert len(bot.session.sent_messages) == len(bodies)

        server_doctor.reset_alert_clock_for_tests()
        async with session_scope() as session:
            third = await server_doctor.run(session, bot)
        assert third["sent"] == len(settings.admin_ids), "بعد ازِ مهلت، همان یافته دوباره هشدار می‌گیرد"

        # بی‌مورد ⇒ بی‌پیام (قوانینِ آستانه/لاگ/شمارنده را موقتاً «همه‌چیز درست» می‌کنیم)
        original = (server_doctor._thresholds, server_doctor._log_findings, server_doctor._counter_findings)  # noqa: SLF001
        server_doctor._thresholds = lambda *args: []  # noqa: SLF001
        server_doctor._log_findings = lambda *args: []  # noqa: SLF001
        server_doctor._counter_findings = lambda *args: []  # noqa: SLF001
        server_doctor.reset_alert_clock_for_tests()
        try:
            sent_before = len(bot.session.sent_messages)
            async with session_scope() as session:
                clean = await server_doctor.run(session, bot)
        finally:
            (server_doctor._thresholds, server_doctor._log_findings, server_doctor._counter_findings) = original  # noqa: SLF001
        assert clean["findings"] == 0 and clean["sent"] == 0, clean
        assert len(bot.session.sent_messages) == sent_before, "هیچ هشدارِ بی‌موردی فرستاده نمی‌شود"

        # ارسالِ خرابِ تلگرام نباید جاب را بیندازد
        class _BrokenSession(FakeSession):
            async def make_request(self, *args, **kwargs):
                raise RuntimeError("TelegramNetworkError")

        broken = Bot(token=MAIN_TOKEN, session=_BrokenSession())
        server_doctor.reset_alert_clock_for_tests()
        async with session_scope() as session:
            survived = await server_doctor.run(session, broken)
        assert survived["sent"] == 0 and survived["findings"] >= 1, survived
        await broken.session.close()
    finally:
        await bot.session.close()
    print("PASS test_run_cooldown_and_recipients")


async def _doctor_gate_state() -> bool:
    async with session_scope() as session:
        admin_settings = await admin_settings_service.get_admin_settings(session)
    return job_gate_service.is_paused(admin_settings, "doctor")


def test_ready_to_alert_treats_never_alerted_as_fresh() -> None:
    """پ۶۵: «هنوز هشدار نشده» باید None باشد، نه `0.0`.

    `time.monotonic()` از مبدأِ دلخواهِ سیستم‌عامل می‌آید و رویِ ماشین/VMِ تازه‌روشن خودش از
    `ALERT_COOLDOWN_SECONDS` کوچک‌تر است؛ با sentinelِ صفری اولین هشدارِ هرِ بوت بی‌صدا خفه می‌شد
    (همین را سوئیتِ کاملِ پ۶۵ گرفتش: `sent == 0` رویِ اجرایِ اول).
    """
    finding = server_doctor.Finding(key="disk", severity="warn", title="عنوان", detail="جزئیات", suggestion="پیشنهاد")
    real_time = server_doctor.time
    server_doctor.time = type("_Clock", (), {"monotonic": staticmethod(lambda: 5.0)})
    try:
        server_doctor.reset_alert_clock_for_tests()
        assert [item.key for item in server_doctor._ready_to_alert([finding])] == ["disk"], "اجرایِ اول باید هشدار بدهد"
        assert server_doctor._ready_to_alert([finding]) == [], "دوباره داخلِ خنک‌کردنِ یک‌ساعته است"
    finally:
        server_doctor.time = real_time
    print("PASS test_ready_to_alert_treats_never_alerted_as_fresh")


async def test_job_gate_has_the_doctor_group() -> None:
    await reset_database()
    assert "doctor" in job_gate_service.GROUPS
    assert await _doctor_gate_state() is False, "پیش‌فرض روشن است (خواستهٔ مالک: ایجنت در حالِ کار)"
    async with session_scope() as session:
        now_paused = await job_gate_service.toggle_group(session, "doctor", by=f"telegram:{ADMIN_TG_ID}")
    assert now_paused is True
    admin_settings_service.reset_read_cache()
    assert await _doctor_gate_state() is True, "جابِ عیب‌یابی از همان دروازهٔ همیشگی خاموش می‌شود"
    async with session_scope() as session:
        assert await job_gate_service.toggle_group(session, "doctor", by=f"telegram:{ADMIN_TG_ID}") is False
    admin_settings_service.reset_read_cache()
    assert await _doctor_gate_state() is False
    print("PASS test_job_gate_has_the_doctor_group")


async def test_doctor_screen(main_dp) -> None:
    await reset_database()
    ai_service.reset_pool_state_for_tests()
    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.DOCTOR_BUTTON)
    assert len(admin.sent) == 1, admin.sent
    body = admin.last_text
    assert body.startswith("🩺 عیب‌یابِ سرور — "), body
    assert "🔴" in body and "استخرِ کلیدهایِ AI" in body, body
    assert "فقط تشخیص می‌دهد و هیچ چیزی را عوض نمی‌کند" in body, body
    assert not any(char.isascii() and char.isdigit() for char in body), "سرِصفحهٔ جلالی"
    flat = callbacks(admin.last_markup)
    assert "doctor_refresh" in flat and "capacity_refresh" in flat and "main_menu" in flat, flat
    assert all(len(value.encode("utf-8")) <= 64 for value in flat), flat
    labels = [b.text for row in admin.last_markup.inline_keyboard for b in row]
    assert main_texts.CAPACITY_REFRESH not in labels, labels
    assert labels.count(main_texts.DOCTOR_REFRESH) == 1 and main_texts.CAPACITY_BUTTON in labels, (
        "پ۷۰: رویِ صفحهٔ عیب‌یاب فقط یکِ «تازه‌سازی» هست و آن هم بازرسی است؛ دکمهٔ دوم نامِ پنلِ ظرفیت را دارد"
    )

    answers_before = len(admin.session.answered_callbacks)
    await admin.tap("doctor_refresh")
    assert len(admin.edits) == 1, admin.edits
    assert "🩺 عیب‌یابِ سرور" in admin.last_edit_text, admin.last_edit_text
    assert len(admin.session.answered_callbacks) == answers_before + 1, "دقیقاً یکِ پاسخِ کال‌بک"
    print("PASS test_doctor_screen")


async def test_access_and_menu(main_dp) -> None:
    await reset_database()
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)
    operator_labels = [button.text for row in keyboards.admin_panel_keyboard(False).keyboard for button in row]
    super_labels = [button.text for row in keyboards.admin_panel_keyboard(True).keyboard for button in row]
    assert main_texts.DOCTOR_BUTTON not in operator_labels, "دکمه فقط در کیبوردِ سوپرادمین"
    assert main_texts.DOCTOR_BUTTON in super_labels
    assert main_texts.DOCTOR_BUTTON in main_router._KNOWN_MENU_BUTTONS

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(10, data="doctor_refresh", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(11, text=main_texts.DOCTOR_BUTTON, user_id=OPERATOR_TG_ID))
    assert not bot.session.sent_messages and not bot.session.edited_texts, "فقط سوپرادمین"
    await bot.session.close()
    print("PASS test_access_and_menu")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_threshold_rules_fire_only_past_the_line()
    await test_counter_and_log_rules()
    await test_inspect_is_read_only_and_uses_live_numbers()
    await test_run_cooldown_and_recipients()
    test_ready_to_alert_treats_never_alerted_as_fresh()
    await test_job_gate_has_the_doctor_group()
    await test_doctor_screen(main_dp)
    await test_access_and_menu(main_dp)
    print("📊 نتیجه: ۸ تستِ پ۶۲ (ایجنتِ عیب‌یابیِ سرور) پاس شد · قوانین/لاگ/فقط‌خواندنی/خنک‌کردن/مبدأِ clock/دروازه/پنل/دسترسی")


if __name__ == "__main__":
    asyncio.run(main())
