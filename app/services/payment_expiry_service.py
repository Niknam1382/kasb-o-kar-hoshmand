"""جابِ انقضایِ پرداختِ سفارش (F7): هر ~۶۰ ثانیه گروه‌هایِ awaiting_payment/receipt_submitted با مهلتِ گذشته ⇒ expired.
اعلان‌ها بعد از commit؛ شکستِ ارسال فقط لاگ می‌شه."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bots.shop_bot import texts as shop_texts
from app.database.models import Customer, ShopBot, ShopOwner
from app.database.session import session_scope
from app.services import order_payment_service

logger = logging.getLogger(__name__)


async def _send_review_warnings(main_bot: Bot) -> None:
    """W5 · 2.2: «۲ ساعت مونده» برایِ رسیدِ بررسی‌نشده؛ هر رسید یک‌بار. شکستِ ارسال فقط لاگ."""
    from app.bots.main_bot import keyboards as main_keyboards
    from app.bots.main_bot import texts as main_texts

    pending: list[tuple[int, str, float, int, str]] = []
    async with session_scope() as session:
        for payment, rows, hours_left in await order_payment_service.due_review_warnings(session):
            shop_bot = await session.get(ShopBot, payment.shop_bot_id)
            owner = await session.get(ShopOwner, shop_bot.shop_owner_id) if shop_bot is not None else None
            if owner is not None:
                pending.append((owner.telegram_id, shop_texts.order_code(rows), hours_left, payment.id, payment.group_id))
    for owner_tid, code, hours_left, payment_id, group_id in pending:
        try:
            await main_bot.send_message(
                owner_tid, main_texts.receipt_review_warning(code, hours_left), reply_markup=main_keyboards.receipt_review_keyboard(payment_id, group_id)
            )
        except TelegramAPIError:
            logger.warning("هشدارِ بررسیِ رسید به فروشگاه‌دار نرسید.")


async def process_payment_expiry(main_bot: Bot, bot_manager) -> int:
    notices: list[tuple[int, int | None, int | None, str]] = []
    async with session_scope() as session:
        groups = await order_payment_service.expire_stale_payment_groups(session)
        for rows in groups:
            first = rows[0]
            shop_bot = await session.get(ShopBot, first.shop_bot_id)
            customer = await session.get(Customer, first.customer_id)
            owner = await session.get(ShopOwner, shop_bot.shop_owner_id) if shop_bot is not None else None
            notices.append(
                (
                    shop_bot.id if shop_bot is not None else 0,
                    owner.telegram_id if owner is not None else None,
                    customer.telegram_id if customer is not None else None,
                    shop_texts.order_code(rows),
                )
            )
    await _send_review_warnings(main_bot)
    for shop_bot_id, owner_tid, customer_tid, code in notices:
        text = shop_texts.payment_expired_message(code)
        shop_bot_instance = bot_manager.get_bot(shop_bot_id) if bot_manager is not None else None
        if shop_bot_instance is not None and customer_tid is not None:
            try:
                await shop_bot_instance.send_message(customer_tid, text)
            except TelegramAPIError:
                logger.warning("اعلانِ انقضایِ پرداخت به مشتری نرسید (shop_bot=%s).", shop_bot_id)
        if owner_tid is not None:
            try:
                await main_bot.send_message(owner_tid, f"⌛️ سفارشِ {code} به‌خاطرِ پایانِ مهلتِ پرداخت منقضی شد و موجودی آزاد شد.")
            except TelegramAPIError:
                logger.warning("اعلانِ انقضایِ پرداخت به فروشگاه‌دار نرسید.")
    return len(notices)
