from __future__ import annotations

import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import ShopBot, ShopOwner
from app.services import stats_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)


async def send_due_reports(session: AsyncSession, main_bot: Bot) -> None:
    admin_settings = await get_admin_settings(session)
    frequency = datetime.timedelta(days=admin_settings.periodic_report_frequency_days)
    now = datetime.datetime.now(datetime.timezone.utc)

    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    active_bots = result.scalars().all()

    for shop_bot in active_bots:
        due = shop_bot.last_report_sent_at is None or (now - shop_bot.last_report_sent_at) >= frequency
        if not due:
            continue

        stats = await stats_service.get_shop_stats(session, shop_bot.id)
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        try:
            await main_bot.send_message(owner.telegram_id, texts.periodic_report_text(stats, admin_settings.periodic_report_frequency_days))
            shop_bot.last_report_sent_at = now
            await session.flush()
        except TelegramAPIError:
            logger.exception("ارسال گزارشِ دوره‌ای برای فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
