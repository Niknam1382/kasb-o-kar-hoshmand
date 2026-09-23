from __future__ import annotations

import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ChannelKnowledge, ShopBot


async def get_shop_bot_by_channel_id(session: AsyncSession, channel_id: str) -> ShopBot | None:
    result = await session.execute(select(ShopBot).where(ShopBot.knowledge_channel_id == channel_id))
    return result.scalar_one_or_none()


async def save_knowledge_post(
    session: AsyncSession, shop_bot_id: int, source_channel_id: str, text: str, posted_at: datetime.datetime
) -> ChannelKnowledge:
    entry = ChannelKnowledge(shop_bot_id=shop_bot_id, source_channel_id=source_channel_id, text=text, posted_at=posted_at)
    session.add(entry)
    await session.flush()
    return entry


async def get_recent_knowledge(session: AsyncSession, shop_bot_id: int, limit: int = 15) -> list[ChannelKnowledge]:
    result = await session.execute(
        select(ChannelKnowledge)
        .where(ChannelKnowledge.shop_bot_id == shop_bot_id)
        .order_by(ChannelKnowledge.posted_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
