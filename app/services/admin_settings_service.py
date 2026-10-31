from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AdminSettings


async def get_admin_settings(session: AsyncSession) -> AdminSettings:
    settings_row = await session.get(AdminSettings, 1)
    if settings_row is None:
        settings_row = AdminSettings(id=1)
        session.add(settings_row)
        await session.flush()
    return settings_row


async def update_setting(session: AsyncSession, field_name: str, value: Any) -> AdminSettings:
    settings_row = await get_admin_settings(session)
    setattr(settings_row, field_name, value)
    await session.flush()
    return settings_row
