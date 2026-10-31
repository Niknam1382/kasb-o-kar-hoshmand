"""تصمیمِ فروشگاه‌دار رویِ رسیدِ کارت‌به‌کارت (C6) + تنظیماتِ «💳 روش‌هایِ پرداختِ مشتری» (C5).

callbackها: `rcpt_ok|rcpt_no|rcpt_nr:<idx|t>:<payment_id>` و `pays_*`. هر تصمیم ایدمپوتنت است (دابل‌تپ بی‌اثر)،
اعلان به مشتری بعد از commit می‌رود و شکستش فقط به فروشگاه‌دار گزارش می‌شه.
"""

from __future__ import annotations

import logging
import re

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers import order_ops
from app.bots.main_bot.states import PaymentOpsStates, PaymentSettingsStates
from app.bots.shop_bot import keyboards as shop_keyboards
from app.bots.shop_bot import texts as shop_texts
from app.bots.shop_bot.handlers.orders import send_invoice_to_customer
from app.database.models import Customer, TenantMode
from app.services import bale_credentials_service, order_payment_service, order_state, payment_settings_service
from app.services.admin_settings_service import get_admin_settings
from app.services import order_transition_service as transitions

logger = logging.getLogger(__name__)

router = Router(name="payment_ops")

REJECT_TEXT_MAX = 300
_MERCHANT_RE = re.compile(r"^[A-Za-z0-9\-]{36}$")


def _parse_id(raw: str) -> int | None:
    raw = (raw or "").strip()
    return int(raw) if raw.isascii() and raw.isdecimal() and 0 < len(raw) <= 12 else None


async def _to_customer(session: AsyncSession, shop_bot, rows, text: str, bot_manager, markup=None) -> bool:
    customer = await session.get(Customer, rows[0].customer_id)
    bot = bot_manager.get_bot(shop_bot.id) if bot_manager is not None else None
    if customer is None or bot is None:
        return False
    try:
        await bot.send_message(customer.telegram_id, text, reply_markup=markup)
    except (TelegramForbiddenError, TelegramAPIError):
        logger.warning("اعلانِ پرداخت به مشتری نرسید (shop_bot=%s).", shop_bot.id)
        return False
    return True


# ── تایید ────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("rcpt_ok:"))
async def rcpt_ok(callback: CallbackQuery, session: AsyncSession, bot_manager=None) -> None:
    owner, shop_bot = await order_ops._owner_and_bot(session, callback.from_user.id)
    payment_id = _parse_id(callback.data.split(":", 1)[1])
    if shop_bot is None or payment_id is None:
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    result = await order_payment_service.approve_payment(session, payment_id, shop_bot.id, decided_by=str(owner.id))
    if not result.ok:
        await callback.answer(texts.PAYS_STALE if result.reason == "not_found" else texts.PAYS_ILLEGAL, show_alert=True)
        return
    await session.commit()
    await callback.answer()
    rows = result.rows
    key = transitions.group_key(rows[0])
    suffix = texts.PAYS_APPROVED_SUFFIX
    if getattr(result, "late", False):
        suffix = f"{texts.PAYS_LATE_APPROVED_SUFFIX}" + (f"\n{texts.PAYS_LATE_OVERSOLD_SUFFIX}" if getattr(result, "oversold", False) else "")
    if result.changed:
        notified = await _to_customer(session, shop_bot, rows, shop_texts.payment_approved_message(shop_texts.order_code(rows)), bot_manager)
        customer = await session.get(Customer, rows[0].customer_id)
        bot = bot_manager.get_bot(shop_bot.id) if bot_manager is not None else None
        if customer is not None and bot is not None:
            await send_invoice_to_customer(session, shop_bot, rows, customer, bot, customer.telegram_id)
        from app.bots.main_bot.handlers import panel  # تحویلِ دیجیتال بعد از «پرداخت‌شده»

        for row in rows:
            try:
                await panel._deliver_digital_after_confirm(session, row, shop_bot, bot_manager, callback.bot)
            except Exception:  # noqa: BLE001 — شکستِ تحویل نباید تاییدِ ثبت‌شده رو خراب کنه
                logger.exception("تحویلِ دیجیتال بعد از پرداخت ناموفق بود (order=%s).", row.id)
        if not notified:
            suffix += f"\n{texts.PAYS_CUSTOMER_NOTIFY_FAILED}"
    await order_ops._edit_owner_message(
        callback, f"{order_ops._current_text(callback)}\n\n{suffix}", keyboards.order_group_actions_keyboard(key, order_state.PAID)
    )


