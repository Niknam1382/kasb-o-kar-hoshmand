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


# =============================================================================
# P21-E (F8): دامنهٔ دسترسیِ ادمینِ عملیاتی رویِ فروشگاه‌دارها
# =============================================================================
def parse_owner_ids(raw: str | None) -> set[int] | None:
    """None ⇒ «بدونِ محدودیت». فهرستِ کاماجدا ⇒ مجموعهٔ شناسه‌ها."""
    if raw is None or not str(raw).strip():
        return None
    return {int(part) for part in str(raw).split(",") if part.strip().lstrip("-").isdigit()}


def allowed_owner_ids(role: AdminRole | None) -> set[int] | None:
    return None if role is None else parse_owner_ids(role.allowed_owner_ids)


async def scope_for(session: AsyncSession, telegram_id: int) -> set[int] | None:
    return allowed_owner_ids(await get_by_telegram_id(session, telegram_id))


def is_in_scope(scope: set[int] | None, owner_id: int) -> bool:
    return scope is None or int(owner_id) in scope


async def can_touch_owner(session: AsyncSession, telegram_id: int, owner_id: int) -> bool:
    """سوپرادمین‌ها از ADMIN_TELEGRAM_IDS می‌آیند (نه این جدول) و محدودیتِ دامنه ندارند."""
    return is_in_scope(await scope_for(session, telegram_id), owner_id)


async def set_scope(session: AsyncSession, role: AdminRole, owner_ids: list[int] | None) -> AdminRole:
    role.allowed_owner_ids = None if not owner_ids else ",".join(str(int(pk)) for pk in sorted(set(owner_ids)))
    await session.flush()
    return role
