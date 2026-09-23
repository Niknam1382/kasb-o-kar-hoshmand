from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditEventType, AuditLogEntry


async def log(
    session: AsyncSession,
    event_type: AuditEventType,
    shop_bot_id: int | None = None,
    actor_telegram_id: int | None = None,
    details: str | None = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(event_type=event_type, shop_bot_id=shop_bot_id, actor_telegram_id=actor_telegram_id, details=details)
    session.add(entry)
    await session.flush()
    return entry


async def get_recent(session: AsyncSession, limit: int = 20, shop_bot_id: int | None = None) -> list[AuditLogEntry]:
    query = select(AuditLogEntry).order_by(AuditLogEntry.id.desc()).limit(limit)
    if shop_bot_id is not None:
        query = query.where(AuditLogEntry.shop_bot_id == shop_bot_id)
    result = await session.execute(query)
    return list(result.scalars().all())
