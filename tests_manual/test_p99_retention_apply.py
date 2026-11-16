"""پ۹۹ · قفل‌ها و پنجره‌هایِ **سفارشیِ هرِ جدول** در اسکریپتِ نگهداریِ داده.

چهار ادعا (هیچ‌کدام با دادهٔ واقعیِ مالک، همه رویِ `kasbokar_test`):
۱. dry-run (حالتِ پیش‌فرض): ردیف‌هایِ پیر فقط *شمرده* می‌شوند و صفر ردیف حذف می‌شود.
۲. `apply=True` بدونِ عبارتِ تایید **یا** بدونِ اذعانِ بکاپ ⇒ کدِ ۲ و صفر حذف (قاعدهٔ ۳).
۳. با هر سه شرط: ردیف‌هایِ بیرونِ پنجره می‌روند، ردیف‌هایِ تازه می‌مانند، تاریخچهٔ چت بی‌`include_chat`
   دست‌نخورده می‌ماند و یکِ ردیفِ ممیزی با تعدادِ پاک‌شده‌ها ثبت می‌شود (قاعدهٔ ۷: قابلِ دفاع).
۴. دفترِ ممیزی پیش‌فرض ۰ روز است ⇒ زنجیرهٔ هشِ آن هرگز با اجرایِ معمولی قطع نمی‌شود؛ پنجرهٔ ۰ یعنی
   «دست مزن» و `_targets` آن را حذف می‌کند.

اجرا: python3 tests_manual/run_one.py test_p99_retention_apply.py
"""
from __future__ import annotations

import asyncio
import datetime as dt
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tests_manual")

from sqlalchemy import func, select  # noqa: E402

from app.database.models import (  # noqa: E402
    AuditEventType,
    AuditLogEntry,
    ConversationMessage,
    Customer,
    InstagramCommentEvent,
    PaymentEventLog,
    RuntimeCounterSnapshot,
)
from app.database.session import session_scope  # noqa: E402
from app.services import audit_log_service  # noqa: E402
from harness import reset_database  # noqa: E402
from scripts import data_retention_apply as retention  # noqa: E402
from shop_setup import seed_usable_shop  # noqa: E402

OWNER_TG_ID = 9_900_000_001
SHOP_BOT_TG_ID = 9_900_000_002
SHOP_ID = 0
WINDOWS = {"payments": 365, "audit": 0, "ig": 180, "counters": 7, "chat": 365}


def _ago(days: int) -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)


async def _seed() -> None:
    """سه ردیفِ پیر + سه ردیفِ تازه در چهار جدول + دو ردیفِ گفتگو (یکی پیر، یکی تازه)."""
    global SHOP_ID
    await reset_database()
    SHOP_ID = await seed_usable_shop(OWNER_TG_ID, SHOP_BOT_TG_ID)
    async with session_scope() as session:
        for days in (500, 400, 10):
            session.add(PaymentEventLog(provider="bale", direction="out", method="createInvoiceLink", created_at=_ago(days)))
        for days in (300, 200, 5):
            session.add(
                InstagramCommentEvent(
                    shop_bot_id=SHOP_ID, comment_id=f"c{days}", text="سلام", outcome="received", created_at=_ago(days)
                )
            )
        for days in (30, 2):
            session.add(
                RuntimeCounterSnapshot(process_key=f"pid-{days}", hostname="test", counters="{}", updated_at=_ago(days))
            )
        customer = Customer(shop_bot_id=SHOP_ID, telegram_id=9_900_000_003, first_name="مشتری")
        session.add(customer)
        await session.flush()
        for days in (500, 3):
            session.add(ConversationMessage(customer_id=customer.id, role="user", content="سلام", created_at=_ago(days)))
        await audit_log_service.log(session, AuditEventType.ADMIN_SETTING_CHANGED, details="ردیفِ ممیزیِ پیرِ ساختگی")
        old_audit = (await session.execute(select(AuditLogEntry).order_by(AuditLogEntry.id.desc()))).scalars().first()
        old_audit.created_at = _ago(900)
        await session.commit()


