"""پرداختِ سفارش در رباتِ فروشگاه (W3 · C5/C6): انتخابِ روش، کارت‌به‌کارت با رسید، نگهبانِ «پرداخت کردم».

callbackها: `pm_menu|pm_manual|pm_card:<key>`، `pay_receipt:<key>`. مالکیت با customer_id چک می‌شه؛
کلیدِ جعلی/کهنه ⇒ هشدارِ مودبانه. این روتر باید **قبل از** `customer.router` وصل شود (state-filter و F.photo).
"""

from __future__ import annotations

import logging
import secrets
import time

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards as main_keyboards
from app.bots.main_bot import texts as main_texts
from app.bots.shop_bot import keyboards, texts
from app.bots.shop_bot.handlers.orders import _load_group, _resolve
from app.bots.shop_bot.states import PaymentStates
from app.database.models import Customer, OrderConsultation, OrderStatus, TenantMode
from app.config import settings
from app.services import (
    bale_credentials_service,
    bale_service,
    order_payment_service,
    order_state,
    order_transition_service,
    payment_settings_service,
    receipt_ai_service,
    shop_owner_service,
    zarinpal_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.services.identity_service import display_user
from app.utils.jalali import format_jalali_datetime, to_tehran
from app.utils.encryption import decrypt_token
from app.utils.validators import format_toman

logger = logging.getLogger(__name__)

router = Router(name="shop_payments")

# B11: اطلاعِ «پیکربندیِ بله‌پی ناقص است» به فروشگاه‌دار — نه به مشتری — و حداکثر هر ۶ ساعت برایِ هر فروشگاه.
_OWNER_ALERT_COOLDOWN_SECONDS = 6 * 60 * 60
_last_owner_misconfig_alert: dict[int, float] = {}


async def _pay_methods(session: AsyncSession, shop_bot, row, *, include_manual: bool = True) -> list[str]:
    """یک ملاکِ واحد برایِ بله‌پی ⇒ «دکمه‌یِ نمایش‌داده‌شده» و «پرداختِ واقعاً ممکن» هرگز جدا نمی‌افتند (B11)."""
    return await bale_credentials_service.methods(session, shop_bot, row, include_manual=include_manual)


async def _notify_owner_bale_misconfigured(main_bot: Bot, session: AsyncSession, shop_bot, missing: tuple[str, ...]) -> None:
    """B11: مشتری پیامِ فنی نمی‌بیند؛ به‌جایش فروشگاه‌دار دقیقاً می‌فهمد چه چیزی کم است."""
    now = time.monotonic()
    last = _last_owner_misconfig_alert.get(shop_bot.id)
    if last is not None and now - last < _OWNER_ALERT_COOLDOWN_SECONDS:
        return
    _last_owner_misconfig_alert[shop_bot.id] = now
    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None:
        return
    try:
        await main_bot.send_message(owner.telegram_id, main_texts.bale_misconfigured_notice(missing))
    except TelegramAPIError:
        logger.warning("اطلاعِ ناقص‌بودنِ پیکربندیِ بله‌پی به فروشگاه‌دار نرسید.", exc_info=True)


def _awaiting(rows) -> bool:
    return bool(rows) and all(order_state.value_of(r.status) == order_state.AWAITING_PAYMENT for r in rows)


async def _ctx(session: AsyncSession, bot_id: int, tg_id: int, key: str):
    shop_bot, customer = await _resolve(session, bot_id, tg_id)
    rows = await _load_group(session, shop_bot, customer, key) if (shop_bot and customer) else []
    if rows and await order_payment_service.expire_if_overdue(session, rows):
        await session.commit()  # expire-on-read: مهلت گذشته ⇒ همین‌جا منقضی (و رزرو آزاد)
    return shop_bot, customer, rows


async def _edit(callback: CallbackQuery, text: str, markup=None) -> None:
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except TelegramAPIError:
        await callback.message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("pm_menu:"))
async def pm_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, _customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    methods = await _pay_methods(session, shop_bot, await payment_settings_service.get(session, shop_bot.id))
    if not methods:
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        return
    await callback.answer()
    total = order_transition_service.group_total_toman(rows)
    await _edit(callback, texts.pay_choose_method_text(total), keyboards.payment_methods_keyboard(key, methods))


