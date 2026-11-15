"""پ۷۹ · ایجنتِ سرور راند ۳: جمعِ شمارنده‌ها بینِ پروسه‌ها + باگِ «برچسبِ فارسی به‌جایِ نامِ خام».

چرا این فایل هست: تا پیش ازِ این `server_doctor.inspect()` شمارنده‌ها را از
`capacity_service.counters_lines()` می‌گرفت که **کلیدِ‌هایش برچسبِ فارسی** بود
(«رویدادِ نامعتبرِ ردشده»)، ولی `_counter_findings` با نامِ خام (`webhook.rejected`) می‌پرسید ⇒ آن سه
یافته در تولید **هیچ‌وقت** شلیک نمی‌کردند (عددِ صفر به‌نظر می‌رسید، یعنی «همه‌چیز سالم»). ضمناً
شمارنده‌ها در حافظهٔ هرِ پروسه‌اند و عیب‌یاب در پروسهٔ core اجرا می‌شود ⇒ در سرورِ چندworker کم‌گویی.

پوششِ داده‌شده:
۱. `local_counters` نامِ خام می‌دهد و فقط پیش‌شمارنده‌هایِ عملیاتی؛ `counters_lines` همان‌ها را برچسب
   می‌زند (تفکیکِ «داده» از «نمایش»).
۲. `process_key` شکلِ «میزبان:pid» دارد و در یکِ پروسه پایدار است.
۳. `publish_counters` یکِ upsert می‌سازد (دو ضربان ⇒ یکِ ردیف) و `aggregate_counters` سهمِ خودِ پروسه را
   یک‌بار می‌شمارد + ردیفِ پروسهٔ دیگر را اضافه می‌کند.
۴. ردیفِ بی‌اعتبار (قدیمی یا JSONِ خراب) در جمع نمی‌آید و در شمارهِ `stale` گزارش می‌شود.
۵. رگرسیونِ باگِ اصلی: پس ازِ `observability.count("webhook.rejected", 25)` یافتهٔ `webhook_rejected`
   در `inspect()` پیدا می‌شود، و خطِ «جمعِ شمارنده‌ها از N پروسه» در پنل ظاهر می‌شود.

اجرا: python3 tests_manual/run_one.py test_p79_counter_aggregation.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app import observability  # noqa: E402
from app.bots.main_bot import texts  # noqa: E402
from app.database.models import RuntimeCounterSnapshot  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import capacity_service, server_doctor  # noqa: E402
from harness import reset_database  # noqa: E402

UTC = dt.timezone.utc


async def _rows() -> list[RuntimeCounterSnapshot]:
    async with session_scope() as session:
        return list((await session.execute(select(RuntimeCounterSnapshot))).scalars().all())


# ============================================================================= ۱ و ۲ — نامِ خام و کلیدِ پروسه
def test_local_counters_keep_raw_names() -> None:
    observability.reset_counters()
    observability.count("webhook.rejected", 3)
    observability.count("wallet.deduct_denied")
    observability.count("not.operational")
    local = capacity_service.local_counters()
    assert local["webhook.rejected"] == 3 and local["wallet.deduct_denied"] == 1, local
    assert "not.operational" not in local, "فقط پیش‌شمارنده‌هایِ عملیاتی جمع می‌شوند"
    labelled = dict(capacity_service.counters_lines(local))
    assert labelled["رویدادِ نامعتبرِ ردشده"] == 3, labelled
    observability.reset_counters()
    print("PASS test_local_counters_keep_raw_names")


def test_process_key_shape() -> None:
    key = capacity_service.process_key()
    assert ":" in key and key == capacity_service.process_key(), key
    assert key.split(":")[-1].isdigit(), key
    print("PASS test_process_key_shape")


# ============================================================================= ۳ — ضربان و جمع
async def test_publish_is_upsert_and_aggregate_sums_processes() -> None:
    await reset_database()
    observability.reset_counters()
    observability.count("webhook.shop", 7)
    async with session_scope() as session:
        await capacity_service.publish_counters(session)
        await session.commit()
    async with session_scope() as session:
        await capacity_service.publish_counters(session)
        await session.commit()
    rows = await _rows()
    assert len(rows) == 1, f"دو ضربانِ یکِ پروسه ⇒ یکِ ردیف (نه دو تا): {len(rows)}"
    assert json.loads(rows[0].counters)["webhook.shop"] == 7, rows[0].counters

    # پروسهٔ دومی (جعلی) که خودش ۵ رویدادِ فروشگاهی دیده است
    async with session_scope() as session:
        session.add(
            RuntimeCounterSnapshot(
                process_key="other-worker:4242", hostname="other-worker",
                counters=json.dumps({"webhook.shop": 5, "wallet.deduct_denied": 2}),
                updated_at=dt.datetime.now(UTC),
            )
        )
        await session.commit()
    async with session_scope() as session:
        totals, processes, stale = await capacity_service.aggregate_counters(session)
    assert totals["webhook.shop"] == 12, totals  # ۷ سهمِ خود + ۵ سهمِ دیگری (سهمِ خود دوباره شمرده نشود)
    assert totals["wallet.deduct_denied"] == 2, totals
    assert processes == 2 and stale == 0, (processes, stale)
    print("PASS test_publish_is_upsert_and_aggregate_sums_processes")


# ============================================================================= ۴ — ردیفِ بی‌اعتبار
async def test_stale_and_broken_rows_are_excluded() -> None:
    await reset_database()
    observability.reset_counters()
    async with session_scope() as session:
        await capacity_service.publish_counters(session)
        old = dt.datetime.now(UTC) - dt.timedelta(seconds=capacity_service.SNAPSHOT_STALE_SECONDS + 60)
        session.add(
            RuntimeCounterSnapshot(process_key="dead-worker:1", hostname="dead", counters=json.dumps({"webhook.main": 99}), updated_at=old)
        )
        session.add(RuntimeCounterSnapshot(process_key="broken-worker:2", hostname="broken", counters="{not json", updated_at=old))
        await session.commit()
    async with session_scope() as session:
        totals, processes, stale = await capacity_service.aggregate_counters(session)
    assert totals.get("webhook.main", 0) == 0, totals
    assert processes == 1, processes
    assert stale == 2, stale
    observability.reset_counters()
    print("PASS test_stale_and_broken_rows_are_excluded")


# ============================================================================= ۵ — رگرسیونِ باگِ اصلی
async def test_doctor_uses_raw_names_and_reports_scope() -> None:
    await reset_database()
    observability.reset_counters()
    server_doctor.reset_alert_clock_for_tests()
    observability.count("webhook.rejected", 25)  # آستانهٔ پیش‌فرض: ۲۰
    async with session_scope() as session:
        findings = await server_doctor.inspect(session)
        snapshot = await capacity_service.snapshot(session)
    keys = {finding.key for finding in findings}
    assert "webhook_rejected" in keys, f"پیش ازِ پ۷۹ این یافته هرگز شلیک نمی‌کرد: {sorted(keys)}"
    # پ۷۹-الف: «چند پروسه» یافته نیست (وگرنه سرورِ سالم هر ساعت اخطارِ بی‌معنی می‌فرستد) — فقط در پنل
    assert "counters.scope" not in keys, sorted(keys)
    assert snapshot["processes"] >= 1 and snapshot["stale_processes"] == 0, snapshot
    body = texts.capacity_text(snapshot)
    assert "از شروعِ این پروسه" in body, body[-400:]
    observability.reset_counters()
    server_doctor.reset_alert_clock_for_tests()
    print("PASS test_doctor_uses_raw_names_and_reports_scope")


async def test_capacity_panel_shares_process_count() -> None:
    await reset_database()
    observability.reset_counters()
    observability.count("webhook.main", 4)
    async with session_scope() as session:
        await capacity_service.publish_counters(session)
        session.add(
            RuntimeCounterSnapshot(
                process_key="second-worker:9", hostname="second", counters=json.dumps({"telegram.send": 3}),
                updated_at=dt.datetime.now(UTC),
            )
        )
        await session.commit()
        snapshot = await capacity_service.snapshot(session)
    body = texts.capacity_text(snapshot)
    assert "جمعِ شمارنده‌ها از ۲ پروسهٔ زنده" in body, body[-500:]
    assert "رویدادِ رباتِ مرکزی: ۴" in body, body[-500:]

    # پروسهٔ بی‌ضربان هم باید در همان خط صادقانه اعلام شود (کم‌گوییِ پنهان نه)
    async with session_scope() as session:
        row = (
            await session.execute(select(RuntimeCounterSnapshot).where(RuntimeCounterSnapshot.process_key == "second-worker:9"))
        ).scalar_one()
        row.updated_at = dt.datetime.now(UTC) - dt.timedelta(hours=2)
        await session.commit()
        snapshot2 = await capacity_service.snapshot(session)
    body2 = texts.capacity_text(snapshot2)
    assert "پروسهٔ بی‌ضربان شمرد نشد" in body2, body2[-500:]
    observability.reset_counters()
    print("PASS test_capacity_panel_shares_process_count")


async def main() -> None:
    test_local_counters_keep_raw_names()
    test_process_key_shape()
    await test_publish_is_upsert_and_aggregate_sums_processes()
    await test_stale_and_broken_rows_are_excluded()
    await test_doctor_uses_raw_names_and_reports_scope()
    await test_capacity_panel_shares_process_count()


if __name__ == "__main__":
    asyncio.run(main())
