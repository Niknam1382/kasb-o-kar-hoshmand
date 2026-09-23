from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import Product, ShopBot, ShopOwner
from app.services import order_service

logger = logging.getLogger(__name__)


async def process_order_expiry(session: AsyncSession, main_bot: Bot) -> None:
    """
    کارِ دوره‌ای: سفارش‌های PENDING که رزروِ موجودیشون منقضی شده رو آزاد
    می‌کنه و به فروشگاه‌دار خبر می‌ده که دیگه رزرو نداره (تا اگه هنوز مشتری
    رو داره، بتونه دستی هماهنگ کنه).
    """
    expired = await order_service.expire_stale_reservations(session)
    if not expired:
        return

    logger.info("تعداد %s رزروِ سفارش منقضی شد.", len(expired))
    for order in expired:
        shop_bot = await session.get(ShopBot, order.shop_bot_id)
        if shop_bot is None:
            continue
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id)
        if owner is None:
            continue
        product_name = None
        if order.product_id is not None:
            product = await session.get(Product, order.product_id)
            product_name = product.name if product is not None else None
        try:
            await main_bot.send_message(owner.telegram_id, texts.order_reservation_expired_notification(product_name, order.summary))
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ انقضای رزروِ سفارش به %s ناموفق بود.", owner.telegram_id)
