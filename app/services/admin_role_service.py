from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminRole, AdminRoleType


async def get_all(session: AsyncSession) -> list[AdminRole]:
    result = await session.execute(select(AdminRole).order_by(AdminRole.id))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, role_id: int) -> AdminRole | None:
    return await session.get(AdminRole, role_id)


async def get_by_telegram_id(session: AsyncSession, telegram_id: int) -> AdminRole | None:
    result = await session.execute(select(AdminRole).where(AdminRole.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def is_operator(session: AsyncSession, telegram_id: int) -> bool:
    return await get_by_telegram_id(session, telegram_id) is not None


async def grant_operator(session: AsyncSession, telegram_id: int, granted_by_telegram_id: int) -> AdminRole:
    role = AdminRole(
        telegram_id=telegram_id,
        role=AdminRoleType.OPERATOR,
        granted_by_telegram_id=granted_by_telegram_id,
    )
    session.add(role)
    await session.flush()
    return role


async def revoke(session: AsyncSession, role: AdminRole) -> None:
    await session.delete(role)
    await session.flush()
