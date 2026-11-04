"""
تست: P31-B — آمارِ روزانه باید برایِ همهٔ فروشگاه‌ها در یکِ تعدادِ ثابتِ کوئری ساخته شود

پیش‌ازاین `report_service.send_due_nightly_reports` داخلِ حلقه به‌ازایِ هر فروشگاه پنج‌کوئری
می‌زد (`stats_service.get_shop_daily_stats`) ⇒ با ۵۰۰ فروشگاه ~۲٬۵۰۰ کوئری در یکِ پاسِ ۳۰
دقیقه‌ای. رفع: `get_shops_daily_stats` با پنج کوئریِ `IN (…) GROUP BY shop_bot_id`.

سه قفل:
۱. عددِ هر فروشگاه **عیناً** مثلِ مسیرِ تک‌فروشگاه است (نه جمعِ سراسری — همان باگِ P29)
۲. تعدادِ کوئری‌ها با N ثابت می‌ماند
۳. فروشگاهِ بدونِ فعالیت صفر می‌گیرد، نه ردیفِ غایب

اجرا: python3 tests_manual/run_one.py test_p31_nightly_stats_batching.py
"""
from __future__ import annotations

import asyncio
import contextlib
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import event  # noqa: E402

from harness import reset_database  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

from app.database.models import Customer, KnowledgeGap, KnowledgeGapStatus, OrderType  # noqa: E402
from app.database.session import engine, session_scope  # noqa: E402
from app.services import order_service, stats_service  # noqa: E402

OWNER_BASE = 999361
BOT_BASE = 999362


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


async def _seed_shops(count: int) -> list[int]:
    return [await seed_usable_shop(OWNER_BASE + index, BOT_BASE + index) for index in range(count)]


async def _add_activity(shop_bot_id: int, *, orders: int, gaps: int) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    async with session_scope() as session:
        customer = await session.scalar(
            Customer.__table__.select().where(Customer.shop_bot_id == shop_bot_id).limit(1)
        )
        telegram_id = 880000 + shop_bot_id
        if customer is None:
            from app.services import customer_service

            customer = await customer_service.get_or_create_customer(session, shop_bot_id, telegram_id, "مشتری", None)
        for index in range(orders):
            await order_service.create_order(session, shop_bot_id, customer.id, OrderType.ORDER, f"سفارشِ {index}", 150_000)
        for index in range(gaps):
            session.add(
                KnowledgeGap(
                    shop_bot_id=shop_bot_id,
                    question_key=f"p31b-{shop_bot_id}-{index}",
                    question_text=f"سوالِ {index}؟",
                    status=KnowledgeGapStatus.OPEN,
                    first_seen_at=now - dt.timedelta(minutes=5),
                    occurrences=1,
                )
            )
        await session.commit()


async def test_grouped_numbers_equal_per_shop_numbers() -> None:
    await reset_database()
    shop_ids = await _seed_shops(3)
    await _add_activity(shop_ids[0], orders=2, gaps=1)
    await _add_activity(shop_ids[1], orders=1, gaps=0)
    await _add_activity(shop_ids[2], orders=0, gaps=0)

    now = dt.datetime.now(dt.timezone.utc)
    day_start = dt.datetime.combine(now.date(), dt.time.min, tzinfo=dt.timezone.utc)

    async with session_scope() as session:
        single = {sid: await stats_service.get_shop_daily_stats(session, sid, day_start, now) for sid in shop_ids}
        grouped = await stats_service.get_shops_daily_stats(session, set(shop_ids), day_start, now)

    for sid in shop_ids:
        assert grouped[sid] == single[sid], f"عددِ فروشگاه {sid} عوض شد: {grouped[sid]} != {single[sid]}"
    assert grouped[shop_ids[0]]["new_orders_today"] == 2, grouped[shop_ids[0]]
    assert grouped[shop_ids[0]]["new_knowledge_gaps"] == 1, grouped[shop_ids[0]]
    # فروشگاهِ سوم فقط مشتریِ ساخته‌شده‌یِ همین تست را دارد (سیدِ seed_usable_shop آن را
    # می‌سازد)، پس صفرِ مورد انتظار در «سفارش» و «سوالِ بی‌جواب» است نه در همهٔ ستون‌ها.
    assert grouped[shop_ids[2]]["new_orders_today"] == 0, grouped[shop_ids[2]]
    assert grouped[shop_ids[2]]["new_knowledge_gaps"] == 0, grouped[shop_ids[2]]
    assert set(grouped[shop_ids[2]]) == set(single[shop_ids[2]]), "همهٔ کلیدها باید برایِ هر فروشگاه باشند"
    print("✅ test_grouped_numbers_equal_per_shop_numbers PASSED")


async def test_query_count_does_not_grow_with_shops() -> None:
    await reset_database()
    one = await _seed_shops(1)
    async with session_scope() as session:
        now = dt.datetime.now(dt.timezone.utc)
        day_start = dt.datetime.combine(now.date(), dt.time.min, tzinfo=dt.timezone.utc)
        with _counted() as seen_one:
            await stats_service.get_shops_daily_stats(session, set(one), day_start, now)
        per_shop_one = len(seen_one)

    six = await _seed_shops(6)
    async with session_scope() as session:
        with _counted() as seen_six:
            await stats_service.get_shops_daily_stats(session, set(six), day_start, now)
    assert len(seen_six) == per_shop_one, f"تعدادِ کوئری با فروشگاه رشد کرد: {per_shop_one} ← {len(seen_six)}"
    assert per_shop_one == 5, f"انتظارِ پنج کوئریِ گروهی داشتیم؛ شد {per_shop_one}"
    print(f"✅ test_query_count_does_not_grow_with_shops PASSED ({per_shop_one} کوئری، مستقل از تعدادِ فروشگاه)")


async def main() -> None:
    await test_grouped_numbers_equal_per_shop_numbers()
    await test_query_count_does_not_grow_with_shops()


if __name__ == "__main__":
    asyncio.run(main())
