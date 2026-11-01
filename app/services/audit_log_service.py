"""گزارشِ ممیزی با زنجیرهٔ هش (P20).

هر ردیفِ تازه، هشِ ردیفِ قبل از خود (`prev_hash`) و هشِ خود (`row_hash`) را نگه می‌دارد:

    row_hash = sha256(prev_hash + شناسه + زمان + نوع + فروشگاه + عامل + جزئیات)

پس حذف یا تغییرِ داده‌یِ یک رویدادِ قدیمی (که someone می‌تواند فقط با دسترسی به دیتابیس انجام دهد)
زنجیره را می‌شکند و با `python scripts/verify_audit_chain.py` قابلِ کشف است. ردیف‌هایِ قدیمیِ
پیش ازِ P20 هش ندارند و زنجیره از اولین ردیفِ هش‌دار شروع می‌شود (بی‌خطر، بدونِ بازنویسیِ تاریخچه).

هم‌زمانی: دو درجِ هم‌زمان می‌توانند «پیشین» یکسانی ببینند ⇒ حلقه از همسایهٔ مستقیم رد می‌شود.
بازبینی این حالت را *پیوندِ ناهمسایه* می‌شمارد نه تحریف، چون هشِ ذخیره‌شده به ردیفِ واقعیِ دیگری
می‌رسد. تحریف فقط وقتی گزارش می‌شود که هیچ ردیفِ قدیمی‌تری با آن هش وجود نداشته باشد.
"""

from __future__ import annotations

import hashlib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditEventType, AuditLogEntry

GENESIS = "0" * 64


def canonical_payload(entry: AuditLogEntry) -> str:
    """رشته‌یِ پایهیِ هر بازبین: هرچه در ستون‌ها هست، به ترتیبِ ثابت."""
    created = entry.created_at.isoformat() if entry.created_at is not None else ""
    event = getattr(entry.event_type, "value", entry.event_type) or ""
    return "|".join(
        [
            str(entry.id),
            created,
            str(event),
            str(entry.shop_bot_id if entry.shop_bot_id is not None else ""),
            str(entry.actor_telegram_id if entry.actor_telegram_id is not None else ""),
            entry.details or "",
        ]
    )


def compute_hash(prev_hash: str, entry: AuditLogEntry) -> str:
    return hashlib.sha256(f"{prev_hash}{canonical_payload(entry)}".encode("utf-8")).hexdigest()


async def _last_hash_before(session: AsyncSession, entry_id: int) -> str:
    result = await session.execute(
        select(AuditLogEntry.row_hash)
        .where(AuditLogEntry.id < entry_id, AuditLogEntry.row_hash.is_not(None))
        .order_by(AuditLogEntry.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none() or GENESIS


async def log(
    session: AsyncSession,
    event_type: AuditEventType,
    shop_bot_id: int | None = None,
    actor_telegram_id: int | None = None,
    details: str | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(event_type=event_type, shop_bot_id=shop_bot_id, actor_telegram_id=actor_telegram_id, details=details)
    session.add(entry)
    await session.flush()  # id و created_at (server_default) این‌جا پر می‌شوند
    entry.prev_hash = await _last_hash_before(session, entry.id)
    entry.row_hash = compute_hash(entry.prev_hash, entry)
    await session.flush()
    return entry


async def get_recent(session: AsyncSession, limit: int = 20, shop_bot_id: int | None = None) -> list[AuditLogEntry]:
    query = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(limit)
    if shop_bot_id is not None:
        query = query.where(AuditLogEntry.shop_bot_id == shop_bot_id)
    result = await session.execute(query)
    return list(result.scalars().all())