# ── ردّ ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("rcpt_no:"))
async def rcpt_no(callback: CallbackQuery, session: AsyncSession) -> None:
    _owner, shop_bot = await order_ops._owner_and_bot(session, callback.from_user.id)
    payment_id = _parse_id(callback.data.split(":", 1)[1])
    payment = (
        await order_payment_service.get_payment_locked(session, payment_id, shop_bot.id)
        if (shop_bot is not None and payment_id is not None)
        else None
    )
    if payment is None:
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    await callback.answer()
    await order_ops._edit_owner_message(
        callback,
        f"{order_ops._current_text(callback)}\n\n{texts.PAYS_ASK_REJECT_REASON}",
        keyboards.receipt_reject_reasons_keyboard(payment_id, texts.RECEIPT_REJECT_REASONS),
    )


async def _reject(session: AsyncSession, owner, shop_bot, payment_id: int, reason: str, bot_manager):
    settings_row = await payment_settings_service.get_or_create(session, shop_bot.id)
    result = await order_payment_service.reject_payment(
        session, payment_id, shop_bot.id, settings_row, reason=reason, decided_by=str(owner.id)
    )
    if not result.ok:
        return result, None
    await session.commit()
    notified = None
    if result.changed:
        rows = result.rows
        key = transitions.group_key(rows[0])
        can_retry = result.final_status == order_state.AWAITING_PAYMENT
        notified = await _to_customer(
            session,
            shop_bot,
            rows,
            shop_texts.payment_rejected_message(shop_texts.order_code(rows), reason, can_retry),
            bot_manager,
            markup=shop_keyboards.receipt_keyboard(key) if can_retry else None,
        )
    return result, notified


@router.callback_query(F.data.startswith("rcpt_nr:"))
async def rcpt_reject_reason(callback: CallbackQuery, session: AsyncSession, state: FSMContext, bot_manager=None) -> None:
    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    _prefix, which, raw_id = parts
    owner, shop_bot = await order_ops._owner_and_bot(session, callback.from_user.id)
    payment_id = _parse_id(raw_id)
    if shop_bot is None or payment_id is None:
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    if which == "t":
        payment = await order_payment_service.get_payment_locked(session, payment_id, shop_bot.id)
        if payment is None:
            await callback.answer(texts.PAYS_STALE, show_alert=True)
            return
        await state.set_state(PaymentOpsStates.waiting_reject_text)
        await state.update_data(rcpt_payment_id=payment_id)
        await callback.answer()
        await callback.message.answer(texts.PAYS_ASK_REJECT_TEXT)
        return
    if not (which.isascii() and which.isdecimal()) or int(which) >= len(texts.RECEIPT_REJECT_REASONS):
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    result, notified = await _reject(session, owner, shop_bot, payment_id, texts.RECEIPT_REJECT_REASONS[int(which)], bot_manager)
    if not result.ok:
        await callback.answer(texts.PAYS_STALE if result.reason == "not_found" else texts.PAYS_ILLEGAL, show_alert=True)
        return
    await callback.answer()
    if result.changed:
        suffix = texts.PAYS_REJECTED_SUFFIX + ("" if notified else f"\n{texts.PAYS_CUSTOMER_NOTIFY_FAILED}")
        key = transitions.group_key(result.rows[0])
        await order_ops._edit_owner_message(
            callback, f"{order_ops._current_text(callback)}\n\n{suffix}", keyboards.order_group_actions_keyboard(key, result.final_status)
        )


@router.message(PaymentOpsStates.waiting_reject_text, F.text)
async def rcpt_reject_text(message: Message, state: FSMContext, session: AsyncSession, bot_manager=None) -> None:
    data = await state.get_data()
    payment_id = data.get("rcpt_payment_id")
    reason = (message.text or "").strip()
    if reason == "/cancel":
        await state.clear()
        await message.answer(texts.ORDER_OPS_CANCELLED)
        return
    if not reason or len(reason) > REJECT_TEXT_MAX:
        await message.answer(texts.PAYS_ASK_REJECT_TEXT)
        return
    await state.clear()
    owner, shop_bot = await order_ops._owner_and_bot(session, message.from_user.id)
    if shop_bot is None or not isinstance(payment_id, int):
        await message.answer(texts.PAYS_STALE)
        return
    result, notified = await _reject(session, owner, shop_bot, payment_id, reason, bot_manager)
    if not result.ok:
        await message.answer(texts.PAYS_STALE if result.reason == "not_found" else texts.PAYS_ILLEGAL)
        return
    await message.answer(texts.PAYS_REJECTED_SUFFIX + ("" if notified is not False else f"\n{texts.PAYS_CUSTOMER_NOTIFY_FAILED}"))


