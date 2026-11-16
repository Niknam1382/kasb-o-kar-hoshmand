"""پ۱۰۲ · مُهرِ سرِ زنجیره وقتی پنجرهٔ ممیزی ردیف‌هایِ کهنه را می‌بَرد.

سیاستِ مالک: ممیزی ۱۸۲۵ روز. ولی هر ردیفِ ممیزی به هشِ ردیفِ قبل چسبیده (`prev_hash`) ⇒ حذفِ ابتدایِ
زنجیره دو حالت دارد: یا بازبینِ زنجیره آن را «تحریف» می‌خواند (که نادرست است، چون خودِ سیستم این حذف را
انجام داده) یا همه‌چیز را قابلِ هر حذفی می‌کند (که خطرناک است). راهِ درست: **مُهر**. پیش ازِ حذف، یکِ
ردیفِ ممیزی با `audit_head_prev=<hashِ آخرین ردیفِ حذفی>` نوشته می‌شود؛ بازبین فقط سرِ بریده‌ای را می‌پذیرد
که مُهرش در همین جدول باشد. سه ادعا:

۱. پیش‌فرض‌ها همان عددِ مالک است (۷۳۰ / ۱۸۲۵ / ۳۶۵ / ۷ / ۳۶۵) و دو اسکریپت یکِ پیشوندِ مُهر دارند.
۲. بعد ازِ حذفِ مجازِ ممیزی، `verify_audit_chain.verify()` ⇒ ۰ و خطِ «سرِ بریده با مُهرِ نگهداری» هست.
۳. حذفِ بی‌مُهرِ همان ابتدایِ زنجیره (شبیه‌سازیِ دسترسیِ مستقیم به DB) ⇒ ۱ و «prev_hash به هیچ ردیفِ
   معتبری نمی‌رسد».

اجرا: python3 tests_manual/run_one.py test_p102_audit_trim_seal.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import io
import sys
from contextlib import redirect_stdout

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import delete, func, select  # noqa: E402

from app.database.models import AuditEventType, AuditLogEntry, PaymentEventLog  # noqa: E402
from app.database.session import session_scope  # noqa: E402
from app.services import audit_log_service  # noqa: E402
from app.services.audit_log_service import GENESIS, compute_hash  # noqa: E402
from harness import reset_database  # noqa: E402
from scripts import data_retention_apply as retention  # noqa: E402
from scripts import verify_audit_chain as verifier  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 10_200_000_001
SHOP_BOT_TG_ID = 10_200_000_002
GUARDS = {"apply": True, "confirm": retention.CONFIRM_PHRASE, "backup_ok": True}


def _ago(days: int) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)


async def _seed(days: int, events: int) -> None:
    await reset_database()
    await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        for index in range(events):
            await audit_log_service.log(session, AuditEventType.ADMIN_SETTING_CHANGED, details=f"ردیفِ {index}")
            moment = _ago(days) if index < events // 2 else _ago(1)
            entry = (await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.id.desc()))).scalars().first()
            # سیدِ تاریخِ گذشته: چون `row_hash` خودِ ستونِ زمان را هم می‌پوشاند، پس ازِ تنظیمِ created_at
            # هشِ ردیف را دوباره می‌سازیم (ساختِ تاریخچهٔ معتبر، نه تحریفِ تاریخچهٔ موجود).
            entry.created_at = moment
            entry.row_hash = compute_hash(entry.prev_hash or GENESIS, entry)
            session.add(PaymentEventLog(provider="bale", direction="out", method="x", created_at=_ago(days + 400)))
        await session.commit()


async def _audit_count() -> int:
    async with session_scope() as session:
        return (await session.execute(select(func.count()).select_from(AuditLogEntry))).scalar_one()


# ============================================================================= ۱
async def test_owner_windows_and_shared_seal_prefix() -> None:
    defaults = {key: days for key, _label, _m, _c, days in retention.TABLES}
    assert defaults == {"payments": 730, "audit": 1825, "ig": 365, "counters": 7, "chat": 365}, defaults
    assert verifier.AUDIT_SEAL_PREFIX == retention.SEAL_PREFIX, (verifier.AUDIT_SEAL_PREFIX, retention.SEAL_PREFIX)
    print("PASS test_owner_windows_and_shared_seal_prefix")


# ============================================================================= ۲
async def test_trim_with_seal_keeps_chain_verifiable() -> None:
    await _seed(days=2_000, events=6)
    before = await _audit_count()
    assert before == 6, before
    assert await verifier.verify(None) == 0, "پیش ازِ حذف، زنجیره سالم است"

    windows = {"payments": 0, "audit": 30, "ig": 0, "counters": 0, "chat": 0}
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = await retention.run(windows, include_chat=False, **GUARDS)
    assert code == 0, buffer.getvalue()
    after = await _audit_count()
    assert after < before, (before, after)
    async with session_scope() as session:
        seals = list(
            (
                await session.execute(
                    select(AuditLogEntry.details).where(
                        AuditLogEntry.event_type == AuditEventType.RETENTION_APPLIED,
                        AuditLogEntry.details.like(f"%{retention.SEAL_PREFIX}%"),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(seals) == 1, seals
        assert f"{retention.SEAL_PREFIX}" in seals[0] and "audit_first_alive_id=" in seals[0], seals[0]
    buffer2 = io.StringIO()
    with redirect_stdout(buffer2):
        assert await verifier.verify(None) == 0, buffer2.getvalue()
    assert "سرِ بریده با مُهرِ نگهداری" in buffer2.getvalue(), buffer2.getvalue()
    print("MEASURED بازبینِ پس ازِ حذف:", " ".join(buffer2.getvalue().split()))
    print("PASS test_trim_with_seal_keeps_chain_verifiable")


# ============================================================================= ۳
async def test_head_removal_without_seal_is_broken() -> None:
    await _seed(days=10, events=5)
    async with session_scope() as session:
        oldest = (
            await session.execute(select(AuditLogEntry.id).order_by(AuditLogEntry.id).limit(1))
        ).scalar_one()
        await session.execute(delete(AuditLogEntry).where(AuditLogEntry.id == oldest))
        await session.commit()
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = await verifier.verify(None)
    assert code == 1, buffer.getvalue()
    assert "prev_hash به هیچ ردیفِ معتبری نمی‌رسد" in buffer.getvalue(), buffer.getvalue()
    print("PASS test_head_removal_without_seal_is_broken")


async def main() -> None:
    await test_owner_windows_and_shared_seal_prefix()
    await test_trim_with_seal_keeps_chain_verifiable()
    await test_head_removal_without_seal_is_broken()


if __name__ == "__main__":
    asyncio.run(main())
