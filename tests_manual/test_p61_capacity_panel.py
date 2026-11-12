"""پ۶۱ · خواستهٔ مالکِ محصول: پنلِ «📡 ظرفیت و فشارِ سرور» در پنلِ ادمین (فقط سوپرادمین).

پوششِ داده‌شده:
۱. `capacity_service.ai_lines`: سقفِ هرِ کلید **همان** فرمولِ governor است (کلیدِ بی‌عدد = سهمِ
   مساوی از سقفِ پلتفرم)، بارِ هرِ کلید از شمارندهٔ زنده می‌آید نه تخمین، و «گلوگاهِ فعلی» در دو
   حالتِ «جمعِ سقفِ کلیدها» و «سقفِ پلتفرم» درست تشخیص داده می‌شود؛ کلیدِ غیرفعال شمرده نمی‌شود.
۲. استخرِ خالی ⇒ «ظرفیتِ قابلِ استفاده» صفر و پیامِ روشن، نه تقسیمِ بر صفر و نه درصدِ ساختگی.
۳. `system_lines` و `db_pool_lines` و `counters_lines`: صفر جملهٔ SQL، درصدها هیچ‌وقت بالایِ صد،
   هسته‌ها حداقل یکی، و برچسبِ فارسی برایِ شمارنده‌هایِ شناخته‌شده (شمارندهٔ ناشناخته با نامِ
   خودش می‌ماند تا چیزی پنهان نشود).
۴. مسیرِ واقعیِ پنل: دکمه ⇒ یکِ پیام با هر سه ستون + ارقامِ جلالی + یادداشتِ صریحِ «سقفِ واقعیِ
   ارائه‌دهنده سنجیده نشده»؛ «🔄 تازه‌سازی» ⇒ یکِ ویرایش و دقیقاً یکِ پاسخِ کال‌بک (نه دو تا).
۵. دسترسی: ادمینِ عملیاتی ⇒ صفر پیام و صفر ویرایش؛ دکمه فقط در کیبوردِ سوپرادمین، ثبت‌شده در
   `_KNOWN_MENU_BUTTONS`، و `callback_data` زیرِ ۶۴ بایت.

اجرا: python3 tests_manual/run_one.py test_p61_capacity_panel.py
"""
from __future__ import annotations

import asyncio
import contextlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from aiogram import Bot  # noqa: E402
from sqlalchemy import event, select  # noqa: E402

from harness import FakeSession, build_test_dispatchers, make_callback_update, make_message_update, reset_database  # noqa: E402
from phase4_helpers import Chat, callbacks  # noqa: E402

from app.bots.main_bot import keyboards, router as main_router, texts as main_texts  # noqa: E402
from app.config import settings  # noqa: E402
from app.database.models import AiApiKeyPoolEntry, AiKeyCapability  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app import observability  # noqa: E402
from app.services import admin_role_service, ai_service, capacity_service  # noqa: E402

ADMIN_TG_ID = 12345
OPERATOR_TG_ID = 998877
MAIN_TOKEN = "550000:FAKE_MAIN_BOT_TOKEN_FOR_P61_TESTING"


@contextlib.contextmanager
def _counted():
    """شمارندهٔ جمله رویِ همان engine (الگویِ test_p31/p55؛ شمارندهٔ کلاس‌ای نه)."""
    seen: list[str] = []

    def _listener(_conn, _cursor, statement, _params, _context, _executemany):
        seen.append(" ".join(statement.split()))

    event.listen(engine.sync_engine, "before_cursor_execute", _listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _listener)


async def _set_pool(*specs: tuple) -> None:
    """استخرِ کلیدها را دقیقاً به همان فهرستِ (برچسب، سقفِ خودِ کلید، فعال، قابلیت) می‌رساند."""
    await reset_database()
    ai_service.reset_pool_state_for_tests()
    observability.reset_counters()
    if not specs:
        return
    async with session_scope() as session:
        session.add_all(
            [
                AiApiKeyPoolEntry(
                    label=spec[0], api_key="کلیدِ-آزمایشی", model="m", base_url="https://example.test/v1",
                    capability=AiKeyCapability.STT if len(spec) > 3 and spec[3] == "stt" else AiKeyCapability.CHAT,
                    is_active=spec[2], max_concurrent=spec[1],
                )
                for spec in specs
            ]
        )


async def _pool_ids() -> list[int]:
    async with session_scope() as session:
        return list((await session.execute(select(AiApiKeyPoolEntry.id).order_by(AiApiKeyPoolEntry.id))).scalars().all())