# =============================================================================
# تنظیماتِ روش‌هایِ پرداخت (C5)
# =============================================================================
async def _settings_ctx(session: AsyncSession, user_id: int):
    owner, shop_bot = await order_ops._owner_and_bot(session, user_id)
    if shop_bot is None:
        return None, None, None
    row = await payment_settings_service.get_or_create(session, shop_bot.id)
    return owner, shop_bot, row


async def _show_menu(callback: CallbackQuery, session: AsyncSession, shop_bot, row) -> None:
    status = await bale_credentials_service.shop_status(session, shop_bot, row)
    text = texts.payments_menu_text(row, shop_bot, status.missing)
    kb = keyboards.payments_menu_keyboard(row, shop_bot)
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "pays_menu")
async def pays_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    _owner, shop_bot, row = await _settings_ctx(session, callback.from_user.id)
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return
    if shop_bot.tenant_mode == TenantMode.CONSULTATION:
        await callback.answer(texts.PAYS_NEEDS_SALES_MODE, show_alert=True)
        return
    await callback.answer()
    await _show_menu(callback, session, shop_bot, row)


@router.callback_query(F.data.startswith("pays_tog:"))
async def pays_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    _owner, shop_bot, row = await _settings_ctx(session, callback.from_user.id)
    code = callback.data.split(":", 1)[1]
    if shop_bot is None or code not in ("card", "bale", "zarinpal", "manual", "auto"):
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    if code == "card":
        if not row.card_enabled and not payment_settings_service.get_card_number(row):
            await callback.answer("اول «💳 تنظیمِ کارت» رو کامل کن.", show_alert=True)
            return
        row.card_enabled = not row.card_enabled
    elif code == "bale":
        # A1: توکنِ درگاهِ سراسریِ مدیر پشتیبانِ توکنِ فروشگاه است، پس با هر کدام می‌شود روشن کرد.
        if not row.bale_enabled and not await bale_credentials_service.provider_token(session, shop_bot):
            await callback.answer("اول توکنِ درگاهِ بله‌پی رو ثبت کن: «💳 پرداختِ آنلاینِ سفارش‌ها».", show_alert=True)
            return
        row.bale_enabled = not row.bale_enabled
    elif code == "zarinpal":
        if not row.zarinpal_enabled and not row.zarinpal_merchant_id_enc:
            await callback.answer("اول «🔑 مرچنتِ زرین‌پال» رو ثبت کن.", show_alert=True)
            return
        row.zarinpal_enabled = not row.zarinpal_enabled
    elif code == "manual":
        online = await bale_credentials_service.methods(session, shop_bot, row, include_manual=False)
        if row.manual_enabled and not online:
            await callback.answer("حداقل یک روش باید فعال بمونه؛ پرداختِ دستی تنها روشِ فعاله.", show_alert=True)
            return
        row.manual_enabled = not row.manual_enabled
        if not row.manual_enabled and not online:
            row.manual_enabled = True
    else:
        row.auto_accept_online = not row.auto_accept_online
    await session.flush()
    await callback.answer()
    await _show_menu(callback, session, shop_bot, row)


@router.callback_query(F.data == "pays_card")
async def pays_card_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PaymentSettingsStates.waiting_card_number)
    await callback.answer()
    await callback.message.answer(texts.PAYS_ASK_CARD_NUMBER)


@router.message(PaymentSettingsStates.waiting_card_number, F.text)
async def pays_card_number(message: Message, state: FSMContext) -> None:
    number = payment_settings_service.parse_card_number(message.text or "")
    if number is None:
        await message.answer(texts.PAYS_INVALID_CARD)
        return
    await state.update_data(card_number=number)
    await state.set_state(PaymentSettingsStates.waiting_card_holder)
    await message.answer(texts.PAYS_ASK_CARD_HOLDER)


