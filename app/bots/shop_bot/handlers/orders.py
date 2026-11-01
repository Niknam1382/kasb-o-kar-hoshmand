"""«📦 سفارش‌هایِ من» در رباتِ فروشگاه (W2 · C4/C8/C9).

فهرستِ گروه‌بندی‌شده (تازه‌ترین اول، صفحه‌بندی) ← کارتِ سفارش با خط‌زمان ← فاکتور / دریافتِ دوباره /
لغوِ مشتری (فقط قبل از پرداخت). این روتر باید **قبل از** `customer.router` وصل شود (F20).
"""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import keyboards, texts
from app.database.models import Customer, Product, TenantMode
from app.services import (
    customer_service,
    digital_service,
    invoice_service,
    order_service,
    order_state,
    order_transition_service,
    platform_service,
    shop_bot_service,
    shop_owner_service,
)

logger = logging.getLogger(__name__)

router = Router(name="shop_orders")

PAGE_SIZE = 5
_NO_INVOICE_STATUSES = {
    order_state.CANCELLED,
    order_state.REJECTED,
    order_state.EXPIRED,
    order_state.AWAITING_CUSTOMER_CONFIRMATION,
}


def parse_key(key: str) -> tuple[str, int | None]:
    """کلیدِ گروه در callback: «o<id>» = سفارشِ تک‌محصولی؛ وگرنه شناسه‌یِ گروهِ چک‌اوت (hex).
    برمی‌گرداند (kind, order_id|None) با kind ∈ {"single","group","bad"}."""
    key = (key or "").strip()
    if not key or len(key) > 40:
        return "bad", None
    if key[0] == "o":
        digits = key[1:]
        if digits.isascii() and digits.isdecimal() and len(digits) <= 12:
            return "single", int(digits)
        return "bad", None
    if all(c in "0123456789abcdef" for c in key):
        return "group", None
    return "bad", None


async def _load_group(session: AsyncSession, shop_bot, customer: Customer, key: str):
    """ردیف‌هایِ گروه — فقط اگه متعلق به همین مشتری و همین فروشگاه باشه (جلوگیری از حدسِ id)."""
    kind, order_id = parse_key(key)
    if kind == "single":
        order = await order_service.get_owned_by_id(session, order_id, shop_bot.id)
        rows = [order] if order is not None else []
    elif kind == "group":
        rows = await order_service.get_by_cart_checkout_group(session, key, shop_bot.id)
        rows.sort(key=lambda r: r.id)
    else:
        rows = []
    if not rows or any(r.customer_id != customer.id for r in rows):
        return []
    return rows


async def _products_for(session: AsyncSession, groups) -> dict[int, Product]:
    products: dict[int, Product] = {}
    for rows in groups:
        for r in rows:
            if r.product_id is not None and r.product_id not in products:
                product = await session.get(Product, r.product_id)
                if product is not None:
                    products[r.product_id] = product
    return products


async def _resolve(session: AsyncSession, bot, telegram_id: int):
    shop_bot = await shop_bot_service.get_by_bot(session, bot)
    if shop_bot is None:
        return None, None
    customer = await customer_service.get_by_shop_bot_and_telegram_id(
        session, shop_bot.id, telegram_id, platform=platform_service.platform_of(bot)
    )
    return shop_bot, customer


async def _render_list(session: AsyncSession, shop_bot, customer: Customer, page: int):
    page = max(0, page)
    consultation = shop_bot.tenant_mode == TenantMode.CONSULTATION
    groups, total_groups = await order_transition_service.list_groups_for_customer(
        session, shop_bot.id, customer.id, limit=PAGE_SIZE, offset=page * PAGE_SIZE
    )
    if not groups and page > 0:
        return await _render_list(session, shop_bot, customer, 0)
    if not groups:
        return (texts.MY_ORDERS_CONSULT_EMPTY if consultation else texts.MY_ORDERS_EMPTY), None
    products = await _products_for(session, groups)
    totals = [order_transition_service.group_total_toman(rows) for rows in groups]
    text = texts.my_orders_list_text(groups, products, totals, page, total_groups, consultation=consultation)
    keys = [order_transition_service.group_key(rows[0]) for rows in groups]
    keyboard = keyboards.my_orders_list_keyboard(keys, page, total_groups, PAGE_SIZE, first_index=page * PAGE_SIZE + 1)
    return text, keyboard


@router.message(F.text == texts.BTN_MY_ORDERS)
async def my_orders_open(message: Message, session: AsyncSession) -> None:
    shop_bot = await shop_bot_service.get_by_bot(session, message.bot)
    if shop_bot is None:
        return
    customer = await customer_service.get_or_create_customer(
        session,
        shop_bot.id,
        message.from_user.id,
        message.from_user.first_name,
        message.from_user.username,
        last_name=message.from_user.last_name,
        platform=platform_service.of_event(message),
    )
    text, keyboard = await _render_list(session, shop_bot, customer, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("myord_page:"))