async def test_ai_lines_mirror_the_governor() -> None:
    original = settings.ai_max_concurrent_calls
    settings.ai_max_concurrent_calls = 40
    try:
        await _set_pool(
            ("کلیدِ اول", 3, True), ("کلیدِ دوم", None, True),
            ("کلیدِ خاموش", 99, False), ("کلیدِ صوت", 9, True, "stt"),
        )
        ids = await _pool_ids()
        ai_service.slots_for(ids[0]).inflight = 2
        ai_service.slots_for(ids[1]).inflight = 5
        ai_service.slots_for(ids[3]).inflight = 1
        async with session_scope() as session:
            ai = await capacity_service.ai_lines(session)
        assert [load.label for load in ai["keys"]] == ["کلیدِ اول", "کلیدِ دوم"], "کلیدِ خاموش و کلیدِ صوت در فهرستِ پاسخ نیستند"
        # سهمِ مساویِ کلیدِ بی‌عدد: ceil(40 / ۲ کلیدِ چت) = ۲۰ — همان چیزی که governor اعمال می‌کند
        assert [load.cap for load in ai["keys"]] == [3, 20], [load.cap for load in ai["keys"]]
        assert [load.inflight for load in ai["keys"]] == [2, 5], "بارِ زنده، نه تخمین"
        assert ai["sum_caps"] == 23 and ai["usable"] == 23
        assert ai["platform_ceiling"] == 40 and ai["bottleneck"] == "keys"
        assert ai["inflight_total"] == 7 and abs(ai["percent"] - 7 / 23 * 100) < 1e-9
        assert abs(ai["keys"][0].percent - 2 / 3 * 100) < 1e-9
        # استخرِ صوت جداست: نه در ظرفیتِ پاسخِ مشتری شمرده می‌شود، نه گم می‌شود
        assert ai["voice"] == {"count": 1, "sum_caps": 9, "inflight": 1}, ai["voice"]
    finally:
        settings.ai_max_concurrent_calls = original
    print("PASS test_ai_lines_mirror_the_governor")


async def test_platform_ceiling_and_empty_pool() -> None:
    original = settings.ai_max_concurrent_calls
    settings.ai_max_concurrent_calls = 40
    try:
        await _set_pool()
        async with session_scope() as session:
            empty = await capacity_service.ai_lines(session)
        assert empty["keys"] == [] and empty["sum_caps"] == 0 and empty["usable"] == 0
        assert empty["percent"] == 0.0, "بی‌کلید ⇒ صفرِ ساختگی نه تقسیمِ بر صفر"
        await _set_pool(("کلیدِ پهن", 500, True))
        async with session_scope() as session:
            wide = await capacity_service.ai_lines(session)
        assert wide["sum_caps"] == 500 and wide["usable"] == 40
        assert wide["bottleneck"] == "platform", "سقفِ پلتفرم گلوگاه است، نه کلید"
    finally:
        settings.ai_max_concurrent_calls = original
    print("PASS test_platform_ceiling_and_empty_pool")


async def test_reads_use_no_sql_and_stay_in_range() -> None:
    await _set_pool(("کلیدِ اول", 5, True))
    with _counted() as seen:
        system = capacity_service.system_lines()
        db = capacity_service.db_pool_lines()
        counters = capacity_service.counters_lines()
    assert not seen, f"این سه خواندن نباید هیچ جملهٔ SQL بسازد: {seen}"
    assert system["cores"] >= 1
    assert system["load_percent"] is None or system["load_percent"] >= 0.0, "بارِ میانگین می‌تواند بالایِ صد باشد"
    for name in ("memory_used_percent", "disk_used_percent"):
        assert system[name] is None or 0.0 <= system[name] <= 100.0, (name, system[name])
    assert 0.0 <= db["percent"] <= 100.0 and db["capacity"] >= 1, db
    assert isinstance(counters, list) and all(isinstance(label, str) and label for label, _value in counters)
    print("PASS test_reads_use_no_sql_and_stay_in_range")


async def test_counter_labels_are_persian() -> None:
    await _set_pool()
    observability.count("webhook.main", 3)
    observability.count("wallet.deduct", 1500)
    observability.count("ai.foo", 1)
    observability.count("internal.noise", 9)
    rows = capacity_service.counters_lines()
    labels = dict(rows)
    assert labels.get("رویدادِ رباتِ مرکزی") == 3, rows
    assert labels.get("برداشتِ کیف‌پول (تومان)") == 1500, rows
    assert labels.get("ai.foo") == 1, "برچسبِ ناشناخته با نامِ فنی می‌ماند تا چیزی پنهان نشود"
    assert all("internal.noise" not in label for label, _value in rows), "شمارندهٔ بی‌ربط فهرست را شلوغ نمی‌کند"
    print("PASS test_counter_labels_are_persian")


