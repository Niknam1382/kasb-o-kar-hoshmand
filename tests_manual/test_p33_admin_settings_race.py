"""
تست: P33-1 — اولینِ خواندنِ `admin_settings` زیرِ دو جریانِ هم‌زمان نباید بشکند

باگِ واقعی (MEASURED ۱۴۰۵-۰۸-۱۳ در بازاجرایِ test_checkout_c3 با FSM_STORAGE=postgres):
`get_admin_settings` اگر ردیفِ id=1 را نبود ببیند خودش می‌ساخت؛ دو تسکِ هم‌زمان هر دو «نبود»
را می‌دیدند و هر دو INSERT می‌زدند ⇒ رویِ دومی
`UniqueViolationError: duplicate key value violates unique constraint "pk_admin_settings"`.
این ربطی به FSM ندارد: هر دو جریانِ هم‌زمانِ اولِ بعدِ reset (یا بعدِ ساختِ دیتابیسِ تازه) همین
می‌خورند. رفع: درج داخلِ savepoint + خواندنِ دوباره، و اگر رقیب rollback کرده بود درجِ خودمان.

سه قفلِ این فایل:
۱. مکانیزمِ رفع به‌طورِ قطعی: درجِ تکراری داخلِ savepoint رد می‌شود و همان تراکنش
   زنده می‌ماند و نوشتنش ذخیره می‌شود (تستِ ۴). بدونِ savepoint همان IntegrityError
   کلِ تراکنشِ خواننده را می‌کشد.
۲. شش خواندنِ هم‌زمان رویِ جدولِ خالی ⇒ بی‌خطا و دقیقاً یکِ ردیف (صاحبِ این تست
   قائلهٔ race را نشان می‌دهد، ولی با کدِ کهنه هم پاس شد؛ یعنی این شش‌جانبه برایِ
   بازتولیدِ باگ کافی نبود — ادعایِ «باگ را می‌گیرد» فقط رویِ تستِ ۴ است).
۳. ردیفِ برگشتی به ORM چسبیده است (نوشتن ذخیره می‌شود) و مسیرِ کش‌شده هم ردیف می‌سازد.

اجرا: python3 tests_manual/run_one.py test_p33_admin_settings_race.py
"""
from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import delete, func, select  # noqa: E402

from harness import reset_database  # noqa: E402

from app.database.models import AdminSettings  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import admin_settings_service  # noqa: E402

READERS = 6


async def _empty_settings_table() -> None:
    async with session_scope() as session:
        await session.execute(delete(AdminSettings))
        await session.commit()


async def _read_once() -> int:
    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        return int(row.id)


async def test_concurrent_first_reads_create_exactly_one_row() -> None:
    await reset_database()
    admin_settings_service.reset_read_cache()
    await _empty_settings_table()

    results = await asyncio.gather(*[_read_once() for _ in range(READERS)], return_exceptions=True)
    errors = [r for r in results if isinstance(r, BaseException)]
    assert not errors, f"خواندنِ هم‌زمان شکست خورد: {errors[0]!r}"
    assert set(results) == {1}, f"همه باید همان ردیفِ id=1 را می‌دیدند؛ شد {set(results)}"

    async with session_scope() as session:
        count = await session.scalar(select(func.count()).select_from(AdminSettings))
    assert count == 1, f"انتظارِ یکِ ردیفِ تنظیمات داشتیم؛ شد {count}"
    print("✅ test_concurrent_first_reads_create_exactly_one_row PASSED")


async def test_created_row_is_writable_and_persists() -> None:
    await reset_database()
    admin_settings_service.reset_read_cache()
    await _empty_settings_table()

    async with session_scope() as session:
        row = await admin_settings_service.get_admin_settings(session)
        row.maintenance_mode = True
        row.nightly_report_hour_utc = 5
        await session.commit()

    async with session_scope() as session:
        fresh = await session.get(AdminSettings, 1)
    assert fresh.maintenance_mode is True and fresh.nightly_report_hour_utc == 5, (
        "ردیفِ ساخته‌شده باید به ORM چسبیده باشد تا نوشتن رویِ آن ذخیره شود"
    )
    print("✅ test_created_row_is_writable_and_persists PASSED")