@router.callback_query(F.data.startswith("pm_manual:"))
async def pm_manual(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not rows:
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    if all(order_state.value_of(r.status) == order_state.PENDING for r in rows):
        await callback.answer()  # دابل‌تپ
        return
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    settings_row = await payment_settings_service.get(session, shop_bot.id)
    if payment_settings_service.METHOD_MANUAL not in await _pay_methods(session, shop_bot, settings_row):
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        return
    result = await order_transition_service.transition_group(
        session, rows[0], order_state.PENDING, actor_type="customer", actor_ref=str(customer.id)
    )
    if not result.ok:
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    admin_settings = await get_admin_settings(session)
    order_payment_service.set_group_deadline(rows, admin_settings.order_reservation_minutes)
    for row in rows:
        row.payment_method = payment_settings_service.METHOD_MANUAL
    await session.commit()
    await callback.answer()
    await _edit(callback, texts.PAY_MANUAL_CHOSEN)
    if result.changed:
        owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
        if owner is not None:
            total = order_transition_service.group_total_toman(rows)
            text = (
                f"🤝 سفارشِ {texts.order_code(rows)} — {display_user(customer, 'short')} پرداختِ دستی/هماهنگی رو انتخاب کرد.\n"
                f"مبلغ: {format_toman(total)}\nتایید یا رد کن:"
            )
            try:
                await main_bot.send_message(owner.telegram_id, text, reply_markup=main_keyboards.cart_group_notification_keyboard(key))
            except TelegramAPIError:
                logger.exception("اطلاعِ انتخابِ پرداختِ دستی به فروشگاه‌دار ناموفق بود.")


@router.callback_query(F.data.startswith("pm_card:"))
async def pm_card(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, _customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    settings_row = await payment_settings_service.get(session, shop_bot.id)
    if payment_settings_service.METHOD_CARD not in await _pay_methods(session, shop_bot, settings_row, include_manual=False):
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        return
    _payment, expires = await order_payment_service.start_payment(session, rows, payment_settings_service.METHOD_CARD, settings_row)
    await session.commit()
    await callback.answer()
    text = texts.card_payment_instructions(
        payment_settings_service.get_card_number(settings_row),
        settings_row.card_holder_name,
        settings_row.bank_name,
        order_transition_service.group_total_toman(rows),
        texts.order_code(rows),
        format_jalali_datetime(to_tehran(expires)),
    )
    await _edit(callback, text, keyboards.receipt_keyboard(key))


@router.callback_query(F.data.startswith("pm_bale:"))
async def pm_bale(callback: CallbackQuery, session: AsyncSession, main_bot: Bot) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, _customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    settings_row = await payment_settings_service.get(session, shop_bot.id)
    status = await bale_credentials_service.shop_status(session, shop_bot, settings_row)
    if not status.available:
        # B11: دکمه با همان ملاکِ `shop_status` ساخته می‌شود، پس این شاخه یعنی کیبوردِ کهنه.
        # مشتری فقط یک پیامِ مودبانه می‌بیند؛ جزئیاتِ فنی برایِ فروشگاه‌دار می‌رود.
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        await _notify_owner_bale_misconfigured(main_bot, session, shop_bot, status.missing)
        return
    total = order_transition_service.group_total_toman(rows)
    payload = f"cartgroup-{key}-{secrets.token_hex(8)}"
    try:
        pay_url = await bale_service.create_invoice_link(
            status.bot_token,
            status.provider_token,
            title="پرداختِ سفارش",
            description=f"سفارش {texts.order_code(rows)}",
            payload=payload,
            amount_rial=bale_service.toman_to_rial(total),
        )
    except bale_service.BaleError:
        logger.exception("ساختِ لینکِ بله‌پی برایِ گروهِ %s ناموفق بود.", key)
        await callback.answer(texts.PAY_ONLINE_LINK_FAILED, show_alert=True)
        return
    payment, expires = await order_payment_service.start_payment(session, rows, payment_settings_service.METHOD_BALE, settings_row)
    payment.provider_ref = payload[:160]
    await session.commit()
    await callback.answer()
    await _edit(callback, texts.online_pay_offer("bale", total, format_jalali_datetime(to_tehran(expires))), keyboards.online_pay_keyboard(pay_url, key))


@router.callback_query(F.data.startswith("pm_zarinpal:"))
async def pm_zarinpal(callback: CallbackQuery, session: AsyncSession) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, _customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    settings_row = await payment_settings_service.get(session, shop_bot.id)
    if payment_settings_service.METHOD_ZARINPAL not in await _pay_methods(session, shop_bot, settings_row, include_manual=False) or not settings.webhook_base_url:
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        return
    total = order_transition_service.group_total_toman(rows)
    callback_url = f"{settings.webhook_base_url.rstrip('/')}/payment/zarinpal/callback"
    try:
        merchant = decrypt_token(settings_row.zarinpal_merchant_id_enc)
        authority, pay_url = await zarinpal_service.request_payment(merchant, total, callback_url, f"سفارش {texts.order_code(rows)}")
    except Exception:  # noqa: BLE001 — ZarinpalError/رمزگشایی؛ جزئیات در لاگ، پیامِ مودبانه به مشتری
        logger.exception("درخواستِ پرداختِ زرین‌پال برایِ گروهِ %s ناموفق بود.", key)
        await callback.answer(texts.PAY_ONLINE_LINK_FAILED, show_alert=True)
        return
    payment, expires = await order_payment_service.start_payment(
        session, rows, payment_settings_service.METHOD_ZARINPAL, settings_row, fresh=True
    )
    payment.provider_ref = authority[:160]
    await session.commit()
    await callback.answer()
    await _edit(callback, texts.online_pay_offer("zarinpal", total, format_jalali_datetime(to_tehran(expires))), keyboards.online_pay_keyboard(pay_url, key))


@router.callback_query(F.data.startswith("pay_receipt:"))
async def pay_receipt_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    key = callback.data.split(":", 1)[1]
    shop_bot, _customer, rows = await _ctx(session, callback.bot.id, callback.from_user.id, key)
    if not _awaiting(rows):
        await callback.answer(texts.PAY_STALE, show_alert=True)
        return
    settings_row = await payment_settings_service.get_or_create(session, shop_bot.id)
    if payment_settings_service.METHOD_CARD not in await _pay_methods(session, shop_bot, settings_row, include_manual=False):
        await callback.answer(texts.PAY_METHOD_UNAVAILABLE, show_alert=True)
        return
    group_id = order_transition_service.group_key(rows[0])
    payment = await order_payment_service.get_active_payment(session, shop_bot.id, group_id, "card")
    if payment is None:
        # بعد از ردِ رسید پرداختِ فعالی نمونده ⇒ تلاشِ تازه (سقفِ دفعات چک می‌شه)
        attempts = await order_payment_service.count_attempts(session, shop_bot.id, group_id, "card")
        if attempts >= settings_row.max_receipt_attempts:
            await callback.answer(texts.PAY_TOO_MANY_ATTEMPTS, show_alert=True)
            return
        await order_payment_service.start_payment(session, rows, payment_settings_service.METHOD_CARD, settings_row)
        await session.commit()
    await state.set_state(PaymentStates.waiting_receipt)
    await state.update_data(pay_key=key)
    await callback.answer()
    await callback.message.answer(texts.PAY_ASK_RECEIPT)


async def _download(message: Message, file_id: str, size: int | None) -> bytes | None:
    if size is not None and size > order_payment_service.MAX_RECEIPT_BYTES:
        await message.answer(texts.PAY_RECEIPT_TOO_BIG)
        return None
    try:
        file_io = await message.bot.download(file_id)
        data = file_io.read() if file_io is not None else b""
    except TelegramAPIError:
        data = b""
    if not data:
        await message.answer(texts.PAY_RECEIPT_DOWNLOAD_FAILED)
        return None
    if len(data) > order_payment_service.MAX_RECEIPT_BYTES:
        await message.answer(texts.PAY_RECEIPT_TOO_BIG)
        return None
    return data


async def _finish_receipt(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    main_bot: Bot,
    *,
    data: bytes | None,
    filename: str | None,
    is_photo: bool,
    tracking: str | None,
    receipt_text: str | None = None,
) -> None:
    fsm = await state.get_data()
    key = fsm.get("pay_key") or ""
    await state.clear()  # دابل‌ارسال: اول state پاک می‌شه
    shop_bot, customer, rows = await _ctx(session, message.bot.id, message.from_user.id, key)
    if not _awaiting(rows):
        await message.answer(texts.PAY_STALE)
        return
    # قفلِ سطری روی گروه (رقابتِ ارسالِ هم‌زمان)
    rows = await order_payment_service.group_rows(session, shop_bot.id, key, lock=True)
    settings_row = await payment_settings_service.get_or_create(session, shop_bot.id)
    sha = order_payment_service.receipt_sha256(data) if data else (
        order_payment_service.receipt_sha256(receipt_text.encode()) if receipt_text else None  # رسیدِ متنیِ تکراری هم پرچم می‌خورد
    )
    try:
        payment = await order_payment_service.submit_receipt(
            session, rows, settings_row, file_sha256=sha, tracking_ref=tracking, receipt_text=receipt_text
        )
    except order_payment_service.ReceiptError as error:
        await message.answer(texts.PAY_TOO_MANY_ATTEMPTS if error.code == "too_many_attempts" else texts.PAY_STALE)
        return
    await session.commit()
    await message.answer(texts.PAY_RECEIPT_RECEIVED)

    owner = await shop_owner_service.get_by_id(session, shop_bot.shop_owner_id)
    if owner is None:
        return
    from app.bots.main_bot import texts as main_texts

    total = order_transition_service.group_total_toman(rows)
    caption = main_texts.receipt_submitted_notification(rows, payment, customer, total)
    # W5/2.1: تحلیلِ AIِ رسید — فقط مشورتی (یک خط زیرِ پیام)؛ هر شکستی فقط یعنی «بدونِ خط»، نه تاخیر/خطا در رسیدگیِ رسید.
    if data and is_photo and settings_row.receipt_ai_enabled:
        try:
            card = payment_settings_service.get_card_number(settings_row)
            advisory = await receipt_ai_service.analyze_receipt(
                session,
                owner=owner,
                admin_settings=await get_admin_settings(session),
                payment=payment,
                image_bytes=data,
                expected_toman=total,
                expected_last4=card[-4:] if card else None,
                order_created_at=rows[0].created_at,
            )
        except Exception:  # noqa: BLE001
            logger.exception("تحلیلِ رسیدِ %s شکست خورد؛ بدونِ خطِ مشورتی ادامه می‌دیم.", payment.id)
            advisory = None
        if advisory:
            caption = f"{caption}\n\n{advisory}"
    markup = main_keyboards.receipt_review_keyboard(payment.id, key)
    try:
        if data and is_photo:
            await main_bot.send_photo(owner.telegram_id, BufferedInputFile(data, filename=filename or "receipt.jpg"), caption=caption, reply_markup=markup)
        elif data:
            await main_bot.send_document(owner.telegram_id, BufferedInputFile(data, filename=filename or "receipt"), caption=caption, reply_markup=markup)
        else:
            await main_bot.send_message(owner.telegram_id, caption, reply_markup=markup)
    except TelegramAPIError:
        logger.exception("ارسالِ رسید به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


@router.message(PaymentStates.waiting_receipt, F.photo)
async def receipt_photo(message: Message, state: FSMContext, session: AsyncSession, main_bot: Bot) -> None:
    photo = message.photo[-1]
    data = await _download(message, photo.file_id, getattr(photo, "file_size", None))
    if data is None:
        return
    await _finish_receipt(message, state, session, main_bot, data=data, filename="receipt.jpg", is_photo=True, tracking=None)


@router.message(PaymentStates.waiting_receipt, F.document)
async def receipt_document(message: Message, state: FSMContext, session: AsyncSession, main_bot: Bot) -> None:
    document = message.document
    mime = (getattr(document, "mime_type", None) or "").lower()
    if not mime.startswith("image/"):
        await message.answer(texts.PAY_RECEIPT_INVALID)
        return
    data = await _download(message, document.file_id, getattr(document, "file_size", None))
    if data is None:
        return
    await _finish_receipt(message, state, session, main_bot, data=data, filename=document.file_name or "receipt", is_photo=False, tracking=None)


@router.message(PaymentStates.waiting_receipt, F.text)
async def receipt_text(message: Message, state: FSMContext, session: AsyncSession, main_bot: Bot) -> None:
    raw = (message.text or "").strip()
    if raw == "/cancel":
        await state.clear()
        await message.answer(texts.PAY_CANCELLED_FLOW)
        return
    tracking = order_payment_service.extract_tracking_ref(raw)
    if tracking is not None:  # فقط یک شماره‌پیگیری
        await _finish_receipt(message, state, session, main_bot, data=None, filename=None, is_photo=False, tracking=tracking)
        return
    parsed = order_payment_service.parse_receipt_text(raw)  # W5: رسیدِ متنیِ آزاد (متنِ کپی‌شده از اپ بانک/پیامک)
    if parsed is None:
        await message.answer(texts.PAY_RECEIPT_INVALID)
        return
    text, labeled_tracking = parsed
    await _finish_receipt(
        message, state, session, main_bot, data=None, filename=None, is_photo=False, tracking=labeled_tracking, receipt_text=text
    )


async def maybe_handle_payment_claim(message: Message, session: AsyncSession, shop_bot, customer: Customer) -> bool:
    """«پرداخت کردم/واریز کردم» وقتی سفارشِ awaiting_payment داره ⇒ راهنمایِ «📎 ارسالِ رسید» به‌جایِ AI (هزینه ۰)."""
    if shop_bot.tenant_mode == TenantMode.CONSULTATION or not order_payment_service.looks_like_payment_claim(message.text or ""):
        return False
    result = await session.execute(
        select(OrderConsultation)
        .where(OrderConsultation.customer_id == customer.id, OrderConsultation.status == OrderStatus.AWAITING_PAYMENT)
        .order_by(OrderConsultation.id.desc())
    )
    row = result.scalars().first()
    if row is None:
        return False
    key = order_transition_service.group_key(row)
    await message.answer(texts.PAY_CLAIM_GUIDE, reply_markup=keyboards.receipt_keyboard(key))
    return True
