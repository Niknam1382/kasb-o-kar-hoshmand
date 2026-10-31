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


async def send_due_nightly_reports(session: AsyncSession, main_bot: Bot, now: datetime.datetime | None = None) -> None:
    """
    گزارشِ شبانه (فازِ ۳): جدا از send_due_reports بالا (که یه خلاصه‌ی سلامتِ
    کلی هر N روزه). این یکی هر روز، وقتی ساعتِ UTC از admin_settings.
    nightly_report_hour_utc گذشت، فقط عددهایِ «امروز» رو می‌فرسته — و چون این
    تابع هر ۳۰ دقیقه صدا زده می‌شه، last_nightly_report_date جلویِ دوبار-
    فرستادن توی یه روز رو می‌گیره.

    پارامترِ now اختیاریه (فقط برای تست — تا بشه بدونِ وابستگی به ساعتِ واقعیِ
    اجرا، رفتارِ «هنوز نرسیده»/«همین الان دوباره چک شد ولی امروز قبلاً رفته»
    رو دقیق تست کرد). توی اجرایِ واقعی (scheduler.py) همیشه None پاس داده
    می‌شه و ساعتِ واقعی استفاده می‌شه.
    """
    admin_settings = await get_admin_settings(session)
    if not admin_settings.nightly_report_enabled:
        return

    now = now or datetime.datetime.now(datetime.timezone.utc)
    if now.hour < admin_settings.nightly_report_hour_utc:
        return
    today = now.date()

    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    active_bots = result.scalars().all()

    for shop_bot in active_bots:
        if shop_bot.last_nightly_report_date == today:
            continue

        day_start = datetime.datetime.combine(today, datetime.time.min, tzinfo=datetime.timezone.utc)
        stats = await stats_service.get_shop_daily_stats(session, shop_bot.id, day_start, now)
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        try:
            await main_bot.send_message(owner.telegram_id, texts.nightly_report_text(stats))
            shop_bot.last_nightly_report_date = today
            await session.flush()
        except TelegramAPIError:
            logger.exception("ارسال گزارشِ شبانه برای فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)
