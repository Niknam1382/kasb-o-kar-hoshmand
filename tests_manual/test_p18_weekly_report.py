"""
تست: P18 · B5 — گزارشِ دوره‌ای سرِ وقتِ درست.

پیش از این مبنا «N روز از آخرین ارسال» بود و چون جاب هر ۳۰ دقیقه چک می‌کرد، لحظه‌یِ ارسال هر هفته
کمی جابه‌جا می‌شد و مبنایش هم UTC بود. حالا: روزِ هفته + ساعتِ *هر فروشگاه*، به وقتِ تهران، و
دقیقاً یک‌بار در هر بازه‌یِ هفتگی.

پوشش:
۱. تابع‌هایِ خالص: تبدیلِ هفته‌یِ ایرانی به weekdayِ پایتون و محاسبه‌یِ آغازِ بازه.
۲. قبل از ساعتِ تنظیم‌شده چیزی نمی‌رود؛ سرِ ساعت یک‌بار می‌رود؛ تیکِ ۳۰ دقیقه‌یِ بعد و روزهایِ بعدِ
   همان هفته دوباره نمی‌فرستد؛ هفته‌یِ بعد سرِ همان ساعت می‌رود.
۳. مبنا واقعاً تهران است نه UTC (ساعتِ ۲۳ِ جمعه‌یِ تهران ≠ ۲۳ِ UTC).
۴. سوییچِ خاموش ⇒ هیچ.
۵. توقفِ زمان (K3/K4): فریزِ سراسری ⇒ هیچ؛ فریزِ تک‌فروشگاه‌دار ⇒ فقط او رد می‌شود.
۶. مسیرِ پنلِ فروشگاه‌دار: روزِ هفته، ساعتِ پیش‌فرض/دلخواه، ردِّ عددِ نامعتبر، روشن/خاموش، برگشت.

اجرا: python3 tests_manual/test_p18_weekly_report.py
"""
from __future__ import annotations

import asyncio
import datetime
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from harness import build_test_dispatchers, reset_database  # noqa: E402
from phase4_helpers import Chat  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.bots.main_bot import texts  # noqa: E402
from app.database.models import ShopBot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import report_service, shop_bot_service, time_freeze_service  # noqa: E402
from app.utils.jalali import TEHRAN_TZ, to_tehran  # noqa: E402
from sqlalchemy import select, update  # noqa: E402

OWNER_TG_ID = 999_811
SHOP_BOT_TG_ID = 999_812
OTHER_OWNER_TG_ID = 999_821
OTHER_SHOP_BOT_TG_ID = 999_822

UTC = datetime.timezone.utc
# ۲۰۲۶-۰۱-۰۳ یک شنبه‌یِ میلادی است (= شنبه‌یِ هفته‌یِ ایرانی).
SATURDAY = datetime.datetime(2026, 1, 3, tzinfo=UTC)


def _utc(year, month, day, hour=0, minute=0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, tzinfo=UTC)


def _tehran(year, month, day, hour, minute=0) -> datetime.datetime:
    return datetime.datetime(year, month, day, hour, minute, tzinfo=TEHRAN_TZ).astimezone(UTC)


async def _set_schedule(shop_bot_id: int, *, weekday: int, hour: int, enabled: bool = True, last_sent=None) -> None:
    async with session_scope() as session:
        await session.execute(
            update(ShopBot)
            .where(ShopBot.id == shop_bot_id)
            .values(
                weekly_report_weekday=weekday,
                weekly_report_hour=hour,
                weekly_report_enabled=enabled,
                last_report_sent_at=last_sent,
            )
        )


# ============================================================================= ۱ — تابع‌هایِ خالص
def test_weekday_conversion_and_window_pure() -> None:
    to_py = report_service.persian_weekday_to_python
    # ۰=شنبه … ۶=جمعه ← weekdayِ پایتون (۰=دوشنبه؛ شنبه=۵)
    assert [to_py(i) for i in range(7)] == [5, 6, 0, 1, 2, 3, 4]
    assert to_py(0) == SATURDAY.weekday(), "شنبه باید با یک شنبه‌یِ واقعی مطابقت کند"

    start = report_service.latest_window_start
    # شنبه ۰۹:۰۰ تهران = شنبه ۰۵:۳۰ UTC
    saturday_9am = _tehran(2026, 1, 3, 9)
    assert saturday_9am == _utc(2026, 1, 3, 5, 30)

    # قبل از ساعت ⇒ بازه‌یِ هفته‌یِ قبل
    assert start(to_tehran(_utc(2026, 1, 3, 5, 0)), 0, 9) == _tehran(2025, 12, 27, 9)
    # دقیقاً سرِ ساعت و بعدش ⇒ همان شنبه
    assert start(to_tehran(saturday_9am), 0, 9) == saturday_9am
    assert start(to_tehran(_utc(2026, 1, 3, 8)), 0, 9) == saturday_9am
    # وسطِ هفته ⇒ تازه‌ترین شنبه، نه هفته‌یِ بعد
    assert start(to_tehran(_utc(2026, 1, 6, 12)), 0, 9) == saturday_9am
    # جمعه (۶) ساعتِ ۲۳ِ تهران = جمعه ۱۹:۳۰ UTC
    assert start(to_tehran(_utc(2026, 1, 9, 20)), 6, 23) == _tehran(2026, 1, 9, 23)
    # ساعتِ خارجِ بازه به ۰..۲۳ محدود می‌شود (نه استثناء)
    assert start(to_tehran(_utc(2026, 1, 3, 22)), 0, 99).hour == 23
    print("✅ test_weekday_conversion_and_window_pure PASSED")


