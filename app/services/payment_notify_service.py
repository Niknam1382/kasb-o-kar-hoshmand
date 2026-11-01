"""اعلان‌هایِ بعد از commit برایِ پرداختِ آنلاینِ تاییدشده (بله‌پی/زرین‌پال): فروشگاه‌دار + مشتری + فاکتور + تحویلِ دیجیتال.
هر شکستِ ارسال فقط لاگ می‌شه؛ اعتبارِ پرداخت قبلاً در DB ثبت شده."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from app.bots.main_bot import keyboards as main_keyboards
from app.bots.shop_bot import texts as shop_texts
from app.database.models import Customer, OrderConsultation, ShopBot, ShopOwner
from app.database.session import session_scope
from app.services import order_state, order_transition_service
from app.utils.validators import format_toman

logger = logging.getLogger(__name__)

METHOD_LABELS = {"bale": "بله‌پی", "zarinpal": "زرین‌پال", "card": "کارت‌به‌کارت"}


async def notify_online_payment(main_bot: Bot, bot_manager, shop_bot_id: int, rows_ids: list[int], *, method: str, late: bool, needs_review: bool, oversold: bool, final_status: str) -> None:
    from sqlalchemy import select

    async with session_scope() as session:
        rows = list((await session.execute(select(OrderConsultation).where(OrderConsultation.id.in_(rows_ids)).order_by(OrderConsultation.id))).scalars().all())
        if not rows:
            return
        shop_bot = await session.get(ShopBot, shop_bot_id)
        customer = await session.get(Customer, rows[0].customer_id)
        owner = await session.get(ShopOwner, shop_bot.shop_owner_id) if shop_bot is not None else None
        code = shop_texts.order_code(rows)
        key = order_transition_service.group_key(rows[0])
        total = order_transition_service.group_total_toman(rows)
        owner_tid = owner.telegram_id if owner is not None else None
        customer_tid = customer.telegram_id if customer is not None else None

        label = METHOD_LABELS.get(method, method)
        lines = [f"💳 پرداختِ آنلاین ({label}) برایِ سفارش {code} تایید شد — {format_toman(total)}."]
        if late:
            lines.append("⏰ پرداخت بعد از پایانِ مهلت رسید" + (" و موجودی کافی نبود (فروش بیش از موجودی)." if oversold else "؛ سفارش دوباره رزرو شد."))
        if needs_review:
            lines.append("⚠️ نیازِ بررسیِ دستی داره (ممکنه لازم باشه مبلغ رو به مشتری برگردونی).")
        if owner_tid is not None:
            try:
                await main_bot.send_message(owner_tid, "\n".join(lines), reply_markup=main_keyboards.order_group_actions_keyboard(key, final_status))
            except TelegramAPIError:
                logger.exception("اطلاعِ پرداختِ آنلاین به فروشگاه‌دار ناموفق بود.")

        shop_bot_instance = bot_manager.customer_bot(shop_bot_id, customer.platform) if (bot_manager is not None and customer is not None) else None
        if shop_bot_instance is not None and customer_tid is not None:
            try:
                await shop_bot_instance.send_message(customer_tid, shop_texts.payment_approved_message(code))
            except TelegramAPIError:
                logger.exception("اعلامِ پرداخت به مشتری ناموفق بود.")
            if not needs_review:
                from app.bots.shop_bot.handlers.orders import send_invoice_to_customer

                await send_invoice_to_customer(session, shop_bot, rows, customer, shop_bot_instance, customer_tid)

        if not needs_review and order_state.value_of(rows[0].status) in order_state.PAID_OR_LATER:
            from app.bots.main_bot.handlers import panel

            for row in rows:
                try:
                    await panel._deliver_digital_after_confirm(session, row, shop_bot, bot_manager, main_bot)
                except Exception:  # noqa: BLE001
                    logger.exception("تحویلِ دیجیتال بعد از پرداختِ آنلاین ناموفق بود (order=%s).", row.id)