async def test_cached_reader_also_creates_the_row() -> None:
    await reset_database()
    admin_settings_service.reset_read_cache()
    await _empty_settings_table()

    async with session_scope() as session:
        row = await admin_settings_service.cached_admin_settings(session)
    assert row.id == 1 and row.maintenance_mode is False

    async with session_scope() as session:
        count = await session.scalar(select(func.count()).select_from(AdminSettings))
    assert count == 1, "مسیرِ کش‌شده هم باید همان ردیف را بسازد، نه اینکه بی‌صدا شکست بخورد"
    print("✅ test_cached_reader_also_creates_the_row PASSED")


async def test_savepoint_contains_the_conflict_and_keeps_the_transaction_usable() -> None:
    """اثباتِ قطعیِ مکانیزمِ رفع (این با شش جریانِ هم‌زمان تضمینی نیست).

    ردیفِ id=1 از بیرون موجود و commit شده است؛ اگر درجِ دوباره بدونِ savepoint امتحان شود،
    IntegrityError کلِ تراکنشِ خواننده را می‌کشد. با savepoint فقط درجِ بی‌مصرف برمی‌گردد و
    همان تراکنش هنوز می‌تواند بنویسد و commit کند.
    """
    from sqlalchemy.exc import IntegrityError

    await reset_database()
    admin_settings_service.reset_read_cache()
    async with session_scope() as session:
        await admin_settings_service.get_admin_settings(session)

    raised = False
    async with session_scope() as session:
        try:
            async with session.begin_nested():
                session.add(AdminSettings(id=1))
        except IntegrityError:
            raised = True
        fresh = await session.get(AdminSettings, 1, populate_existing=True)
        fresh.nightly_report_hour_utc = 7
        await session.commit()

    assert raised, "درجِ تکراری باید داخلِ savepoint رد شود"
    async with session_scope() as session:
        row = await session.get(AdminSettings, 1)
    assert row.nightly_report_hour_utc == 7, "تراکنشِ اصلی نباید با خطایِ درج بمیرد"
    print("✅ test_savepoint_contains_the_conflict_and_keeps_the_transaction_usable PASSED")


async def test_stale_read_recovers_instead_of_crashing() -> None:
    """تستِ بازتولیدِ باگ: اگر جریانی ردیف را «هنوز نیست» ببیند و تا لحظۀ درج ساخته شود.

    زمانِ واقعیِ race را نمی‌توان تضمینی درآورد (شش جریانِ هم‌زمان هم با کدِ کهنه پاس شد)،
    پس همین حالتِ «دیدنِ کهنه» صریح شبیه‌سازی می‌شود: اولین session.get بی‌مقدار برمی‌گردد.
    با کدِ کهنه اینجا UniqueViolationErrorِ pk_admin_settings می‌آید؛ با رفع، همان ردیف
    خوانده می‌شود. (منفی‌سنجی شده: see TEST_RESULTS §۲۲.)
    """
    from sqlalchemy.ext.asyncio import AsyncSession as _AS

    await reset_database()
    admin_settings_service.reset_read_cache()
    await _empty_settings_table()
    async with session_scope() as session:  # یکِ خوانندهٔ عادی ردیف را می‌سازد
        await admin_settings_service.get_admin_settings(session)

    original_get = _AS.get
    calls = {"n": 0}

    async def stale_get(self, entity, ident, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            return None
        return await original_get(self, entity, ident, **kw)

    _AS.get = stale_get
    try:
        async with session_scope() as session:
            row = await admin_settings_service.get_admin_settings(session)
    finally:
        _AS.get = original_get

    assert int(row.id) == 1 and calls["n"] >= 2, f"باید از دیدنِ کهنه بازیابی می‌شد؛ شد {row}"
    print("✅ test_stale_read_recovers_instead_of_crashing PASSED")


async def main() -> None:
    await test_concurrent_first_reads_create_exactly_one_row()
    await test_created_row_is_writable_and_persists()
    await test_cached_reader_also_creates_the_row()
    await test_savepoint_contains_the_conflict_and_keeps_the_transaction_usable()
    await test_stale_read_recovers_instead_of_crashing()


if __name__ == "__main__":
    asyncio.run(main())
