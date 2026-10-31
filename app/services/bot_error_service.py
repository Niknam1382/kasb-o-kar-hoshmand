from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BotErrorEvent

logger = logging.getLogger(__name__)


async def log_error(session: AsyncSession, shop_bot_id: int) -> None:
    session.add(BotErrorEvent(shop_bot_id=shop_bot_id))
    await session.flush()
