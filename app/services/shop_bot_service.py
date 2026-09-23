from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopBot, ShopOwner
from app.utils.encryption import encrypt_token


async def get_by_owner(session: AsyncSession, owner: ShopOwner | None) -> ShopBot | None:
    if owner is None:
        return None
    result = await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner.id))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, shop_bot_id: int) -> ShopBot | None:
    return await session.get(ShopBot, shop_bot_id)


async def get_by_bot_telegram_id(session: AsyncSession, bot_telegram_id: int) -> ShopBot | None:
    result = await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == bot_telegram_id))
    return result.scalar_one_or_none()


async def get_all_active(session: AsyncSession) -> list[ShopBot]:
    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    return list(result.scalars().all())


async def upsert_shop_bot(
    session: AsyncSession, owner: ShopOwner, raw_token: str, bot_telegram_id: int, bot_username: str
) -> ShopBot:
    shop_bot = await get_by_owner(session, owner)
    encrypted = encrypt_token(raw_token)
    if shop_bot is None:
        shop_bot = ShopBot(
            shop_owner_id=owner.id,
            encrypted_token=encrypted,
            bot_telegram_id=bot_telegram_id,
            bot_username=bot_username,
            webhook_secret_token=secrets.token_urlsafe(32),
        )
        session.add(shop_bot)
    else:
        shop_bot.encrypted_token = encrypted
        shop_bot.bot_telegram_id = bot_telegram_id
        shop_bot.bot_username = bot_username
        shop_bot.is_active = True
        shop_bot.disabled_reason = None
    await session.flush()
    return shop_bot