async def test_capacity_screen(main_dp) -> None:
    original = settings.ai_max_concurrent_calls
    settings.ai_max_concurrent_calls = 40
    try:
        await _set_pool(("کلیدِ اول", 3, True), ("کلیدِ دوم", None, True), ("کلیدِ صوت", 9, True, "stt"))
        ids = await _pool_ids()
        ai_service.slots_for(ids[0]).inflight = 1
        observability.count("webhook.main", 4)
        admin = Chat(main_dp, ADMIN_TG_ID)
        await admin.say(main_texts.CAPACITY_BUTTON)
        assert len(admin.sent) == 1, admin.sent
        body = admin.last_text
        assert body.startswith("📡 ظرفیت و فشارِ سرور"), body
        for part in ("🤖 پاسخِ مشتری", "🗄 دیتابیس", "🖥 سرور", "📚 شمارنده‌ها", "٪"):
            assert part in body, (part, body)
        assert "کلیدِ اول: ۱ از ۳" in body, body
        assert "🎙 صوت — ۱ کلید · ۰ درخواستِ در حالِ اجرا از ۹" in body, body
        assert "گلوگاهِ فعلی: جمعِ سقفِ کلیدها" in body, body
        assert "رویدادِ رباتِ مرکزی: ۴" in body, body
        assert "سقفِ واقعیِ سرویسِ ارائه‌دهندهٔ هوشِ مصنوعی هنوز سنجیده نشده" in body, "یادداشتِ صریحِ NOT RUN"
        assert not any(char.isascii() and char.isdigit() for char in body), "ارقامِ جلالی در همهٔ صفحه"
        flat = callbacks(admin.last_markup)
        assert "capacity_refresh" in flat and "main_menu" in flat, flat

        answers_before = len(admin.session.answered_callbacks)
        await admin.tap("capacity_refresh")
        assert len(admin.edits) == 1, admin.edits
        assert body.splitlines()[0] in admin.last_edit_text, admin.last_edit_text
        assert len(admin.session.answered_callbacks) == answers_before + 1, "دقیقاً یکِ پاسخِ کال‌بک"
        # استخرِ خالی هم صفحه را نمی‌شکند: همان هدر + پیامِ روشن، بدونِ «گلوگاه»
        await _set_pool()
        await admin.tap("capacity_refresh")
        assert main_texts.CAPACITY_NO_KEYS in admin.last_edit_text, admin.last_edit_text
        assert "گلوگاهِ فعلی" not in admin.last_edit_text
    finally:
        settings.ai_max_concurrent_calls = original
    print("PASS test_capacity_screen")


async def test_access_and_menu(main_dp) -> None:
    await _set_pool(("کلیدِ اول", 3, True))
    async with session_scope() as session:
        await admin_role_service.grant_operator(session, OPERATOR_TG_ID, granted_by_telegram_id=ADMIN_TG_ID)

    operator_labels = [button.text for row in keyboards.admin_panel_keyboard(False).keyboard for button in row]
    super_labels = [button.text for row in keyboards.admin_panel_keyboard(True).keyboard for button in row]
    assert main_texts.CAPACITY_BUTTON not in operator_labels, "دکمه فقط در کیبوردِ سوپرادمین"
    assert main_texts.CAPACITY_BUTTON in super_labels
    assert main_texts.CAPACITY_BUTTON in main_router._KNOWN_MENU_BUTTONS, "وسطِ FSM هم escape شود"
    assert len("capacity_refresh".encode("utf-8")) <= 64

    bot = Bot(token=MAIN_TOKEN, session=FakeSession())
    await main_dp.feed_update(bot, make_callback_update(10, data="capacity_refresh", user_id=OPERATOR_TG_ID))
    await main_dp.feed_update(bot, make_message_update(11, text=main_texts.CAPACITY_BUTTON, user_id=OPERATOR_TG_ID))
    assert not bot.session.sent_messages and not bot.session.edited_texts, "فقط سوپرادمین"
    await bot.session.close()

    admin = Chat(main_dp, ADMIN_TG_ID)
    await admin.say(main_texts.CAPACITY_BUTTON)
    assert admin.sent, "سوپرادمین همان صفحه را می‌بیند"
    print("PASS test_access_and_menu")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, _main_bot = build_test_dispatchers()
    await test_ai_lines_mirror_the_governor()
    await test_platform_ceiling_and_empty_pool()
    await test_reads_use_no_sql_and_stay_in_range()
    await test_counter_labels_are_persian()
    await test_capacity_screen(main_dp)
    await test_access_and_menu(main_dp)
    print("📊 نتیجه: ۶ تستِ پ۶۱ (پنلِ ظرفیتِ AI و فشارِ سرور) پاس شد · زنده/بدونِ SQL/جلالی/دسترسی")


if __name__ == "__main__":
    asyncio.run(main())