async def _counts() -> dict[str, int]:
    async with session_scope() as session:
        out = {}
        for key, (_label, model) in {
            "payments": ("", PaymentEventLog),
            "ig": ("", InstagramCommentEvent),
            "counters": ("", RuntimeCounterSnapshot),
            "chat": ("", ConversationMessage),
            "audit": ("", AuditLogEntry),
        }.items():
            out[key] = (await session.execute(select(func.count()).select_from(model))).scalar_one()
        return out


# ============================================================================= ۱
async def test_dry_run_deletes_nothing() -> None:
    await _seed()
    before = await _counts()
    code = await retention.run(WINDOWS, apply=False, confirm="", backup_ok=False, include_chat=False)
    assert code == 0, code
    assert await _counts() == before, "dry-run نباید یکِ ردیف هم کم کند"
    print("PASS test_dry_run_deletes_nothing")


# ============================================================================= ۲
async def test_missing_guards_block_deletion() -> None:
    await _seed()
    before = await _counts()
    assert await retention.run(WINDOWS, apply=True, confirm="", backup_ok=True, include_chat=True) == 2
    assert await _counts() == before, "بدونِ عبارتِ تایید ⇒ صفر حذف"
    assert await retention.run(WINDOWS, apply=True, confirm=retention.CONFIRM_PHRASE, backup_ok=False, include_chat=True) == 2
    assert await _counts() == before, "بدونِ اذعانِ بکاپ ⇒ صفر حذف"
    assert await retention.run(
        {"payments": 0, "audit": 0, "ig": 0, "counters": 0, "chat": 0}, apply=True, confirm=retention.CONFIRM_PHRASE, backup_ok=True, include_chat=True
    ) == 0, "همه صفر ⇒ هیچ هدفی، کدِ ۰ و صفر حذف"
    assert await _counts() == before
    print("PASS test_missing_guards_block_deletion")


# ============================================================================= ۳ و ۴
async def test_full_apply_honours_per_table_windows() -> None:
    await _seed()
    audit_before = (await _counts())["audit"]
    code = await retention.run(
        WINDOWS, apply=True, confirm=retention.CONFIRM_PHRASE, backup_ok=True, include_chat=False
    )
    assert code == 0, code
    after = await _counts()
    assert after["payments"] == 1, after  # فقطِ ۱۰ روزه می‌ماند (۵۰۰ و ۴۰۰ بیرونِ ۳۶۵)
    assert after["ig"] == 1, after  # ۳۰۰ و ۲۰۰ بیرونِ ۱۸۰
    assert after["counters"] == 1, after  # ۳۰ روزه بیرونِ ۷
    assert after["chat"] == 2, "تاریخچهٔ چت بدونِ include_chat دست‌نخورده می‌ماند"
    assert after["audit"] == audit_before + 1, "فقطِ ردیفِ تازهٔ ممیزی افزوده می‌شود؛ ردیفِ کهنه نمی‌رود"
    async with session_scope() as session:
        aged = (
            await session.execute(
                select(func.count()).select_from(AuditLogEntry).where(AuditLogEntry.created_at < _ago(365))
            )
        ).scalar_one()
        assert aged == 1, f"پنجرهٔ ۰ ⇒ ردیفِ ۹۰۰ روزهٔ ممیزی (و زنجیرهٔ هشش) باید بماند، نه اینکه {aged} تا باشد"
    async with session_scope() as session:
        rows = list(
            (
                await session.execute(select(AuditLogEntry).where(AuditLogEntry.event_type == AuditEventType.RETENTION_APPLIED))
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1, rows
        assert "payments=2" in rows[0].details and "ig=2" in rows[0].details and "جمع=5" in rows[0].details, rows[0].details
    print("PASS test_full_apply_honours_per_table_windows")


async def test_chat_window_only_when_asked() -> None:
    await _seed()
    assert await retention.run(
        WINDOWS, apply=True, confirm=retention.CONFIRM_PHRASE, backup_ok=True, include_chat=True
    ) == 0
    after = await _counts()
    assert after["chat"] == 1, after  # ۵۰۰ روزه بیرونِ ۳۶۵ رفت، ۳ روزه ماند
    print("PASS test_chat_window_only_when_asked")


async def main() -> None:
    await test_dry_run_deletes_nothing()
    await test_missing_guards_block_deletion()
    await test_full_apply_honours_per_table_windows()
    await test_chat_window_only_when_asked()


if __name__ == "__main__":
    asyncio.run(main())
