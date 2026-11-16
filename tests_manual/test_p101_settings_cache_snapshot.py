"""پ۱۰۱ · کشِ تنظیمات حالا **مقدار** نگه می‌دارد، نه ردیفِ ORMِ مرده.

زمینه از پ۹۶: در فایل‌هایی که اپِ ASGI را مستقیم صدا می‌زنند `SAWarning: non-checked-in connection` و
بعد `greenlet is being finalized` دیده می‌شد. فرضِ پ۹۶ (کشِ ORM) اینجا رفع شد — کشِ
`admin_settings_service.cached_admin_settings` به‌جایِ `expunge` کردنِ ردیف، کپیِ مقدار در یکِ شیءِ آزاد
می‌سازد — ولی در پ۱۰۱ ثابت شد این **علتِ نویز نبود**؛ علتِ واقعی (نشتِ اتصالِ «idle in transaction» در
`_ops_status_json`) در پ۱۰۴ پیدا و رفع شد و از آن پس همان سه فایلِ HTTP صفر warning می‌دهند.
این فایل پس ازِ پ۱۰۴ یعنی: «کشِ مقدار، کوئریِ صفر در خواندنِ گرم، و نشکستنِ `/ops/status` رویِ استخرِ
بدونِ `checkedout`». چهار چیز قفل می‌شود که با بازنویسیِ تصادفی نمی‌شکند:

۱. شیءِ کش‌شده به هیچ سشنی وصل نیست و هیچ فیلدِ «بارگذاری‌نشده» ندارد ⇒ خواندنش هرگز IO نمی‌زند.
۲. دومینِ خواندن (در سشنِ جدا) صفر SELECT رویِ `admin_settings` است ⇒ همان سودِ P31 سرِ جایش است.
۳. نوشتن از مسیرِ درست (`update_setting` + flush) کش را باطل می‌کند و مقدارِ تازه دیده می‌شود.
۴. بعد ازِ بسته‌شدنِ سشنِ سازنده، خواندنِ فیلدها بی‌خطا است (با ORMِ detachedِ قدیمی این همان
   جایی بود که یا DetachedInstanceError می‌داد یا اتصالِ مرده را زنده می‌کرد).

اجرا: python3 tests_manual/run_one.py test_p101_settings_cache_snapshot.py
"""
from __future__ import annotations

import asyncio
import contextlib
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import event, inspect as sa_inspect  # noqa: E402

from app.database.session import engine, session_scope  # noqa: E402
from app.services import admin_settings_service as svc  # noqa: E402
from harness import reset_database  # noqa: E402


@contextlib.contextmanager
def counted() -> list[str]:
    seen: list[str] = []

    def listener(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001, ARG002
        seen.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", listener)
    try:
        yield seen
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", listener)


def _admin_selects(statements: list[str]) -> int:
    return sum(1 for s in statements if "admin_settings" in " ".join(s.split()).lower())


# ============================================================================= ۱ و ۴
async def test_cached_object_holds_values_not_a_dead_connection() -> None:
    await reset_database()
    async with session_scope() as session:
        snapshot = await svc.cached_admin_settings(session)
    state = sa_inspect(snapshot, raiseerr=False)
    assert state is not None
    assert state.session_id is None, "کشِ تنظیمات نباید به هیچ سشنی وصل باشد"
    assert not state.unloaded, f"هیچ فیلدی بارگذاری‌نشده نمانده باشد: {sorted(state.unloaded)}"
    # سشن بسته شده؛ خواندنِ فیلدها باید محضِ حافظه باشد (نه IO، نه خطا):
    value = snapshot.min_topup_amount_toman
    assert isinstance(value, int), value
    print("PASS test_cached_object_holds_values_not_a_dead_connection")


# ============================================================================= ۲
async def test_second_read_is_zero_statements() -> None:
    await reset_database()
    async with session_scope() as session:
        await svc.get_admin_settings(session)  # ساختِ ردیف بیرون ازِ بلوکِ شمارش (واریزِ یک‌باره، نه هزینهٔ هر خواندن)
        await session.commit()
    svc.reset_read_cache()
    with counted() as seen:
        async with session_scope() as session:
            await svc.cached_admin_settings(session)
        first = _admin_selects(seen)
        seen.clear()
        async with session_scope() as session:
            again = await svc.cached_admin_settings(session)
        second = _admin_selects(seen)
    assert first == 1, first
    assert second == 0, second
    assert again.min_topup_amount_toman == 50_000, again.min_topup_amount_toman
    print("PASS test_second_read_is_zero_statements")


# ============================================================================= ۳
async def test_write_through_service_invalidates_cache() -> None:
    await reset_database()
    async with session_scope() as session:
        await svc.cached_admin_settings(session)
    async with session_scope() as session:
        await svc.update_setting(session, "min_topup_amount_toman", 75_000)
        await session.commit()
    async with session_scope() as session:
        fresh = await svc.cached_admin_settings(session)
    assert fresh.min_topup_amount_toman == 75_000, fresh.min_topup_amount_toman
    print("PASS test_write_through_service_invalidates_cache")


# ============================================================================= ۵
async def test_capacity_survives_a_pool_without_counters() -> None:
    """پ۱۰۱: استخرِ بدونِ `checkedout()` (مثلِ NullPool) نباید `/ops/status` را بترکاند."""
    from types import SimpleNamespace

    from app.services import capacity_service

    real_engine = capacity_service.engine
    # استخری مثلِ NullPool: فقط `size` دارد و `checkedout()` / `overflow()` ندارد.
    capacity_service.engine = SimpleNamespace(sync_engine=SimpleNamespace(pool=SimpleNamespace(size=lambda: 0)))
    try:
        lines = capacity_service.db_pool_lines()
    finally:
        capacity_service.engine = real_engine
    assert lines["mode"] == "null", lines
    assert lines["capacity"] == 1 and lines["percent"] == 0.0, lines
    from app.bots.main_bot import texts

    snapshot = {
        "ai": {"inflight_total": 0, "usable": 10, "percent": 0.0, "keys": 0, "bottleneck": "platform",
               "sum_caps": 10, "platform_ceiling": 10, "voice": {"count": 0, "inflight": 0, "sum_caps": 0}},
        "db": lines,
        "system": {"cores": 1, "load1": None, "load_percent": 0.0, "memory_used_percent": None,
                   "disk_used_percent": None, "disk_label": "/"},
        "counters": [], "processes": 1, "stale_processes": 0,
    }
    rendered = texts.capacity_text(snapshot)
    assert "بدونِ استخر" in rendered, rendered[:400]
    print("PASS test_capacity_survives_a_pool_without_counters")


async def main() -> None:
    await test_cached_object_holds_values_not_a_dead_connection()
    await test_second_read_is_zero_statements()
    await test_write_through_service_invalidates_cache()
    await test_capacity_survives_a_pool_without_counters()


if __name__ == "__main__":
    asyncio.run(main())