# ============================================================================= ۲ — یک‌بار در بازه
async def test_sent_once_per_weekly_window(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    # هفته‌یِ قبل سرِ ساعت فرستاده شده (پایدار، نه فروشگاهِ تازه)
    await _set_schedule(shop_bot_id, weekday=0, hour=9, last_sent=_tehran(2025, 12, 27, 9, 5))

    async def run(now: datetime.datetime) -> None:
        async with session_scope() as session:
            await report_service.send_due_reports(session, main_bot, now=now)

    sent = main_bot.session.sent_messages
    await run(_utc(2026, 1, 3, 5, 0))  # شنبه ۰۸:۳۰ تهران — هنوز نرسیده
    assert len(sent) == 0, "قبل از ساعتِ تنظیم‌شده نباید برود"

    await run(_utc(2026, 1, 3, 5, 30))  # شنبه ۰۹:۰۰ تهران — سرِ وقت
    assert len(sent) == 1, f"سرِ ساعت باید دقیقاً یک‌بار برود؛ رفته: {len(sent)}"
    assert sent[0]["chat_id"] == OWNER_TG_ID

    await run(_utc(2026, 1, 3, 6, 0))  # تیکِ ۳۰ دقیقه‌یِ بعدِ همان روز
    await run(_utc(2026, 1, 3, 20))  # آخرِ همان روز
    await run(_utc(2026, 1, 6, 12))  # سه‌شنبه‌یِ همان هفته
    assert len(sent) == 1, "در همان بازه نباید دوباره برود"

    await run(_utc(2026, 1, 10, 5, 30))  # شنبه‌یِ هفته‌یِ بعد، سرِ همان ساعت
    assert len(sent) == 2, "هفته‌یِ بعد سرِ همان ساعت باید دوباره برود"

    async with session_scope() as session:
        row = (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()
        assert row.last_report_sent_at == _utc(2026, 1, 10, 5, 30)
    print("✅ test_sent_once_per_weekly_window PASSED")


# ============================================================================= ۳ — مبنا تهران است نه UTC
async def test_schedule_is_anchored_to_tehran_not_utc(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    # جمعه ساعتِ ۲۳ِ تهران = جمعه ۱۹:۳۰ UTC
    await _set_schedule(shop_bot_id, weekday=6, hour=23, last_sent=_tehran(2026, 1, 2, 23, 5))

    sent = main_bot.session.sent_messages
    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=_utc(2026, 1, 9, 19, 0))
    assert len(sent) == 0, "۱۹:۰۰ UTC یعنی ۲۲:۳۰ تهران — هنوز نرسیده"

    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=_utc(2026, 1, 9, 19, 30))
    assert len(sent) == 1, "۱۹:۳۰ UTC یعنی ۲۳:۰۰ تهران — سرِ وقت"

    # اگر مبنا UTC بود، همین‌جا (۲۳:۰۰ UTC = ۰۲:۳۰ شنبه‌یِ تهران) باز هم می‌فرستاد
    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=_utc(2026, 1, 9, 23, 0))
    assert len(sent) == 1, "۲۳:۰۰ UTC از بازه‌یِ تهران گذشته و نباید دوباره برود"
    print("✅ test_schedule_is_anchored_to_tehran_not_utc PASSED")


# ============================================================================= ۴ — سوییچِ خاموش
async def test_disabled_shop_gets_nothing(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_schedule(shop_bot_id, weekday=0, hour=9, enabled=False, last_sent=None)

    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=_utc(2026, 1, 3, 6))
    assert main_bot.session.sent_messages == []
    print("✅ test_disabled_shop_gets_nothing PASSED")


async def _owner_id_of(shop_bot_id: int) -> int:
    async with session_scope() as session:
        return (await session.execute(select(ShopBot.shop_owner_id).where(ShopBot.id == shop_bot_id))).scalar_one()


