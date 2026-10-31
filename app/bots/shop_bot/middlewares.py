"""P18 · B4: دروازه‌یِ مشتریِ بلاک‌شده.

یک میدل‌ورِ outer رویِ روتِرِ رباتِ فروشگاه تا *هیچ* مسیری (متن، عکس، صدا، و کالبکِ سبد/چک‌اوت/سفارش/
پرداخت/پیشنهادِ AI) برایِ مشتریِ بلاک‌شده اجرا نشود: نه AI، نه سفارش، نه پرداخت، نه کسرِ کیف‌پول.
مشتری حداکثر یک پیامِ ادبی می‌گیرد (با کول‌دن تا اسپم نشود) و کالبک‌ها بی‌صدا پاسخ داده می‌شوند تا
اسپینرِ تلگرام گیر نکند.

هزینه: یک SELECTِ ایندکس‌دار به‌ازایِ هر آپدیت (`shop_bots.bot_telegram_id` یکتا +
`customers(shop_bot_id, telegram_id)` یکتا) و بدونِ بارگذاریِ ردیفِ کامل. این عمداً به‌جایِ چک در
بیش از بیست هندلرِ پراکنده انتخاب شد تا هیچ مسیری جا نیفتد.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.shop_bot import texts
from app.database.models import Customer, ShopBot

logger = logging.getLogger(__name__)

NOTICE_COOLDOWN_SECONDS = 60 * 60
_MAX_TRACKED_KEYS = 10_000
_last_notice_at: dict[tuple[int, int], float] = {}


def reset_notice_cache() -> None:
    """فقط برایِ تست: `reset_database` شناسه‌ها را دوباره استفاده می‌کند."""
    _last_notice_at.clear()


def notice_allowed(bot_telegram_id: int, customer_telegram_id: int, now: float | None = None) -> bool:
    """«حداکثر یک پیامِ ادبی» در هر کول‌دن، به‌تفکیکِ فروشگاه (نه سراسری)."""
    now = time.monotonic() if now is None else now
    key = (bot_telegram_id, customer_telegram_id)
    previous = _last_notice_at.get(key)
    if previous is not None and now - previous < NOTICE_COOLDOWN_SECONDS:
        return False
    if len(_last_notice_at) >= _MAX_TRACKED_KEYS and key not in _last_notice_at:
        _last_notice_at.clear()
    _last_notice_at[key] = now
    return True


async def is_blocked(session: AsyncSession, bot_telegram_id: int, customer_telegram_id: int) -> bool:
    row = await session.execute(
        select(Customer.id)
        .join(ShopBot, ShopBot.id == Customer.shop_bot_id)
        .where(
            ShopBot.bot_telegram_id == bot_telegram_id,
            Customer.telegram_id == customer_telegram_id,
            Customer.is_blocked.is_(True),
        )
        .limit(1)
    )
    return row.first() is not None


class BlockedCustomerMiddleware(BaseMiddleware):
    async def __call__(
        self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]
    ) -> Any:
        user = getattr(event, "from_user", None)
        bot = data.get("bot")
        session = data.get("session")
        if user is None or bot is None or not isinstance(session, AsyncSession):
            return await handler(event, data)

        try:
            blocked = await is_blocked(session, bot.id, user.id)
        except Exception:
            # شکستِ این چک هرگز نباید کلِ ربات را بیندازد؛ هندلرها نگهبان‌هایِ خودشان را دارند.
            logger.exception("بررسیِ وضعیتِ بلاکِ مشتری ناموفق بود؛ آپدیت به‌صورتِ عادی ادامه می‌یابد.")
            return await handler(event, data)

        if not blocked:
            return await handler(event, data)

        if isinstance(event, CallbackQuery):
            await event.answer()
            return None
        if isinstance(event, Message) and notice_allowed(bot.id, user.id):
            await event.answer(texts.CUSTOMER_BLOCKED_NOTICE)
        return None