async def my_orders_page(callback: CallbackQuery, session: AsyncSession) -> None:
    raw = callback.data.split(":", 1)[1]
    shop_bot, customer = await _resolve(session, callback.bot, callback.from_user.id)
    if shop_bot is None or customer is None or not (raw.isascii() and raw.isdecimal()) or len(raw) > 4:
        await callback.answer(texts.MY_ORDER_STALE, show_alert=True)
        return
    text, keyboard = await _render_list(session, shop_bot, customer, int(raw))
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=keyboard)


def _can_invoice(rows) -> bool:
    return order_state.value_of(rows[0].status) not in _NO_INVOICE_STATUSES


async def _render_card(session: AsyncSession, shop_bot, rows):
    products = await _products_for(session, [rows])
    timeline = await order_transition_service.get_timeline(session, rows[0])
    total = order_transition_service.group_total_toman(rows)
    text = texts.my_order_card_text(rows, products, total, timeline)
    status = order_state.value_of(rows[0].status)
    digital_ids = [
        r.id
        for r in rows
        if r.digital_delivered_at is not None and digital_service.is_digital(products.get(r.product_id))
    ]
    keyboard = keyboards.my_order_card_keyboard(
        order_transition_service.group_key(rows[0]),
        can_invoice=_can_invoice(rows),
        can_cancel=status in order_state.CUSTOMER_CANCELLABLE,
        digital_order_ids=digital_ids,
        can_pay=status == order_state.AWAITING_PAYMENT,
    )
    return text, keyboard


@router.callback_query(F.data.startswith("myord_view:"))
async def my_order_view(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, customer = await _resolve(session, callback.bot, callback.from_user.id)
    rows = await _load_group(session, shop_bot, customer, key) if (shop_bot and customer) else []
    if not rows:
        await callback.answer(texts.MY_ORDER_STALE, show_alert=True)
        return
    text, keyboard = await _render_card(session, shop_bot, rows)
    await callback.answer()
    try:
        await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=keyboard)


async def send_invoice_to_customer(session: AsyncSession, shop_bot, rows, customer: Customer, target_bot: Bot, chat_id: int) -> bool:
    """فاکتور (ایدمپوتنت: همون شماره) را به‌صورتِ پیام + فایل می‌فرستد؛ شکستِ ارسال ⇒ False.

    P18 · B6: فایلِ PDFِ راست‌به‌چپ؛ اگر ساختِ PDF ممکن نباشد همان HTMLِ قبلی فرستاده می‌شود.
    """
    invoice, _created = await invoice_service.ensure_invoice(session, rows, customer, f"@{shop_bot.bot_username}")
    await session.commit()
    data = invoice_service.load_data(invoice)
    try:
        await target_bot.send_message(chat_id, invoice_service.format_invoice_text(data))
        pdf_bytes = invoice_service.build_invoice_pdf(data)
        if pdf_bytes is not None:
            await target_bot.send_document(chat_id, BufferedInputFile(pdf_bytes, filename=f"{invoice.number}.pdf"))
        else:
            html_bytes = invoice_service.build_invoice_html(data).encode("utf-8")
            await target_bot.send_document(chat_id, BufferedInputFile(html_bytes, filename=f"{invoice.number}.html"))
    except TelegramAPIError:
        logger.exception("ارسالِ فاکتورِ %s ناموفق بود.", invoice.number)
        return False
    return True


@router.callback_query(F.data.startswith("myord_inv:"))
async def my_order_invoice(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, customer = await _resolve(session, callback.bot, callback.from_user.id)
    rows = await _load_group(session, shop_bot, customer, key) if (shop_bot and customer) else []
    if not rows:
        await callback.answer(texts.MY_ORDER_STALE, show_alert=True)
        return
    if not _can_invoice(rows):
        await callback.answer(texts.MY_ORDER_INVOICE_UNAVAILABLE, show_alert=True)
        return
    await callback.answer()
    await send_invoice_to_customer(session, shop_bot, rows, customer, callback.bot, callback.from_user.id)


@router.callback_query(F.data.startswith("myord_cancel:"))
async def my_order_cancel(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, customer = await _resolve(session, callback.bot, callback.from_user.id)
    rows = await _load_group(session, shop_bot, customer, key) if (shop_bot and customer) else []
    if not rows:
        await callback.answer(texts.MY_ORDER_STALE, show_alert=True)
        return
    result = await order_transition_service.customer_cancel_group(session, rows[0], customer_id=customer.id)
    if not result.ok:
        await callback.answer(texts.MY_ORDER_CANNOT_CANCEL, show_alert=True)
        return
    await session.commit()
    await callback.answer(texts.MY_ORDER_CANCELLED)
    try:
        await callback.message.edit_text(texts.MY_ORDER_CANCELLED, reply_markup=None)
    except TelegramAPIError:
        pass
    if result.changed:
        owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
        if owner is not None:
            try:
                await main_bot.send_message(owner.telegram_id, main_texts.order_cancelled_by_customer_notification(rows, customer))
            except TelegramAPIError:
                logger.exception("اطلاعِ لغوِ سفارش به فروشگاه‌دار ناموفق بود.")
