"""P21-D (F7): اخطارِ «موجودی دارد تمام می‌شود» به خودِ فروشگاه‌دار.

امروز فروشگاه‌دار از اتمامِ موجودی *بعد از* سفارشِ مشتری باخبر می‌شود (ردکردنِ سفارش). این
جاب همان را قبل از فروشِ از‌دست‌رفته می‌گوید: برایِ هر فروشنده‌ای که آستانه تعیین کرده،
محصولاتِ فعالی که «موجودیِ واقعی» (موجودی کمِ رزروِ سفارش‌هایِ باز) زیرِ آستانه‌اند فهرست
می‌شوند و حداکثر یک پیام در ۲۴ ساعت می‌روند.

هیچ‌چیز اجباری نیست: `low_stock_alert_threshold` به‌صورتِ NULL ساخته شده ⇒ رفتارِ امروز
بدونِ تغییر می‌ماند تا فروشگاه‌دار خودش روشنش کند.
"""

from __future__ import annotations

import datetime
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import Product, ShopBot, ShopOwner

logger = logging.getLogger(__name__)

NOTIFY_INTERVAL_SECONDS = 24 * 60 * 60  # هر فروشگاه حداکثر یک اخطارِ موجودی در شبانه‌روز
LIST_LIMIT = 8


def available_stock(product: Product) -> int:
    """موجودیِ واقعی: عددِ انبار کمِ آنچه سفارش‌هایِ باز رزرو کرده‌اند. None ⇒ بی‌محدودیت."""
    if product.stock_quantity is None:
        return -1
    return int(product.stock_quantity or 0) - int(product.reserved_quantity or 0)


async def low_stock_rows(session: AsyncSession, shop_bot_id: int, threshold: int) -> list[Product]:
    result = await session.execute(
        select(Product)
        .where(
            Product.shop_bot_id == shop_bot_id,
            Product.is_active.is_(True),
            Product.retired_at.is_(None),
            Product.stock_quantity.is_not(None),
        )
        .order_by(Product.stock_quantity.asc(), Product.id)
    )
    return [product for product in result.scalars().all() if available_stock(product) <= threshold]


def _aware(value: datetime.datetime | None) -> datetime.datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)


def is_due(shop_bot: ShopBot, now: datetime.datetime) -> bool:
    last = _aware(shop_bot.low_stock_notified_at)
    return last is None or (now - last).total_seconds() >= NOTIFY_INTERVAL_SECONDS


async def run(session: AsyncSession, main_bot: Bot, now: datetime.datetime | None = None) -> dict[str, int]:
    """یک دورِ اخطارِ موجودی برایِ همه‌یِ فروشگاه‌هایِ فعالِ با آستانه. خلاصه برمی‌گرداند."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    sent = skipped = 0
    shop_bots = list(
        (
            await session.execute(
                select(ShopBot).where(
                    ShopBot.is_active.is_(True),
                    ShopBot.low_stock_alert_threshold.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for shop_bot in shop_bots:
        threshold = int(shop_bot.low_stock_alert_threshold or 0)
        if threshold <= 0 or not is_due(shop_bot, now):
            skipped += 1
            continue
        rows = await low_stock_rows(session, shop_bot.id, threshold)
        if not rows:
            continue
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        if owner is None:
            continue
        try:
            await main_bot.send_message(owner.telegram_id, texts.stock_alert_text(rows, threshold, LIST_LIMIT))
        except TelegramAPIError:
            # اخطارِ جانبی هرگز نباید کلِ جاب را برایِ فروشگاه‌هایِ بعدی بخواباند
            logger.warning("اخطارِ موجودی به فروشگاه‌دارِ رباتِ %s نرسید.", shop_bot.id, exc_info=True)
            continue
        shop_bot.low_stock_notified_at = now
        sent += 1
    await session.flush()
    if sent:
        logger.info("اخطارِ موجودی: %s فروشگاه پیام گرفت (آستانهٔ خودشان).", sent)
    return {"sent": sent, "skipped": skipped}