@router.message(PaymentSettingsStates.waiting_card_holder, F.text)
async def pays_card_holder(message: Message, state: FSMContext) -> None:
    raw = (message.text or "").strip()
    await state.update_data(card_holder=None if raw in ("-", "—") else raw[:80])
    await state.set_state(PaymentSettingsStates.waiting_card_bank)
    await message.answer(texts.PAYS_ASK_CARD_BANK)


@router.message(PaymentSettingsStates.waiting_card_bank, F.text)
async def pays_card_bank(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    _owner, shop_bot, row = await _settings_ctx(session, message.from_user.id)
    if shop_bot is None or not data.get("card_number"):
        await message.answer(texts.PAYS_STALE)
        return
    raw = (message.text or "").strip()
    payment_settings_service.set_card(row, data["card_number"], data.get("card_holder"), None if raw in ("-", "—") else raw)
    row.card_enabled = True
    await session.flush()
    await message.answer(texts.PAYS_SAVED + f"\nکارت: {payment_settings_service.mask_card(data['card_number'])}")


@router.callback_query(F.data.startswith("pays_dl:"))
async def pays_deadline_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    method = callback.data.split(":", 1)[1]
    if method not in ("card", "bale", "zarinpal"):
        await callback.answer(texts.PAYS_STALE, show_alert=True)
        return
    await state.set_state(PaymentSettingsStates.waiting_deadline)
    await state.update_data(pays_method=method)
    await callback.answer()
    low, high = payment_settings_service.deadline_bounds(await get_admin_settings(session))
    await callback.message.answer(texts.pays_ask_deadline(low, high))


@router.message(PaymentSettingsStates.waiting_deadline, F.text)
async def pays_deadline_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    low, high = payment_settings_service.deadline_bounds(await get_admin_settings(session))
    value = payment_settings_service.parse_positive_int(message.text or "", low, high)
    if value is None:
        await message.answer(f"{texts.PAYS_INVALID_NUMBER}\n{texts.pays_range_hint(low, high, 'دقیقه')}")
        return
    data = await state.get_data()
    await state.clear()
    _owner, shop_bot, row = await _settings_ctx(session, message.from_user.id)
    method = data.get("pays_method")
    if shop_bot is None or method not in ("card", "bale", "zarinpal"):
        await message.answer(texts.PAYS_STALE)
        return
    setattr(row, f"{method}_deadline_minutes", value)
    await session.flush()
    await message.answer(texts.PAYS_SAVED)


@router.callback_query(F.data == "pays_hold")
async def pays_hold_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.set_state(PaymentSettingsStates.waiting_hold)
    await callback.answer()
    low, high = payment_settings_service.review_hold_bounds(await get_admin_settings(session))
    await callback.message.answer(texts.pays_ask_hold(low, high))


@router.message(PaymentSettingsStates.waiting_hold, F.text)
async def pays_hold_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    low, high = payment_settings_service.review_hold_bounds(await get_admin_settings(session))
    value = payment_settings_service.parse_positive_int(message.text or "", low, high)
    if value is None:
        await message.answer(f"{texts.PAYS_INVALID_NUMBER}\n{texts.pays_range_hint(low, high, 'دقیقه')}")
        return
    await state.clear()
    _owner, shop_bot, row = await _settings_ctx(session, message.from_user.id)
    if shop_bot is None:
        await message.answer(texts.PAYS_STALE)
        return
    row.receipt_review_hold_minutes = value
    await session.flush()
    await message.answer(texts.PAYS_SAVED)


@router.callback_query(F.data == "pays_zp")
async def pays_zarinpal_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(PaymentSettingsStates.waiting_zarinpal_merchant)
    await callback.answer()
    await callback.message.answer(texts.PAYS_ASK_ZARINPAL)


@router.message(PaymentSettingsStates.waiting_zarinpal_merchant, F.text)
async def pays_zarinpal_save(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = (message.text or "").strip()
    if raw != "حذف" and not _MERCHANT_RE.match(raw):
        await message.answer(texts.PAYS_INVALID_MERCHANT)
        return
    await state.clear()
    _owner, shop_bot, row = await _settings_ctx(session, message.from_user.id)
    if shop_bot is None:
        await message.answer(texts.PAYS_STALE)
        return
    if raw == "حذف":
        row.zarinpal_merchant_id_enc = None
        row.zarinpal_enabled = False
    else:
        from app.utils.encryption import encrypt_token

        row.zarinpal_merchant_id_enc = encrypt_token(raw)
        row.zarinpal_enabled = True
    await session.flush()
    await message.answer(texts.PAYS_SAVED)
