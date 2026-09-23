from __future__ import annotations

import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import ShopOwner, Subscription, SubscriptionStatus
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)


async def process_grace_transitions(session: AsyncSession, main_bot: Bot) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    admin_settings = await get_admin_settings(session)
    grace_delta = datetime.timedelta(hours=admin_settings.grace_period_hours)

    latest_sub_subq = (
        select(Subscription.shop_owner_id, func.max(Subscription.id).label("max_id")).group_by(Subscription.shop_owner_id).subquery()
    )
    result = await session.execute(select(Subscription).join(latest_sub_subq, Subscription.id == latest_sub_subq.c.max_id))
    latest_subscriptions = result.scalars().all()

    for sub in latest_subscriptions:
        if sub.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIAL) and sub.end_date <= now:
            sub.status = SubscriptionStatus.GRACE
            if not sub.grace_reminder_sent:
                owner = await session.get(ShopOwner, sub.shop_owner_id)
                try:
                    await main_bot.send_message(owner.telegram_id, texts.grace_period_reminder(admin_settings.grace_period_hours))
                    sub.grace_reminder_sent = True
                except TelegramAPIError:
                    logger.exception("یادآوریِ مهلت انقضا برای %s ناموفق بود.", owner.telegram_id)
            await session.flush()

        elif sub.status == SubscriptionStatus.GRACE and sub.end_date + grace_delta <= now:
            sub.status = SubscriptionStatus.EXPIRED
            await session.flush()
