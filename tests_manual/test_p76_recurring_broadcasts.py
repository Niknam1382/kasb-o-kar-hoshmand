"""پ۷۶ · خواستهٔ مالک (موردِ ۱۷، ۲۰۲۶-۱۱-۱۲): «رابطِ زمان‌بندی را بازنویسی کن و ارسالِ چندروزه/هفتگی بگذار».

پوششِ داده‌شده:
۱. ریاضِ زمان: `occurrence` (روز + ساعت به وقتِ تهران ⇒ UTC) و `next_occurrence` (گامِ روزانه/هفتگی،
   پایانِ `repeat_until`، سقفِ ۶۰ نوبت، و جبرانِ تأخیرِ جاب بدونِ جابه‌جاییِ ساعتِ انتخابی).
۲. `schedule` با پیش‌فرضِ `once` ⇒ همان رفتارِ امروز؛ نوعِ ناشناخته به `once` برمی‌گردد (نه خطا).
۳. `queue_due` برایِ ردیفِ تکرارشونده: صف + `repeat_sent+1` + `pending` شدنِ دوباره با زمانِ بعدی؛
   کلیدِ dedupe هر نوبت تازه است ⇒ نوبتِ دوم پیامِ تکراری نمی‌شود ولی دو نوبتِ هم‌زمانِ یکِ نوبت نه.
   ردیفِ `once` دقیقاً مثلِ دیروز `queued` می‌شود و کلیدِ dedupe‌اش عوض نمی‌شود.
۴. ویزاردِ پنل: روز ← ساعت ← تکرار ← پایان ← پیش‌نمایش ← تایید؛ ورودیِ دست‌کاری‌شده در هر گام رد
   می‌شود، «❌ لغو» از هر گام کار می‌کند، و مسیرِ قدیمی (`sched_when:*` + نوشتنِ آزاد) سرجایش است.
۵. کیبورد: بودجهٔ ۶۴ بایتیِ `schedw_*` و دیده‌شدنِ «🔁 هر روز» در فهرستِ ارسال‌ها.

اجرا: python3 tests_manual/run_one.py test_p76_recurring_broadcasts.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

from aiogram import Bot  # noqa: E402

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app.bots.main_bot import keyboards, texts  # noqa: E402
from app.database.models import Notification, ScheduledBroadcast  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import scheduled_broadcast_service as svc, shop_bot_service, shop_owner_service  # noqa: E402
from app.utils.jalali import TEHRAN_TZ  # noqa: E402
from harness import FakeSession, build_test_dispatchers, register_fake_shop_bot, reset_database  # noqa: E402
from phase4_helpers import Chat, add_customer, callbacks  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER = 997_701
SHOP_BOT_TG = 997_702
CUSTOMER_ONE = 997_711
CUSTOMER_TWO = 997_712
NOW = dt.datetime(2026, 11, 15, 6, 0, tzinfo=dt.timezone.utc)  # ۰۹:۳۰ به وقتِ تهران
SHOP: dict[str, int] = {}


# ============================================================================= ۱ — ریاضِ زمان
def test_occurrence_math_is_tehran_aware() -> None:
    today_noon = svc.occurrence(0, 12, 0, NOW)
    assert today_noon is not None and today_noon.hour == 8, today_noon  # ۱۲:۰۰ تهران == ۰۸:۰۰ UTC
    assert today_noon.date() == NOW.astimezone(TEHRAN_TZ).date()
    assert svc.occurrence(1, 9) == svc.occurrence(1, 9, 0)
    assert svc.occurrence(0, 24) is None and svc.occurrence(-1, 10) is None and svc.occurrence(1, 10, 99) is None
    assert svc.occurrence(svc.MAX_LEAD_DAYS + 1, 10) is None

    row = ScheduledBroadcast(
        shop_bot_id=1, owner_id=1, text="ت", scheduled_at=NOW, repeat_kind=svc.REPEAT_DAILY, repeat_sent=0
    )
    nxt = svc.next_occurrence(row, NOW)
    assert nxt == NOW + dt.timedelta(days=1), nxt
    row.repeat_kind = svc.REPEAT_WEEKLY
    assert svc.next_occurrence(row, NOW) == NOW + dt.timedelta(days=7)
    row.repeat_kind = svc.REPEAT_ONCE
    assert svc.next_occurrence(row, NOW) is None, "یک‌بارمصرف دیگر نوبتی ندارد"

    row.repeat_kind = svc.REPEAT_DAILY
    row.repeat_until = NOW + dt.timedelta(days=2, hours=1)
    assert svc.next_occurrence(row, NOW) == NOW + dt.timedelta(days=1), "نوبتِ بعدی پیش ازِ پایان است"
    row.scheduled_at = NOW + dt.timedelta(days=2)
    assert svc.next_occurrence(row, NOW) is None, "نوبتِ بعدی از repeat_until می‌گذرد ⇒ تمام"
    row.repeat_until = None
    row.repeat_sent = svc.REPEAT_MAX_OCCURRENCES
    assert svc.next_occurrence(row, NOW) is None, "سقفِ ایمنیِ ۶۰ نوبت"
    # جاب دیر افتاده: نوبتِ بعدی در گذشته نیست
    row.repeat_sent = 0
    row.scheduled_at = NOW - dt.timedelta(days=3)
    late = svc.next_occurrence(row, NOW)
    assert late is not None and late > NOW, late
    print("PASS test_occurrence_math_is_tehran_aware")


# ============================================================================= ۲ و ۳ — سرویس و جاب
async def _make_shop() -> int:
    await reset_database()
    shop_bot_id = await seed_usable_shop(OWNER, SHOP_BOT_TG)
    SHOP["id"] = shop_bot_id
    async with session_scope() as session:
        owner = await shop_owner_service.get_by_telegram_id(session, OWNER)
        SHOP["owner"] = owner.id
    await add_customer(shop_bot_id, CUSTOMER_ONE, first_name="سارا")
    await add_customer(shop_bot_id, CUSTOMER_TWO, first_name="رضا")
    return shop_bot_id


async def _notifications() -> list[str]:
    async with session_scope() as session:
        rows = (await session.execute(select(Notification.dedupe_key).order_by(Notification.id))).scalars().all()
    return list(rows)


async def _row() -> ScheduledBroadcast:
    async with session_scope() as session:
        return (await session.execute(select(ScheduledBroadcast))).scalar_one()


async def _set_scheduled_at(moment: dt.datetime) -> None:
    async with session_scope() as session:
        row = (await session.execute(select(ScheduledBroadcast))).scalar_one()
        row.scheduled_at = moment
        await session.commit()


async def test_schedule_defaults_and_recurring_columns() -> None:
    await _make_shop()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, SHOP["id"])
        plain = await svc.schedule(session, shop_bot=shop_bot, owner_id=SHOP["owner"], text="سلام ۱", scheduled_at=NOW + dt.timedelta(hours=2))
        weekly = await svc.schedule(
            session, shop_bot=shop_bot, owner_id=SHOP["owner"], text="سلام ۲", scheduled_at=NOW + dt.timedelta(days=1),
            repeat_kind=svc.REPEAT_WEEKLY, repeat_until=NOW + dt.timedelta(days=8),
        )
        bogus = await svc.schedule(
            session, shop_bot=shop_bot, owner_id=SHOP["owner"], text="سلام ۳", scheduled_at=NOW + dt.timedelta(hours=3),
            repeat_kind="every-other-tuesday",
        )
        await session.commit()
    assert plain.repeat_kind == svc.REPEAT_ONCE and plain.repeat_sent == 0 and plain.repeat_until is None
    assert weekly.repeat_kind == svc.REPEAT_WEEKLY
    assert weekly.repeat_until == (NOW + dt.timedelta(days=8)).astimezone(dt.timezone.utc)
    assert bogus.repeat_kind == svc.REPEAT_ONCE, "نوعِ ناشناخته ⇒ یک‌بارمصرف، نه خطا"
    print("PASS test_schedule_defaults_and_recurring_columns")


async def test_queue_due_repeats_and_keeps_once_identical() -> None:
    await _make_shop()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, SHOP["id"])
        await svc.schedule(
            session, shop_bot=shop_bot, owner_id=SHOP["owner"], text="هر روز سلام",
            scheduled_at=NOW - dt.timedelta(minutes=1), repeat_kind=svc.REPEAT_DAILY,
            repeat_until=NOW + dt.timedelta(days=1, hours=1),
        )
        await session.commit()

    async with session_scope() as session:
        first = await svc.queue_due(session, None, now=NOW)
        await session.commit()
    assert first["queued"] == 2 and first["scheduled"] == 1, first
    row = await _row()
    assert row.status == svc.PENDING and row.repeat_sent == 1, (row.status, row.repeat_sent)
    assert row.scheduled_at == NOW - dt.timedelta(minutes=1) + dt.timedelta(days=1), row.scheduled_at
    keys_after_first = await _notifications()
    assert len(keys_after_first) == 2 and keys_after_first[0] != keys_after_first[1]

    second_now = row.scheduled_at + dt.timedelta(minutes=1)
    async with session_scope() as session:
        second = await svc.queue_due(session, None, now=second_now)
        await session.commit()
    assert second["queued"] == 2, second
    row = await _row()
    assert row.repeat_sent == 2, row.repeat_sent
    keys = await _notifications()
    assert len(keys) == 4, "نوبتِ دوم کلیدِ تازه دارد ⇒ پیامِ تکراری نمی‌شود، ولی نوبت هم جا نمی‌افتد"
    assert len(set(keys)) == 4

    # نوبتِ سوم از repeat_until می‌گذرد ⇒ تمام
    third_now = row.scheduled_at + dt.timedelta(minutes=1)
    async with session_scope() as session:
        third = await svc.queue_due(session, None, now=third_now)
        await session.commit()
    assert third["scheduled"] == 0, third
    assert (await _row()).status == svc.QUEUED, "پایانِ تکرار ⇒ دیگر pending نمی‌شود"

    # رفتارِ یک‌بارمصرف: همان status و همان شکلِ کلیدِ قدیمی
    await _make_shop()
    async with session_scope() as session:
        shop_bot = await shop_bot_service.get_by_id(session, SHOP["id"])
        await svc.schedule(session, shop_bot=shop_bot, owner_id=SHOP["owner"], text="یک‌بار", scheduled_at=NOW - dt.timedelta(minutes=5))
        await session.commit()
    async with session_scope() as session:
        summary = await svc.queue_due(session, None, now=NOW)
        await session.commit()
    assert summary["queued"] == 2, summary
    row = await _row()
    assert row.status == svc.QUEUED and row.repeat_sent == 1 and row.scheduled_at < NOW
    keys = await _notifications()
    broadcast_id = row.id
    assert keys == [f"bcast:{broadcast_id}:{CUSTOMER_ONE}:telegram", f"bcast:{broadcast_id}:{CUSTOMER_TWO}:telegram"], keys
    print("PASS test_queue_due_repeats_and_keeps_once_identical")


# ============================================================================= ۴ — ویزاردِ پنل
async def test_wizard_flow(main_dp, bot_manager) -> None:
    shop_bot_id = await _make_shop()
    shop_bot_instance = _shop_bot_instance(shop_bot_id)
    register_fake_shop_bot(bot_manager, shop_bot_id, shop_bot_instance)
    owner = Chat(main_dp, OWNER)

    await owner.say(texts.BROADCAST_SALES_BUTTON)
    await owner.say("تخفیفِ هر روز 🎁")
    assert "customer_broadcast_schedule" in callbacks(owner.last_markup), owner.last_markup
    await owner.tap("customer_broadcast_schedule")
    datas = callbacks(owner.last_markup)
    assert "schedw_day" in datas and "sched_when:1h" in datas, datas  # مسیرِ قدیمی دست‌نخورده

    await owner.tap("schedw_day")
    assert "کدامِ روز؟" in owner.last_text, owner.last_text
    await owner.tap("schedw_day:1")
    assert "چه ساعتی؟" in owner.last_text, owner.last_text
    await owner.tap("schedw_time:18")
    assert "یک‌بار فرستاده شود یا تکرار شود؟" in owner.last_text, owner.last_text
    await owner.tap("schedw_repeat:daily")
    assert "تکرار تا کِی" in owner.last_text, owner.last_text
    await owner.tap("schedw_until:7")
    preview = owner.last_text
    assert "🔁 تکرار: هر روز" in preview, preview
    assert "🏁 پایانِ تکرار:" in preview and "۲ نفر" in preview, preview
    assert not any(char.isascii() and char.isdigit() for char in preview), preview
    assert callbacks(owner.last_markup) == ["schedw_confirm", "schedw_day", "customer_broadcast_cancel"], owner.last_markup

    await owner.tap("schedw_confirm")
    row = await _row()
    assert row.repeat_kind == svc.REPEAT_DAILY and row.repeat_until is not None, (row.repeat_kind, row.repeat_until)
    assert row.status == svc.PENDING and row.repeat_sent == 0
    assert row.text == "تخفیفِ هر روز 🎁"
    assert "اولین ارسال" in owner.last_edit_text and "هر روز" in owner.last_edit_text, owner.last_edit_text

    await owner.say(texts.SCHEDULED_LIST_BUTTON)
    assert "🔁 هر روز" in owner.last_text or "· هر روز" in owner.last_text, owner.last_text

    # گامِ «یک‌بار» بی‌پرسیدنِ پایان، مستقیم پیش‌نمایش می‌دهد
    await owner.say(texts.BROADCAST_SALES_BUTTON)
    await owner.say("یک‌بارمصرف")
    await owner.tap("customer_broadcast_schedule")
    await owner.tap("schedw_day")
    await owner.tap("schedw_day:2")
    await owner.tap("schedw_time:12")
    await owner.tap("schedw_repeat:once")
    assert "🔁 تکرار: یک‌بار" in owner.last_text, owner.last_text
    await owner.tap("schedw_confirm")
    rows = await _all_rows()
    assert len(rows) == 2 and rows[-1].repeat_kind == svc.REPEAT_ONCE
    print("PASS test_wizard_flow")


async def _all_rows() -> list[ScheduledBroadcast]:
    async with session_scope() as session:
        return list((await session.execute(select(ScheduledBroadcast).order_by(ScheduledBroadcast.id))).scalars().all())


def _shop_bot_instance(shop_bot_id: int) -> Bot:
    return Bot(token=f"{SHOP_BOT_TG}:FAKE", session=FakeSession())


async def test_wizard_rejects_bad_steps(main_dp, bot_manager) -> None:
    shop_bot_id = await _make_shop()
    register_fake_shop_bot(bot_manager, shop_bot_id, _shop_bot_instance(shop_bot_id))
    owner = Chat(main_dp, OWNER)
    await owner.say(texts.BROADCAST_SALES_BUTTON)
    await owner.say("متنِ آزمون")
    await owner.tap("customer_broadcast_schedule")
    await owner.tap("schedw_day")

    await owner.tap("schedw_day:abc")
    assert owner.last_toast["text"] == texts.SCHEDULE_WIZARD_STALE, owner.last_toast
    await owner.tap("schedw_day:1")
    await owner.tap("schedw_time:99")
    assert owner.last_toast["text"] == texts.SCHEDULE_WIZARD_BAD_TIME, owner.last_toast
    await owner.tap("schedw_time:custom")
    await owner.say("هیچ‌وقت")
    assert owner.last_text == texts.SCHEDULE_WIZARD_BAD_TIME, owner.last_text
    await owner.say("۱۰:۳۰")
    assert "یک‌بار فرستاده شود" in owner.last_text, owner.last_text
    await owner.tap("schedw_repeat:fortnightly")
    assert owner.last_toast["text"] == texts.SCHEDULE_WIZARD_STALE
    await owner.tap("schedw_repeat:weekly")
    await owner.tap("schedw_until:xyz")
    assert owner.last_toast["text"] == texts.SCHEDULE_WIZARD_STALE
    await owner.tap("schedw_until:0")
    assert "بدونِ تاریخِ پایان" in owner.last_text, owner.last_text
    assert "✅ زمان‌بندی کن" in [b.text for row in owner.last_markup.inline_keyboard for b in row], owner.last_markup

    # لغو از میانهٔ ویزارد ⇒ هیچ ردیفی نمی‌ماند
    await owner.tap("customer_broadcast_cancel")
    assert owner.last_edit_text == texts.CUSTOMER_BROADCAST_CANCELLED, owner.last_edit_text
    async with session_scope() as session:
        left = (await session.execute(select(func.count()).select_from(ScheduledBroadcast))).scalar_one()
    assert left == 0, left
    print("PASS test_wizard_rejects_bad_steps")


def test_keyboard_budget() -> None:
    flat = callbacks(keyboards.schedule_wizard_day_keyboard())
    assert flat == ["schedw_day:0", "schedw_day:1", "schedw_day:2", "schedw_day:3", "schedw_day:7", "customer_broadcast_cancel"], flat
    assert all(len(item.encode("utf-8")) <= 64 for item in flat), flat
    assert callbacks(keyboards.schedule_wizard_time_keyboard())[-1] == "schedw_day"
    assert callbacks(keyboards.schedule_wizard_until_keyboard())[-2] == "schedw_until:0"
    assert callbacks(keyboards.schedule_wizard_confirm_keyboard()) == ["schedw_confirm", "schedw_day", "customer_broadcast_cancel"]
    assert texts.SCHEDULE_REPEAT_LABELS == {"once": "یک‌بار", "daily": "هر روز", "weekly": "هر هفته"}
    print("PASS test_keyboard_budget")


async def main() -> None:
    main_dp, _shop_dp, bot_manager, _main_bot = build_test_dispatchers()
    test_occurrence_math_is_tehran_aware()
    await test_schedule_defaults_and_recurring_columns()
    await test_queue_due_repeats_and_keeps_once_identical()
    await test_wizard_flow(main_dp, bot_manager)
    await test_wizard_rejects_bad_steps(main_dp, bot_manager)
    test_keyboard_budget()
    print("📊 نتیجه: ۶ تستِ پ۷۶ (ویزاردِ زمان‌بندی + ارسالِ چندروزه/هفتگی) پاس شد")


if __name__ == "__main__":
    asyncio.run(main())
