"""
تست: P29-B — جاب‌هایِ دوره‌ای نباید «به‌ازایِ هر فروشگاه» چندِ کوئری بزنند

عددِ MEASURED با `scripts/scale_probe.py` رویِ ۵۰۰ فروشگاه، پیش‌ازاین رفع:
  · پاسِ گرمِ جاب = ۵۲۸ statement که ۵۰۰تاش یکِ `SELECT shop_bots`ِ تکراری داخلِ
    `bot_branding_service.sync_all` بود — برایِ ربات‌هایی که نوبتِ بازرسی‌شان هم نشده بود
  · پاسِ سرد = ۴۳۲۹ statement؛ در حلقهٔ گزارشِ شبانه به‌ازایِ هر فروشگاه یکِ
    `session.get(ShopOwner)` و یکِ aggregate رویِ *کلِ* جدولِ کمیسیون می‌خورد (O(N²) با رشدِ داده)
رفع: خواندنِ دسته‌ای (یکِ `IN (…)`) و جمعِ بدهیِ هر فروشگاه در یکِ کوئریِ گروهی.

سه چیزی که این فایل قفل می‌کند:
  ۱. تعدادِ کوئریِ پاس با تعدادِ فروشگاه ثابت می‌ماند (رگرسیونِ N+1)
  ۲. با وجودِ خواندنِ دسته‌ای، فقط رباتِ نوبت‌دار پردازش می‌شود و برچسبِ «بازرسی شد» می‌گیرد؛
     بقیه دست‌نخورده می‌مانند (رفتارِ P21-A)
  ۳. «طلبِ کمیسیونِ وصول‌نشده» در گزارشِ شبانه بدهیِ *همان* فروشگاه است، نه جمعِ سراسریِ
     پنلِ ادمین (پیش‌ازاین عددِ بقیه به یکِ فروشگاه‌دار نشان داده می‌شد)

اجرا: python3 tests_manual/run_one.py test_p29_job_query_bounds.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests_manual"))

from sqlalchemy import event, select  # noqa: E402

from harness import build_test_dispatchers, make_shop_bot, register_fake_shop_bot, reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import ShopBot  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import bot_branding_service, commission_receivable_service, report_service  # noqa: E402
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.utils.validators import format_toman  # noqa: E402

OWNER_BASE = 9_300_000
BOT_BASE = 9_400_000
VALID_TOKEN = "111111:" + "A" * 32


@contextlib.contextmanager
def counted() -> list[str]:
    """statement‌هایِ داخلِ بلوک را جمع می‌کند (برایِ اثباتِ «ثابت نسبت به N»)."""
    seen: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG002
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


def containing(statements: list[str], needle: str) -> int:
    return sum(1 for s in statements if needle in " ".join(s.split()).lower())


async def seed_shops(count: int) -> list[int]:
    return [await seed_usable_shop(OWNER_BASE + index, BOT_BASE + index) for index in range(count)]


async def test_branding_pass_does_not_query_per_bot(bot_manager, main_bot) -> None:
    await reset_database()
    shop_bot_ids = await seed_shops(6)
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
    async with session_scope() as session:
        rows = (await session.execute(select(ShopBot).where(ShopBot.id.in_(shop_bot_ids)))).scalars().all()
        for shop_bot in rows:
            shop_bot.branding_next_check_at = future
    for shop_bot_id in shop_bot_ids:
        register_fake_shop_bot(bot_manager, shop_bot_id, make_shop_bot(VALID_TOKEN))

    async with session_scope() as session:
        with counted() as statements:
            counts = await bot_branding_service.sync_all(session, bot_manager, main_bot)
    assert counts["shops"] == 0, f"رباتِ بی‌نوبت نباید پردازش شود: {counts}"
    bot_selects = containing(statements, "from shop_bots")
    assert bot_selects == 1, f"۶ ربات ⇒ {bot_selects} SELECT از shop_bots (باید یکِ خواندنِ دسته‌ای باشد)"

    # فقط یکی را نوبت‌دار کن: همان پردازش می‌شود و برچسبِ بازرسی می‌گیرد، بقیه دست‌نخورده
    due_id = shop_bot_ids[2]
    async with session_scope() as session:
        admin_settings = await get_admin_settings(session)
        admin_settings.branding_text = "فروشگاهِ رسمی — پشتیبانی ۹ تا ۱۸"
        shop_bot = await session.get(ShopBot, due_id)
        shop_bot.branding_next_check_at = None
        shop_bot.branding_checked_at = None

    async with session_scope() as session:
        with counted() as second:
            counts = await bot_branding_service.sync_all(session, bot_manager, main_bot)
    assert counts["shops"] == 1, f"فقط رباتِ نوبت‌دار پردازش می‌شود: {counts}"
    assert containing(second, "from shop_bots") == 1
    async with session_scope() as session:
        rows = (await session.execute(select(ShopBot.id, ShopBot.branding_checked_at).where(ShopBot.id.in_(shop_bot_ids)))).all()
    checked = {shop_id for shop_id, checked_at in rows if checked_at is not None}
    assert checked == {due_id}, f"برچسبِ بازرسی فقط به همان ربات: {checked}"
    print("✅ test_branding_pass_does_not_query_per_bot PASSED")


async def test_nightly_report_shows_each_shops_own_debt(main_bot) -> None:
    await reset_database()
    shop_bot_ids = await seed_shops(2)
    async with session_scope() as session:
        bots = (await session.execute(select(ShopBot).where(ShopBot.id.in_(shop_bot_ids)).order_by(ShopBot.id))).scalars().all()
        admin_settings = await get_admin_settings(session)
        admin_settings.nightly_report_enabled = True
        admin_settings.nightly_report_hour_utc = 0
        await commission_receivable_service.record(
            session, owner_id=bots[0].shop_owner_id, group_key="probe-group-0", amount_toman=100_000, note="تست"
        )
        await commission_receivable_service.record(
            session, owner_id=bots[1].shop_owner_id, group_key="probe-group-1", amount_toman=250_000, note="تست"
        )

    main_bot.session.sent_messages.clear()
    now = datetime.datetime.now(datetime.timezone.utc)
    async with session_scope() as session:
        with counted() as statements:
            await report_service.send_due_nightly_reports(session, main_bot, now=now)

    bodies = [m["text"] for m in main_bot.session.sent_messages]
    assert len(bodies) == 2, f"دو فروشگاه ⇒ دو گزارش، نه {len(bodies)}"
    joined = "\n".join(bodies)
    assert format_toman(100_000) in joined and format_toman(250_000) in joined, f"بدهیِ هر فروشگاه در گزارشِ خودش: {joined!r}"
    assert format_toman(350_000) not in joined, "جمعِ سراسریِ پنلِ ادمین نباید در گزارشِ خصوصیِ فروشگاه باشد"
    aggregates = containing(statements, "from commission_receivables")
    assert aggregates == 1, f"۲ فروشگاه ⇒ {aggregates} کوئری رویِ جدولِ کمیسیون (باید یکِ گروهی باشد)"
    assert containing(statements, "from shop_owners") == 1, "مالک‌ها دسته‌ای خوانده می‌شوند"
    print("✅ test_nightly_report_shows_each_shops_own_debt PASSED")


async def test_weekly_report_loads_owners_once(main_bot) -> None:
    await reset_database()
    shop_bot_ids = await seed_shops(3)
    async with session_scope() as session:
        bots = (await session.execute(select(ShopBot).where(ShopBot.id.in_(shop_bot_ids)))).scalars().all()
        for shop_bot in bots:
            shop_bot.weekly_report_enabled = True
            shop_bot.last_report_sent_at = None

    main_bot.session.sent_messages.clear()
    async with session_scope() as session:
        with counted() as statements:
            await report_service.send_due_reports(session, main_bot)
    assert len(main_bot.session.sent_messages) == 3, f"سه فروشگاه ⇒ سه گزارش: {len(main_bot.session.sent_messages)}"
    owner_selects = containing(statements, "from shop_owners")
    assert owner_selects == 1, f"۳ فروشگاه ⇒ {owner_selects} SELECT از shop_owners (باید یکی باشد)"
    print("✅ test_weekly_report_loads_owners_once PASSED")


async def main() -> None:
    _main_dispatcher, _shop_dispatcher, bot_manager, main_bot = build_test_dispatchers()
    await test_branding_pass_does_not_query_per_bot(bot_manager, main_bot)
    await test_nightly_report_shows_each_shops_own_debt(main_bot)
    await test_weekly_report_loads_owners_once(main_bot)
    print("\n✅ همهٔ تست‌هایِ P29ِ «جابِ بدونِ N+1» پاس شدند")


if __name__ == "__main__":
    asyncio.run(main())
