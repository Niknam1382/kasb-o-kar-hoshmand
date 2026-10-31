"""اعمال/ردِ پیشنهادِ ویرایشِ سبد با AI (W5 · C2). هیچ فراخوانیِ AI و هیچ هزینه‌ای اینجا نیست."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.shop_bot import cart_proposal_ui as ui
from app.bots.shop_bot import keyboards, texts
from app.services import cart_edit_service, cart_proposal_service, cart_service, customer_service, product_service, shop_bot_service

logger = logging.getLogger(__name__)

router = Router(name="shop_cart_proposals")


async def _edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


def _parse_id(data: str) -> int | None:
    raw = data.split(":", 1)[1] if ":" in data else ""
    return int(raw) if raw.isdecimal() and raw.isascii() else None


@router.callback_query(F.data.startswith("cart_ai_apply:"))
async def cart_ai_apply(callback: CallbackQuery, session: AsyncSession) -> None:
    proposal_id = _parse_id(callback.data)
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None or proposal_id is None:
        await callback.answer(ui.PROPOSAL_GONE, show_alert=True)
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_cart(session, shop_bot.id, customer.id) if customer else None
    if cart is None:
        await callback.answer(ui.PROPOSAL_GONE, show_alert=True)
        return

    status, row = await cart_proposal_service.claim(session, proposal_id, cart.id)
    if status == cart_proposal_service.CLAIM_NOT_FOUND:
        await callback.answer(ui.PROPOSAL_GONE, show_alert=True)
        return
    if status == cart_proposal_service.CLAIM_ALREADY_USED:
        await callback.answer(ui.PROPOSAL_ALREADY, show_alert=True)  # دابل‌تپ/کهنه ⇒ بدونِ اثرِ دوم
        return
    if status == cart_proposal_service.CLAIM_EXPIRED:
        await callback.answer()
        await _edit(callback, ui.PROPOSAL_EXPIRED)
        return

    items = await cart_service.get_items_with_products(session, cart.id)
    if row.fingerprint != cart_service.cart_fingerprint(items)[:16]:
        await callback.answer()
        await _edit(callback, ui.PROPOSAL_STALE)
        return

    operations = cart_proposal_service.deserialize_ops(row.ops_json)
    products_by_id = {}
    for operation in operations:
        if operation.product_id is not None and operation.product_id not in products_by_id:
            product = await product_service.get_owned_by_id(session, operation.product_id, shop_bot.id)
            if product is not None:
                products_by_id[product.id] = product
    outcomes = await cart_edit_service.apply_operations(session, cart, operations, products_by_id)
    await callback.answer()
    if not outcomes:
        await _edit(callback, texts.CART_AI_CLARIFY_GENERIC)
        return
    items_after = await cart_service.get_items_with_products(session, cart.id)
    await _edit(callback, texts.cart_ai_edit_reply(outcomes, 0, items_after), reply_markup=keyboards.cart_view_keyboard(items_after))


@router.callback_query(F.data.startswith("cart_ai_reject:"))
async def cart_ai_reject(callback: CallbackQuery, session: AsyncSession) -> None:
    proposal_id = _parse_id(callback.data)
    shop_bot = await shop_bot_service.get_by_bot_telegram_id(session, callback.bot.id)
    if shop_bot is None or proposal_id is None:
        await callback.answer(ui.PROPOSAL_GONE, show_alert=True)
        return
    customer = await customer_service.get_by_shop_bot_and_telegram_id(session, shop_bot.id, callback.from_user.id)
    cart = await cart_service.get_cart(session, shop_bot.id, customer.id) if customer else None
    if cart is None:
        await callback.answer(ui.PROPOSAL_GONE, show_alert=True)
        return
    consumed = await cart_proposal_service.reject(session, proposal_id, cart.id)
    if not consumed:
        await callback.answer(ui.PROPOSAL_ALREADY, show_alert=True)
        return
    await callback.answer()
    await _edit(callback, ui.PROPOSAL_REJECTED)
