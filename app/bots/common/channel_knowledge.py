from __future__ import annotations

from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import channel_knowledge_service


async def capture_channel_post(channel_post: Message, session: AsyncSession) -> None:
    text = channel_post.text or channel_post.caption
    if not text:
        return

    shop_bot = await channel_knowledge_service.get_shop_bot_by_channel_id(session, str(channel_post.chat.id))
    if shop_bot is None:
        return

    await channel_knowledge_service.save_knowledge_post(session, shop_bot.id, str(channel_post.chat.id), text, channel_post.date)


def create_channel_knowledge_router(name: str) -> Router:
    router = Router(name=name)
    router.channel_post.register(capture_channel_post)
    return router