# ============================================================================= ۵ — توقفِ زمان (K3/K4)
async def test_time_freeze_skips_reports(main_bot) -> None:
    await reset_database()
    main_bot.session.sent_messages.clear()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    second = await seed_usable_shop(OTHER_OWNER_TG_ID, OTHER_SHOP_BOT_TG_ID)
    await _set_schedule(first, weekday=0, hour=9, last_sent=None)
    await _set_schedule(second, weekday=0, hour=9, last_sent=None)
    now = _utc(2026, 1, 3, 6)

    async with session_scope() as session:
        freeze = await time_freeze_service.start(
            session, scope="owner", owner_id=await _owner_id_of(first), max_days=7, reason=None, by="test"
        )
        assert freeze is not None
    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=now)
    sent = main_bot.session.sent_messages
    assert [m["chat_id"] for m in sent] == [OTHER_OWNER_TG_ID], "فقط فروشگاه‌دارِ فریزنشده گزارش می‌گیرد"

    # فریزِ سراسری ⇒ هیچ
    await reset_database()
    main_bot.session.sent_messages.clear()
    first = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    await _set_schedule(first, weekday=0, hour=9, last_sent=None)
    async with session_scope() as session:
        assert await time_freeze_service.start(session, scope="all", owner_id=None, max_days=7, reason=None, by="test")
    async with session_scope() as session:
        await report_service.send_due_reports(session, main_bot, now=now)
    assert main_bot.session.sent_messages == []
    print("✅ test_time_freeze_skips_reports PASSED")


# ============================================================================= ۶ — پنلِ فروشگاه‌دار
async def test_owner_report_schedule_panel(main_dp) -> None:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    owner = Chat(main_dp, OWNER_TG_ID)

    async def stored():
        async with session_scope() as session:
            return (await session.execute(select(ShopBot).where(ShopBot.id == shop_bot_id))).scalar_one()

    await owner.say("⚙️ تنظیماتِ ربات فروشگاه")
    assert "گزارشِ دوره‌ای: شنبه ساعتِ 09:00" in owner.last_text, owner.last_text
    await owner.tap("rp_open")
    assert "روزِ هفته: شنبه" in owner.edits[-1]["text"] and "وضعیت: 🟢 روشن" in owner.edits[-1]["text"]

    await owner.tap("rp_day:3")
    row = await stored()
    assert row.weekly_report_weekday == 3 and owner.last_toast["text"] == texts.REPORT_SCHEDULE_SAVED
    assert "روزِ هفته: سه‌شنبه" in owner.edits[-1]["text"]

    await owner.tap("rp_hour:18")
    assert (await stored()).weekly_report_hour == 18
    assert "ساعت: 18:00 (به وقتِ تهران)" in owner.edits[-1]["text"]

    # کلیدهایِ دستکاری‌شده/نامعتبر رد می‌شوند و چیزی را خراب نمی‌کنند
    for bad in ("rp_day:9", "rp_day:-1", "rp_day:abc", "rp_hour:24", "rp_hour:x"):
        await owner.tap(bad)
        assert owner.last_toast["text"] == texts.SHOP_SETTINGS_STALE, bad
    row = await stored()
    assert row.weekly_report_weekday == 3 and row.weekly_report_hour == 18

    # ساعتِ دلخواه: ارقامِ فارسی، ردِّ نامعتبر، ماندنِ state
    await owner.tap("rp_hour_custom")
    assert owner.last_text == texts.REPORT_HOUR_ASK
    for bad in ("24", "abc", "-3", "²"):
        await owner.say(bad)
        assert owner.last_text == texts.REPORT_HOUR_INVALID, bad
    assert (await stored()).weekly_report_hour == 18
    await owner.say("۲۱")
    assert (await stored()).weekly_report_hour == 21
    assert "ساعت: 21:00 (به وقتِ تهران)" in owner.last_text

    # دابل‌تپ روی خاموش/روشن: دو بار ⇒ همان وضعیتِ اول
    await owner.tap("rp_toggle")
    assert (await stored()).weekly_report_enabled is False
    await owner.tap("rp_toggle")
    await owner.tap("rp_toggle")
    assert (await stored()).weekly_report_enabled is False

    await owner.tap("rp_back")
    assert "مدتِ تجمیعِ پیام‌ها" in owner.edits[-1]["text"], "برگشت به صفحه‌یِ تنظیماتِ ربات"

    # ایزولاسیون: تنظیماتِ فروشگاهِ دیگر دست‌نخورده
    assert shop_bot_service.valid_report_weekday(6) and not shop_bot_service.valid_report_weekday(7)
    assert not shop_bot_service.valid_report_weekday("3") and not shop_bot_service.valid_report_weekday(None)
    assert shop_bot_service.parse_report_hour("۰") == 0 and shop_bot_service.parse_report_hour("23") == 23
    assert shop_bot_service.parse_report_hour("24") is None and shop_bot_service.parse_report_hour("abc") is None
    print("✅ test_owner_report_schedule_panel PASSED")


async def main() -> None:
    main_dp, _shop_dp, _bot_manager, main_bot = build_test_dispatchers()
    test_weekday_conversion_and_window_pure()
    await test_sent_once_per_weekly_window(main_bot)
    await test_schedule_is_anchored_to_tehran_not_utc(main_bot)
    await test_disabled_shop_gets_nothing(main_bot)
    await test_time_freeze_skips_reports(main_bot)
    await test_owner_report_schedule_panel(main_dp)


if __name__ == "__main__":
    asyncio.run(main())
