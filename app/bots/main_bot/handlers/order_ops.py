"""عملیاتِ گروهیِ سفارش توسطِ فروشگاه‌دار (W2 · C4/C9/D5).

دکمه‌هایِ `og_*`: شروعِ پردازش، ارسال (+کدِ رهگیری)، تکمیل، ردّ/استرداد با دلیل، «استرداد انجام شد» و
«✉️ پیام به این مشتری». هر گذار از `order_transition_service.transition_group` می‌گذرد (قفل، ایدمپوتنسی،
رزرو، `order_events`)؛ **اعلان به مشتری بعد از commit** می‌رود و شکستِ ارسال فقط به فروشگاه‌دار اطلاع می‌شود.
"""

from __future__ import annotations

import hashlib
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import OrderOpsStates
from app.bots.shop_bot import texts as shop_texts
from app.bots.shop_bot.handlers.orders import parse_key
from app.database.models import Customer, DirectMessage
from app.utils.validators import fa_text
from app.services import (
    notification_service,
    order_service,
    order_state,
    order_transition_service,
    shop_bot_service,
    shop_owner_service,
)

logger = logging.getLogger(__name__)

router = Router(name="order_ops")

REJECT_TEXT_MAX = 300
TRACKING_MAX = 100
DIRECT_MAX = 1000


