from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MandatoryChannel

logger = logging.getLogger(__name__)


def _chat_id_arg(channel_id: str) -> str | int:
    stripped = channel_id.strip()
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    return stripped


async def get_missing_channels(bot: Bot, channels: list[MandatoryChannel], user_id: int) -> list[MandatoryChannel]:
    missing = []
    for channel in channels:
        try:
            member = await bot.get_chat_member(_chat_id_arg(channel.channel_id), user_id)
            if member.status in ("left", "kicked"):
                missing.append(channel)
        except TelegramAPIError:
            logger.warning("چک کردنِ عضویتِ کاربر %s در کانال %s ناموفق بود.", user_id, channel.channel_id)
            missing.append(channel)
    return missing


async def get_mandatory_channels(session: AsyncSession) -> list[MandatoryChannel]:
    result = await session.execute(select(MandatoryChannel).order_by(MandatoryChannel.is_primary.desc(), MandatoryChannel.id))
    return list(result.scalars().all())


async def get_by_id(session: AsyncSession, channel_id: int) -> MandatoryChannel | None:
    return await session.get(MandatoryChannel, channel_id)


async def get_primary_channel(session: AsyncSession) -> MandatoryChannel | None:
    result = await session.execute(select(MandatoryChannel).where(MandatoryChannel.is_primary.is_(True)).limit(1))
    return result.scalar_one_or_none()


async def create_channel(
    session: AsyncSession, channel_id: str, name: str, invite_link: str | None, is_primary: bool
) -> MandatoryChannel:
    if is_primary:
        existing = await get_primary_channel(session)
        if existing is not None:
            existing.is_primary = False

    channel = MandatoryChannel(channel_id=channel_id, name=name, invite_link=invite_link, is_primary=is_primary)
    session.add(channel)
    await session.flush()
    return channel


async def delete_channel(session: AsyncSession, channel_id: int) -> None:
    channel = await get_by_id(session, channel_id)
    if channel is not None:
        await session.delete(channel)
        await session.flush()
