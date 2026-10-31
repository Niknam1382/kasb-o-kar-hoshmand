from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import ShopOwner
from app.services import wallet_service

logger = logging.getLogger(__name__)


async def process_wallet_expiry_and_reminders(session: AsyncSession, main_bot: Bot) -> None:
    """
    کارِ روزانه‌ی کیف‌پول:
    ۱. بسته‌های شارژی که تاریخِ انقضاشون گذشته رو واقعاً منقضی می‌کنه و موجودیِ
       کش‌شده‌ی فروشگاه‌دار رو متناسب کم می‌کنه.
    ۲. به فروشگاه‌دارهایی که یکی از بسته‌هاشون به مرزِ یادآوری (۳۰، ۷، یا ۱ روزِ
       مونده به انقضا) رسیده، پیامِ یادآوری می‌فرسته — هر بسته فقط یه‌بار به
       ازای هر مرز.
    """
    expired_count = await wallet_service.expire_stale_charges(session)
    if expired_count:
        logger.info("تعداد %s بسته‌ی کیف‌پول منقضی شد.", expired_count)

    due_reminders = await wallet_service.find_charges_needing_reminder(session)
    for charge, days_left in due_reminders:
        owner = await session.get(ShopOwner, charge.shop_owner_id)
        if owner is None:
            continue
        try:
            await main_bot.send_message(owner.telegram_id, texts.wallet_expiry_reminder(days_left, charge.remaining_toman))
            await wallet_service.mark_reminder_sent(session, charge, days_left)
        except TelegramAPIError:
            logger.exception("یادآوریِ انقضای کیف‌پول برای %s ناموفق بود.", owner.telegram_id)