async def _owner_and_bot(session: AsyncSession, user_id: int):
    owner = await shop_owner_service.get_by_telegram_id(session, user_id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    return owner, shop_bot


async def _load_rows(session: AsyncSession, shop_bot, key: str):
    """ردیف‌هایِ گروه، فقط متعلق به همین فروشگاه (کلیدِ جعلی/کهنه ⇒ [])."""
    kind, order_id = parse_key(key)
    if kind == "single":
        order = await order_service.get_owned_by_id(session, order_id, shop_bot.id)
        return [order] if order is not None else []
    if kind == "group":
        rows = await order_service.get_by_cart_checkout_group(session, key, shop_bot.id)
        rows.sort(key=lambda r: r.id)
        return rows
    return []


async def notify_customer(session: AsyncSession, shop_bot, rows, text: str, bot_manager) -> bool:
    """پیامِ رباتِ فروشگاه به مشتری؛ `TelegramForbiddenError`/ربات‌نبودن ⇒ False (فقط لاگ)."""
    customer = await session.get(Customer, rows[0].customer_id)
    if customer is None or bot_manager is None:
        return False
    bot = bot_manager.customer_bot(shop_bot.id, customer.platform)
    if bot is None:
        return False
    try:
        await bot.send_message(customer.telegram_id, text)
    except TelegramForbiddenError:
        # مشتری ربات را بلاک کرده: تلاشِ دوباره بی‌معنی است ( صف نمی‌رود).
        logger.info("مشتریِ %s ربات را بلاک کرده؛ اعلانِ وضعیتِ سفارش فرستاده نشد.", customer.id)
        return False
    except TelegramAPIError:
        # خطایِ گذرا (۴۲۹/۵۰۳/شبکه) ⇒ در صفِ اعلان‌ها می‌ماند و جابِ دوره‌ای دوباره تلاش می‌کند.
        await notification_service.enqueue(
            session,
            customer.telegram_id,
            text,
            platform=customer.platform,
            shop_bot_id=shop_bot.id,
            label=f"order-status:{rows[0].id}",
            dedupe_key=f"ordstat:{rows[0].id}:{hashlib.sha1(text.encode()).hexdigest()[:8]}",
        )
        logger.warning("اعلانِ وضعیتِ سفارش به مشتری نرسید؛ در صفِ تلاشِ دوباره ثبت شد (shop_bot=%s).", shop_bot.id)
        return False
    return True


async def _edit_owner_message(callback: CallbackQuery, text: str, keyboard) -> None:
    try:
        if callback.message.photo:
            await callback.message.edit_caption(caption=text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(text, reply_markup=keyboard)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=keyboard)


def _current_text(callback: CallbackQuery) -> str:
    return callback.message.caption or callback.message.text or ""


async def _apply(
    callback: CallbackQuery,
    session: AsyncSession,
    bot_manager,
    key: str,
    to_status,
    *,
    tracking_code: str | None = None,
    reason: str | None = None,
    edit_owner_message: bool = True,
    use_reject_logic: bool = False,
) -> bool:
    """یک گذارِ کامل: قفل+اعتبارسنجی ← commit ← اعلانِ مشتری ← به‌روزرسانیِ پیامِ فروشگاه‌دار."""
    owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    if shop_bot is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return False
    rows = await _load_rows(session, shop_bot, key)
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return False

    if use_reject_logic:
        result = await order_transition_service.reject_or_refund_group(
            session, rows[0], reason=reason, actor_type="owner", actor_ref=str(owner.id)
        )
    else:
        result = await order_transition_service.transition_group(
            session, rows[0], to_status, actor_type="owner", actor_ref=str(owner.id), reason=reason, tracking_code=tracking_code
        )
    if not result.ok:
        await callback.answer(texts.ORDER_OPS_ILLEGAL, show_alert=True)
        return False
    await session.commit()
    await callback.answer()
    if not result.changed:
        return True  # دابل‌تپ: اثرِ دوم ندارد

    final = result.to_status
    notified = await notify_customer(
        session,
        shop_bot,
        rows,
        shop_texts.order_status_customer_message(final, rows, tracking_code=tracking_code, reason=reason),
        bot_manager,
    )
    if edit_owner_message:
        suffix = fa_text(texts.ORDER_OPS_DONE_SUFFIX, label=texts.order_status_label(final))
        if final == order_state.REFUND_PENDING:
            suffix += f"\n{texts.ORDER_REFUND_GUIDE}"
        if not notified:
            suffix += f"\n{texts.ORDER_CUSTOMER_NOTIFY_FAILED}"
        keyboard = keyboards.order_group_actions_keyboard(key, final)
        await _edit_owner_message(callback, f"{_current_text(callback)}\n\n{suffix}", keyboard)
    return True


@router.callback_query(F.data.startswith("og_start:"))
async def og_start(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    await _apply(callback, session, bot_manager, callback.data.split(":", 1)[1], order_state.PROCESSING)


@router.callback_query(F.data.startswith("og_done:"))
async def og_done(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    await _apply(callback, session, bot_manager, callback.data.split(":", 1)[1], order_state.COMPLETED)


@router.callback_query(F.data.startswith("og_restock:"))
async def og_restock(callback: CallbackQuery, session: AsyncSession) -> None:
    """W5 · 2.2: برگشتِ موجودیِ سفارشِ استردادشده به انبار (اختیارِ فروشگاه‌دار؛ هر ردیف حداکثر یک‌بار)."""
    key = callback.data.split(":", 1)[1]
    _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if shop_bot else []
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    if any(order_state.value_of(r.status) != order_state.REFUNDED for r in rows):
        await callback.answer(texts.ORDER_OPS_ILLEGAL, show_alert=True)
        return
    restocked = await order_transition_service.restock_group(session, rows)
    await callback.answer(texts.ORDER_RESTOCKED if restocked else texts.ORDER_RESTOCK_NOTHING, show_alert=not restocked)


@router.callback_query(F.data.startswith("og_refunded:"))
async def og_refunded(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    await _apply(callback, session, bot_manager, callback.data.split(":", 1)[1], order_state.REFUNDED)


# ── ارسال (+کدِ رهگیری) ─────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("og_ship:"))
async def og_ship_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if shop_bot else []
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    await state.set_state(OrderOpsStates.waiting_tracking_code)
    await state.update_data(og_key=key)
    await callback.answer()
    await callback.message.answer(texts.ORDER_ASK_TRACKING_CODE)


@router.message(OrderOpsStates.waiting_tracking_code, F.text)
async def og_ship_code(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    key = data.get("og_key")
    raw = (message.text or "").strip()
    if len(raw) > TRACKING_MAX:
        await message.answer(texts.ORDER_TRACKING_TOO_LONG)
        return
    await state.clear()  # دابل‌تپ: اول state پاک می‌شه
    owner, shop_bot = await _owner_and_bot(session, message.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if (shop_bot and key) else []
    if not rows:
        await message.answer(texts.ORDER_OPS_STALE)
        return
    tracking = None if raw in ("-", "—", "") else raw
    result = await order_transition_service.transition_group(
        session, rows[0], order_state.SHIPPED, actor_type="owner", actor_ref=str(owner.id), tracking_code=tracking
    )
    if not result.ok:
        await message.answer(texts.ORDER_OPS_ILLEGAL)
        return
    await session.commit()
    if not result.changed:
        await message.answer(fa_text(texts.ORDER_OPS_DONE_SUFFIX, label=texts.order_status_label(order_state.SHIPPED)))
        return
    notified = await notify_customer(
        session, shop_bot, rows, shop_texts.order_status_customer_message(order_state.SHIPPED, rows, tracking_code=tracking), bot_manager
    )
    suffix = fa_text(texts.ORDER_OPS_DONE_SUFFIX, label=texts.order_status_label(order_state.SHIPPED))
    if not notified:
        suffix += f"\n{texts.ORDER_CUSTOMER_NOTIFY_FAILED}"
    await message.answer(suffix, reply_markup=keyboards.order_group_actions_keyboard(key, order_state.SHIPPED))


# ── ردّ / استرداد با دلیل ───────────────────────────────────────────────────
@router.callback_query(F.data.startswith("og_rej:"))
async def og_reject_start(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if shop_bot else []
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    await callback.answer()
    await _edit_owner_message(
        callback,
        f"{_current_text(callback)}\n\n{texts.ORDER_ASK_REJECT_REASON}",
        keyboards.order_reject_reasons_keyboard(key, texts.ORDER_REJECT_REASONS),
    )


@router.callback_query(F.data.startswith("og_back:"))
async def og_back(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if shop_bot else []
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    await callback.answer()
    base = _current_text(callback).split(f"\n\n{texts.ORDER_ASK_REJECT_REASON}")[0]
    await _edit_owner_message(callback, base, keyboards.order_group_actions_keyboard(key, rows[0].status))


@router.callback_query(F.data.startswith("og_rr:"))
async def og_reject_reason(callback: CallbackQuery, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    _prefix, which, key = parts
    if which == "t":
        _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
        rows = await _load_rows(session, shop_bot, key) if shop_bot else []
        if not rows:
            await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
            return
        await state.set_state(OrderOpsStates.waiting_reject_text)
        await state.update_data(og_key=key)
        await callback.answer()
        await callback.message.answer(texts.ORDER_ASK_REJECT_TEXT)
        return
    if not (which.isascii() and which.isdecimal()) or int(which) >= len(texts.ORDER_REJECT_REASONS):
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    await _apply(callback, session, bot_manager, key, None, reason=texts.ORDER_REJECT_REASONS[int(which)], use_reject_logic=True)


@router.message(OrderOpsStates.waiting_reject_text, F.text)
async def og_reject_text(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    key = data.get("og_key")
    reason = (message.text or "").strip()
    if not reason or len(reason) > REJECT_TEXT_MAX:
        await message.answer(texts.ORDER_ASK_REJECT_TEXT)
        return
    await state.clear()
    owner, shop_bot = await _owner_and_bot(session, message.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if (shop_bot and key) else []
    if not rows:
        await message.answer(texts.ORDER_OPS_STALE)
        return
    result = await order_transition_service.reject_or_refund_group(
        session, rows[0], reason=reason, actor_type="owner", actor_ref=str(owner.id)
    )
    if not result.ok:
        await message.answer(texts.ORDER_OPS_ILLEGAL)
        return
    await session.commit()
    if not result.changed:
        await message.answer(fa_text(texts.ORDER_OPS_DONE_SUFFIX, label=texts.order_status_label(result.to_status)))
        return
    notified = await notify_customer(
        session, shop_bot, rows, shop_texts.order_status_customer_message(result.to_status, rows, reason=reason), bot_manager
    )
    suffix = fa_text(texts.ORDER_OPS_DONE_SUFFIX, label=texts.order_status_label(result.to_status))
    if result.to_status == order_state.REFUND_PENDING:
        suffix += f"\n{texts.ORDER_REFUND_GUIDE}"
    if not notified:
        suffix += f"\n{texts.ORDER_CUSTOMER_NOTIFY_FAILED}"
    await message.answer(suffix, reply_markup=keyboards.order_group_actions_keyboard(key, result.to_status))


# ── پیامِ مستقیم (D5-ساده) ──────────────────────────────────────────────────
@router.callback_query(F.data.startswith("og_msg:"))
async def og_message_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    _owner, shop_bot = await _owner_and_bot(session, callback.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if shop_bot else []
    if not rows:
        await callback.answer(texts.ORDER_OPS_STALE, show_alert=True)
        return
    await state.set_state(OrderOpsStates.waiting_direct_message)
    await state.update_data(og_key=key)
    await callback.answer()
    await callback.message.answer(texts.ORDER_ASK_DIRECT_MESSAGE)


@router.message(OrderOpsStates.waiting_direct_message, F.text)
async def og_message_text(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    key = data.get("og_key")
    body = (message.text or "").strip()
    if not body:
        await message.answer(texts.ORDER_ASK_DIRECT_MESSAGE)
        return
    if len(body) > DIRECT_MAX:
        await message.answer(texts.ORDER_DIRECT_TOO_LONG)
        return
    await state.clear()
    _owner, shop_bot = await _owner_and_bot(session, message.from_user.id)
    rows = await _load_rows(session, shop_bot, key) if (shop_bot and key) else []
    if not rows:
        await message.answer(texts.ORDER_OPS_STALE)
        return
    delivered = await notify_customer(session, shop_bot, rows, shop_texts.DIRECT_MESSAGE_PREFIX + body, bot_manager)
    session.add(
        DirectMessage(shop_bot_id=shop_bot.id, customer_id=rows[0].customer_id, order_id=rows[0].id, body=body, delivered=delivered)
    )
    await session.commit()
    await message.answer(texts.ORDER_DIRECT_SENT if delivered else texts.ORDER_DIRECT_BLOCKED)
