from __future__ import annotations

import asyncio
import logging
import re
import secrets
from decimal import Decimal, InvalidOperation

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.common.keyboard_utils import NO_INLINE_KEYBOARD
from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsAdmin, IsSuperAdmin
from app.bots.main_bot.handlers.owner_common import parse_suffix_int
from app.bots.main_bot.states import (
    AdminChannelStates,
    AdminGiftStates,
    AdminPricingStates,
    AdminRoleStates,
    AdminSettingsStates,
    AdminWalletCorrectionStates,
    AiPoolStates,
    BroadcastStates,
    ModerationStates,
)
from app.config import settings
from app.database.models import AiKeyCapability, AuditEventType, DiscountType, PaymentPurpose, PaymentStatus, WalletTransactionReason
from app.services import (
    admin_role_service,
    admin_settings_service,
    ai_pool_service,
    ai_service,
    audit_log_service,
    bale_bot_service,
    bale_credentials_service,
    bale_service,
    bot_branding_service,
    channel_service,
    commission_receivable_service,
    credit_batch_service,
    discount_service,
    excel_export_service,
    moderation_service,
    notification_service,
    otp_service,
    payment_event_service,
    payment_service,
    prompt_defaults,
    shop_bot_service,
    identity_service,
    shop_owner_service,
    sms_service,
    stats_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils import csv_export
from app.utils.jalali import format_jalali_datetime
from app.utils.validators import fa_text, format_toman, normalize_telegram_username, parse_signed_toman_amount, to_e164_iran

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

# زیرمجموعه‌ی سوپرادمین‌محورِ پنل: تنظیماتِ قیمت/تخفیف، تنظیماتِ کلیدها،
# استخرِ کلیدهایِ AI، و مدیریتِ خودِ ادمین‌ها. یه IsSuperAdmin روی کلِ این
# روتر یعنی لازم نیست هر هندلر رو جدا نگهبانی کنیم؛ روترِ اصلی (بالا) با
# IsAdmin گسترده‌شده هم سوپرادمین و هم ادمینِ عملیاتی رو قبول می‌کنه، ولی
# این زیرروتر فقط سوپرادمین.
super_router = Router(name="admin_super")
super_router.message.filter(IsSuperAdmin())
super_router.callback_query.filter(IsSuperAdmin())


def _chat_id_arg(channel_id: str) -> str | int:
    stripped = channel_id.strip()
    if stripped.lstrip("-").isdecimal():
        return int(stripped)
    return stripped


def _owner_display_name(owner) -> str:
    return identity_service.display_user(owner, "short")


async def _roles_keyboard(session: AsyncSession, roles):
    return keyboards.admin_roles_list_keyboard(roles, await _identity_labels(session, [r.telegram_id for r in roles]))


async def _identity_labels(session: AsyncSession, telegram_ids) -> dict[int, str]:
    """telegram_id → هویتِ متنی (برایِ فهرست‌هایِ ادمین)؛ کسی که ثبت‌نام نکرده برچسبِ ثابت می‌گیره، نه عدد."""
    labels: dict[int, str] = {}
    for tg_id in telegram_ids:
        owner = await shop_owner_service.get_by_telegram_id(session, tg_id)
        labels[tg_id] = identity_service.display_user(owner, "short") if owner else "ادمین (هنوز ثبت‌نام نکرده)"
    return labels


# =============================================================================
# ورودی پنل ادمین
# =============================================================================
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_super = message.from_user.id in settings.admin_ids
    await message.answer(texts.ADMIN_PANEL_INTRO, reply_markup=keyboards.admin_panel_keyboard(is_super))


# =============================================================================
# تایید/رد پرداخت (منتقل‌شده از panel.py طبق تصمیمِ بازآرایی)
# =============================================================================
@router.callback_query(F.data.startswith("admin_approve_payment:"))
async def cb_admin_approve_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_id = parse_suffix_int(callback.data, "admin_approve_payment:")
    payment = await payment_service.get_by_id(session, payment_id) if payment_id is not None else None
    if payment is None or payment.status != PaymentStatus.PENDING:
        await callback.answer("این پرداخت قبلاً بررسی شده.", show_alert=True)
        return

    # P24 (امنیت): تایید/ردِ پرداخت پولِ یکِ فروشگاه‌دارِ مشخص است، پس دقیقاً مثلِ suspend/هدیه/
    # اصلاحِ کیف‌پول باید دامنه‌مند باشد. تا پیشِ این، ادمینِ عملیاتیِ دامنه‌دار با حدس‌زدنِ
    # payment_id در callback_data می‌توانست شارژِ کیف‌پولِ هر فروشگاهِ دیگری را تأیید کند.
    _owner_scope, allowed = await _scoped_owner(session, callback.from_user.id, payment.shop_owner_id)
    if not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return

    owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
    is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
    _effect, reward_info = await payment_service.approve_payment(session, payment, callback.from_user.id)
    if _effect is None:
        # دو ادمین (یا ادمین + وب‌هوک) هم‌زمان زده‌اند؛ برندهٔ رقابت اعتبار را اضافه کرده است.
        await callback.answer("این پرداخت همین حالا توسطِ دیگری بررسی شد.", show_alert=True)
        return

    await callback.answer()
    new_caption = (callback.message.caption or "") + f"\n\n{texts.admin_payment_approved_confirmation(_owner_display_name(owner))}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=NO_INLINE_KEYBOARD)

    try:
        await callback.bot.send_message(
            owner.telegram_id, texts.payment_approved_notification(is_topup, payment.final_amount if is_topup else None)
        )
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ تاییدِ پرداخت به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    if reward_info:
        try:
            await callback.bot.send_message(
                reward_info["referrer_telegram_id"], texts.referrer_reward_notification(reward_info["amount_toman"])
            )
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ پاداشِ معرف به %s ناموفق بود.", reward_info["referrer_telegram_id"])
        try:
            await callback.bot.send_message(
                reward_info["referred_telegram_id"], texts.referred_reward_notification(reward_info["amount_toman"])
            )
        except TelegramAPIError:
            logger.exception("اطلاع‌رسانیِ پاداشِ معرفی‌شده به %s ناموفق بود.", reward_info["referred_telegram_id"])


@router.callback_query(F.data.startswith("admin_reject_payment:"))
async def cb_admin_reject_payment(callback: CallbackQuery, session: AsyncSession) -> None:
    payment_id = parse_suffix_int(callback.data, "admin_reject_payment:")
    payment = await payment_service.get_by_id(session, payment_id) if payment_id is not None else None
    if payment is None or payment.status != PaymentStatus.PENDING:
        await callback.answer("این پرداخت قبلاً بررسی شده.", show_alert=True)
        return

    _owner_scope, allowed = await _scoped_owner(session, callback.from_user.id, payment.shop_owner_id)
    if not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return

    owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
    await payment_service.reject_payment(session, payment, callback.from_user.id)

    await callback.answer()
    new_caption = (callback.message.caption or "") + f"\n\n{texts.admin_payment_rejected_confirmation(_owner_display_name(owner))}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=NO_INLINE_KEYBOARD)

    try:
        await callback.bot.send_message(owner.telegram_id, texts.payment_rejected_notification(None))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ ردِ پرداخت به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


@router.message(F.text == "🧾 صف تایید پرداخت‌ها")
async def payment_queue_stub(message: Message, session: AsyncSession) -> None:
    pending = await payment_service.get_pending_payments(session)
    if not pending:
        await message.answer(texts.ADMIN_NO_PENDING_PAYMENTS)
        return
    await message.answer(
        texts.ADMIN_PENDING_PAYMENTS_INTRO
        + f"\n\n{len(pending)} پرداخت در انتظار تایید هست.\n"
        "یادآوری: هر پرداختِ جدید همون لحظه‌ای که رسیدش ارسال بشه با دکمه‌ی تایید/رد برات فرستاده می‌شه."
    )


# =============================================================================
# آمار سراسری
# =============================================================================
@router.message(Command("admin_stats"))
@router.message(F.text == "📊 آمار سراسری")
async def admin_stats(message: Message, session: AsyncSession) -> None:
    stats = await stats_service.get_platform_stats(session)
    await message.answer(texts.platform_stats_text(stats))


# =============================================================================
# پیام همگانی
# =============================================================================
@router.message(Command("broadcast"))
@router.message(F.text == "📣 پیام همگانی")
async def broadcast_start(message: Message, state: FSMContext) -> None:
    await state.set_state(BroadcastStates.waiting_message)
    await message.answer(texts.ASK_BROADCAST_MESSAGE)


@router.message(BroadcastStates.waiting_message, F.text)
async def broadcast_message_entered(message: Message, state: FSMContext) -> None:
    await state.update_data(broadcast_text=message.text)
    await state.set_state(BroadcastStates.waiting_confirmation)
    await message.answer(texts.broadcast_preview(message.text), reply_markup=keyboards.confirm_broadcast_keyboard())


ADMIN_BROADCAST_PACE_SECONDS = 0.06  # همان درسِ مسیرِ مشتری: بدونِ ریتم، تلگرام flood-wait می‌زند


async def _run_admin_broadcast(bot: Bot, owners, text: str, admin_telegram_id: int) -> None:
    """P24 (امنک/عملکرد): حلقهٔ ارسالِ ادمین قبلاً *داخلِ* هندلر و بدونِ ریتم اجرا می‌شد.

    دو پیامدِ واقعی: ۱) تا پایانِ حلقه، pollingِ رباتِ اصلی رویِ همه‌یِ آپدیت‌ها می‌خوابد
    (چندصد فروشگاه‌دار × تأخیرِ شبکه = دقیقه‌ها بی‌پاسخیِ ربات)، ۲) بدونِ sleep/RetryAfter
    تلگرام flood-wait می‌دهد و بیشترِ پیام‌ها در `except` می‌سوزند در حالی که شمارشِ «sent»
    غلط گزارش می‌شود؛ خطرِ بن‌شدنِ ربات. حالا تسکِ پس‌زمینه با ریتم و یکِ retry.
    """
    sent = 0
    for owner in owners:
        try:
            await bot.send_message(owner.telegram_id, text)
            sent += 1
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after)
            try:
                await bot.send_message(owner.telegram_id, text)
                sent += 1
            except TelegramAPIError:
                logger.info("ارسالِ پیام همگانی به %s (حتی بعدِ retry) ناموفق بود.", owner.telegram_id)
        except TelegramAPIError:
            logger.info("ارسالِ پیام همگانی به %s ناموفق بود (احتمالاً ربات را بلاک کرده).", owner.telegram_id)
        await asyncio.sleep(ADMIN_BROADCAST_PACE_SECONDS)
    try:
        await bot.send_message(admin_telegram_id, texts.broadcast_sent_confirmation(sent))
    except TelegramAPIError:
        logger.exception("خلاصهٔ پیام همگانی به ادمین %s نرسید.", admin_telegram_id)


@router.callback_query(BroadcastStates.waiting_confirmation, F.data == "broadcast_confirm")
async def broadcast_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owners = await shop_owner_service.get_all_registered(session)
    targets = [owner for owner in owners if owner.telegram_id != callback.from_user.id]
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.admin_broadcast_started(len(targets)))
    asyncio.create_task(_run_admin_broadcast(callback.bot, targets, data["broadcast_text"], callback.from_user.id))


@router.callback_query(BroadcastStates.waiting_confirmation, F.data == "broadcast_cancel")
async def broadcast_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.BROADCAST_CANCELLED)


# =============================================================================
# مدیریت کانال‌های اجباری
# =============================================================================
async def _render_channel_list(message: Message, session: AsyncSession) -> None:
    channels = await channel_service.get_mandatory_channels(session)
    text = texts.MANDATORY_CHANNELS_INTRO if channels else texts.NO_MANDATORY_CHANNELS
    await message.answer(text, reply_markup=keyboards.mandatory_channels_list_keyboard(channels))


@router.message(F.text == "📢 مدیریت کانال‌های اجباری")
async def open_channel_management(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await _render_channel_list(message, session)


@router.callback_query(F.data == "admin_channel_list")
async def cb_channel_list(callback: CallbackQuery, session: AsyncSession) -> None:
    channels = await channel_service.get_mandatory_channels(session)
    text = texts.MANDATORY_CHANNELS_INTRO if channels else texts.NO_MANDATORY_CHANNELS
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboards.mandatory_channels_list_keyboard(channels))


@router.callback_query(F.data == "admin_channel_add")
async def cb_channel_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminChannelStates.waiting_name)
    await callback.answer()
    await callback.message.answer(texts.ASK_CHANNEL_NAME)


@router.message(AdminChannelStates.waiting_name, F.text)
async def channel_add_name(message: Message, state: FSMContext) -> None:
    await state.update_data(channel_name=message.text.strip())
    await state.set_state(AdminChannelStates.waiting_channel_proof)
    await message.answer(texts.ASK_CHANNEL_PROOF_ADMIN)


async def _resolve_main_channel(message: Message) -> tuple[str, str | None] | None:
    channel_id: str | None = None
    username_link: str | None = None

    if message.forward_from_chat is not None:
        channel_id = str(message.forward_from_chat.id)
    elif message.text and message.text.strip().startswith("@"):
        username = message.text.strip()
        try:
            chat = await message.bot.get_chat(username)
        except TelegramAPIError:
            return None
        channel_id = str(chat.id)
        username_link = f"https://t.me/{username.lstrip('@')}"

    if channel_id is None:
        return None

    try:
        me = await message.bot.get_me()
        member = await message.bot.get_chat_member(_chat_id_arg(channel_id), me.id)
        if member.status not in ("administrator", "creator"):
            return None
    except TelegramAPIError:
        return None

    invite_link = username_link
    if invite_link is None:
        try:
            link_obj = await message.bot.create_chat_invite_link(_chat_id_arg(channel_id))
            invite_link = link_obj.invite_link
        except TelegramAPIError:
            invite_link = None

    return channel_id, invite_link


@router.message(AdminChannelStates.waiting_channel_proof)
async def channel_add_proof(message: Message, state: FSMContext) -> None:
    resolved = await _resolve_main_channel(message)
    if resolved is None:
        await message.answer(texts.CHANNEL_PROOF_INVALID)
        return

    channel_id, invite_link = resolved
    await state.update_data(channel_id=channel_id, invite_link=invite_link)
    await state.set_state(AdminChannelStates.waiting_is_primary)
    await message.answer(
        texts.ASK_CHANNEL_IS_PRIMARY, reply_markup=keyboards.yes_no_keyboard("admin_channel_primary:yes", "admin_channel_primary:no")
    )


@router.callback_query(AdminChannelStates.waiting_is_primary, F.data.startswith("admin_channel_primary:"))
async def channel_add_primary_choice(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    is_primary = callback.data.split(":")[1] == "yes"
    data = await state.get_data()

    channel = await channel_service.create_channel(session, data["channel_id"], data["channel_name"], data.get("invite_link"), is_primary)

    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.channel_added_confirmation(channel.name))
    await _render_channel_list(callback.message, session)


@router.callback_query(F.data.startswith("admin_channel_delete:"))
async def cb_channel_delete(callback: CallbackQuery) -> None:
    channel_pk = int(callback.data.split(":")[1])
    await callback.answer()
    await callback.message.edit_text(texts.ADMIN_CHANNEL_DELETE_CONFIRM, reply_markup=keyboards.confirm_delete_channel_keyboard(channel_pk))


@router.callback_query(F.data.startswith("admin_channel_delete_confirm:"))
async def cb_channel_delete_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    channel_pk = int(callback.data.split(":")[1])
    channel = await channel_service.get_by_id(session, channel_pk)
    if channel is None:
        await callback.answer()
        await _render_channel_list(callback.message, session)
        return

    name = channel.name
    await channel_service.delete_channel(session, channel_pk)
    await callback.answer()
    await callback.message.edit_text(texts.channel_deleted_confirmation(name))
    await _render_channel_list(callback.message, session)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# =============================================================================
# تنظیمات قیمت و تخفیف
# =============================================================================
@super_router.message(F.text == "💰 تنظیمات قیمت و تخفیف")
async def open_pricing_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_pricing_menu_keyboard())


@super_router.callback_query(F.data == "admin_pricing_menu")
async def cb_pricing_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_pricing_menu_keyboard())


@super_router.callback_query(F.data == "admin_toggle_sms")
async def cb_toggle_sms(callback: CallbackQuery, session: AsyncSession) -> None:
    """A3: درِ سرویسِ پیامک. خاموش ⇒ همان مسیرِ بدونِ پیامکِ امروز (ثبت‌نام هیچ‌وقت نمی‌خوابد)."""
    admin_settings = await get_admin_settings(session)
    admin_settings.sms_enabled = not admin_settings.sms_enabled
    await session.flush()
    sent = await otp_service.sent_count_within(session)
    await callback.answer(fa_text(texts.SMS_SENT_VOLUME_LINE, days=otp_service.COST_WINDOW_DAYS, count=sent))
    if admin_settings.sms_enabled and not (admin_settings.sms_api_key or "").strip():
        await callback.message.answer(texts.SMS_ENABLED_WITHOUT_KEY)
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_branding_sync")
async def cb_branding_sync(callback: CallbackQuery, session: AsyncSession, bot_manager, bot: Bot) -> None:
    """A2 + P21-A: «همین الان» بیوگرافیِ همه‌یِ ربات‌هایِ فروشگاهی (تلگرام و بله) را بازبینی کن.

    force=True یعنی نوبتِ per-ربات نادیده گرفته می‌شود (درخواستِ صریحِ ادمین)، پس شمارشِ
    `shops`/`total` با حالتِ عادیِ پاسِ دوره‌ای فرق می‌کند.
    """
    await callback.answer()
    counts = await bot_branding_service.sync_all(session, bot_manager, bot, force=True)
    if not counts["total"]:
        await callback.message.answer(texts.BRANDING_SAVED_NO_BOTS)
        return
    await callback.message.answer(fa_text(texts.BRANDING_SYNC_RESULT, **counts))
    if counts["error"]:
        await callback.message.answer(fa_text(texts.BRANDING_SYNC_FAILED, error=counts["error"]))


@super_router.callback_query(F.data == "admin_branding_report")
async def cb_branding_report(callback: CallbackQuery, session: AsyncSession) -> None:
    """P21-A: کدام فروشگاه‌ها بیشترین دستکاری/حذفِ بیو را دارند (ستونِ شمارنده تا حالا هیچ‌جا دیده نمی‌شد)."""
    await callback.answer()
    admin_settings = await get_admin_settings(session)
    rows = await bot_branding_service.tamper_report(session)
    if not rows:
        await callback.message.answer(fa_text(texts.BRANDING_REPORT_EMPTY, minutes=bot_branding_service.interval_of(admin_settings)))
        return
    items = [
        fa_text(texts.BRANDING_REPORT_ITEM, 
            username=row["bot_username"] or f"رباتِ #{row['shop_bot_id']}",
            count=row["tamper_count"],
            checked=format_jalali_datetime(row["checked_at"]) if row["checked_at"] else texts.BRANDING_REPORT_NEVER,
        )
        for row in rows
    ]
    await callback.message.answer(
        fa_text(texts.BRANDING_REPORT_TITLE, minutes=bot_branding_service.interval_of(admin_settings)) + "\n".join(items)
    )


@super_router.callback_query(F.data == "admin_toggle_zarinpal")
async def cb_toggle_zarinpal(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.zarinpal_enabled = not admin_settings.zarinpal_enabled
    await session.flush()
    await callback.answer(texts.switch_toast("زرین‌پال از فروشگاه‌دارها", admin_settings.zarinpal_enabled))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_bale_pay")
async def cb_toggle_bale_pay(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.bale_pay_enabled = not admin_settings.bale_pay_enabled
    await session.flush()
    await callback.answer(texts.switch_toast("بله‌پی از فروشگاه‌دارها", admin_settings.bale_pay_enabled))
    if admin_settings.bale_pay_enabled and not admin_settings.bale_provider_token:
        # A1: توکنِ درگاهِ سراسری فقط پشتیبان است؛ بدونِ آن هر فروشگاه باید توکنِ درگاهِ خودش را داشته باشد.
        await callback.message.answer(texts.BALE_ENABLED_WITHOUT_GLOBAL_PROVIDER)
    if admin_settings.bale_pay_enabled and not bale_credentials_service.bot_username():
        # P26: لینکِ پرداخت به چتِ همان رباتِ بله می‌رود، پس نامِ کاربریِ شناخته‌شده لازم است.
        # تا `getMe` جواب ندهد دکمه ساخته می‌شود ولی لینکی ندارد — همان‌جا به ادمین گفته می‌شود.
        await callback.message.answer(texts.BALE_PAY_BOT_NOT_CONNECTED)
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_recalc_wallet_cost")
async def cb_recalc_wallet_cost(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    new_cost = wallet_service.compute_cost_per_1k_tokens_from_formula(admin_settings)
    admin_settings.wallet_cost_per_1k_tokens_toman = new_cost
    await session.flush()
    await callback.answer()
    await callback.message.answer(texts.admin_wallet_cost_recalculated(new_cost))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_registrations")
async def cb_toggle_registrations(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.allow_new_registrations = not admin_settings.allow_new_registrations
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"allow_new_registrations -> {admin_settings.allow_new_registrations}",
    )
    await session.flush()
    await callback.answer(texts.switch_toast("ثبت‌نامِ کاربرانِ جدید", admin_settings.allow_new_registrations))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_topups")
async def cb_toggle_topups(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.allow_wallet_topups = not admin_settings.allow_wallet_topups
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"allow_wallet_topups -> {admin_settings.allow_wallet_topups}",
    )
    await session.flush()
    await callback.answer(texts.switch_toast("شارژِ کیف‌پول", admin_settings.allow_wallet_topups))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_commission")
async def cb_toggle_commission(callback: CallbackQuery, session: AsyncSession) -> None:
    """PHASE 5D: روشن/خاموشِ کمیسیونِ درصدی. تغییر، سفارش‌هایِ درجریان را عوض نمی‌کند
    (نرخِشان snapshot شده) و رویِ سفارش‌هایِ تسویه‌شده هیچ اثری ندارد."""
    admin_settings = await get_admin_settings(session)
    admin_settings.commission_enabled = not admin_settings.commission_enabled
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"commission_enabled -> {admin_settings.commission_enabled}، نرخ {admin_settings.commission_percent}٪",
    )
    await session.flush()
    await callback.answer(
        fa_text(texts.COMMISSION_TOGGLED_ON, percent=admin_settings.commission_percent)
        if admin_settings.commission_enabled
        else texts.COMMISSION_TOGGLED_OFF
    )
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_bale_bots")
async def cb_toggle_bale_shop_bots(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    """P19: رونمایی/پنهان‌کردنِ «رباتِ بله‌یِ خودِ فروشگاه».

    پنهان ⇒ نه دکمه‌ای در پنلِ فروشگاه‌دار می‌ماند نه هیچ اتصالِ بله‌ای باز؛ وقتی روشن کردی،
    فروشگاه‌هایی که توکن ثبت کرده‌اند بی‌درنگ وصل می‌شوند."""
    admin_settings = await get_admin_settings(session)
    admin_settings.bale_shop_bots_enabled = not admin_settings.bale_shop_bots_enabled
    now_enabled = admin_settings.bale_shop_bots_enabled
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"bale_shop_bots_enabled -> {now_enabled}",
    )
    await session.flush()

    connected = 0
    if now_enabled:
        for shop_bot in await shop_bot_service.get_all_active(session):
            if not bale_bot_service.connectable(shop_bot):
                continue
            try:
                await bot_manager.register_bale(shop_bot)
                connected += 1
            except Exception:
                logger.exception("وصل‌کردنِ اتصالِ بله‌یِ فروشگاه %s ناموفق بود.", shop_bot.id)
    else:
        for shop_bot_id in bot_manager.registered_bale_bot_ids():
            await bot_manager.unregister_bale(shop_bot_id)

    await callback.answer(
        fa_text(texts.BALE_SHOP_BOTS_REVEALED, count=connected) if now_enabled else texts.BALE_SHOP_BOTS_HIDDEN
    )
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_maintenance")
async def cb_toggle_maintenance(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.maintenance_mode = not admin_settings.maintenance_mode
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"maintenance_mode -> {admin_settings.maintenance_mode}",
    )
    await session.flush()
    extra = " — همه‌یِ ربات‌ها موقتاً پاسخ نمی‌دن" if admin_settings.maintenance_mode else ""
    await callback.answer(texts.switch_toast("حالتِ تعمیر", admin_settings.maintenance_mode) + extra)
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_nightly_report")
async def cb_toggle_nightly_report(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.nightly_report_enabled = not admin_settings.nightly_report_enabled
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"nightly_report_enabled -> {admin_settings.nightly_report_enabled}",
    )
    await session.flush()
    await callback.answer(texts.switch_toast("گزارشِ شبانه", admin_settings.nightly_report_enabled))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_knowledge_gap")
async def cb_toggle_knowledge_gap(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.knowledge_gap_enabled = not admin_settings.knowledge_gap_enabled
    await audit_log_service.log(
        session,
        AuditEventType.KILL_SWITCH_TOGGLED,
        actor_telegram_id=callback.from_user.id,
        details=f"knowledge_gap_enabled -> {admin_settings.knowledge_gap_enabled}",
    )
    await session.flush()
    await callback.answer(texts.switch_toast("تشخیصِ سوال‌هایِ بی‌جواب", admin_settings.knowledge_gap_enabled))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


# --- کدهای تخفیف ---
async def _render_discounts_list(message: Message, session: AsyncSession) -> None:
    codes = await discount_service.get_all_codes(session)
    await message.edit_text(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_discounts_list_keyboard(codes))


@super_router.callback_query(F.data == "admin_pricing_discounts")
async def cb_pricing_discounts(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_discounts_list(callback.message, session)


@super_router.callback_query(F.data.startswith("admin_discount_toggle:"))
async def cb_discount_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    code_id = int(callback.data.split(":")[1])
    code = await discount_service.toggle_code_active(session, code_id)
    await callback.answer(texts.switch_toast(f"کدِ تخفیفِ «{code.code}»" if code else "کدِ تخفیف", bool(code and code.is_active)))
    await _render_discounts_list(callback.message, session)


@super_router.callback_query(F.data == "admin_discount_add")
async def cb_discount_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPricingStates.waiting_discount_code)
    await callback.answer()
    await callback.message.answer(texts.ADMIN_ASK_DISCOUNT_CODE_NAME)


@super_router.message(AdminPricingStates.waiting_discount_code, F.text)
async def discount_code_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    code = message.text.strip().upper()
    if not (code.isascii() and code.isalnum()):
        await message.answer(texts.ADMIN_DISCOUNT_CODE_INVALID)
        return

    existing = await discount_service.get_all_codes(session)
    if any(c.code == code for c in existing):
        await message.answer(texts.ADMIN_DISCOUNT_CODE_DUPLICATE)
        return

    await state.update_data(discount_code=code)
    # P25: «مبلغِ ثابت» از پنل حذف شد — هر کدِ تازه‌ای درصدی است، پس مرحلهٔ پرسیدنِ نوع هم نیست.
    await state.set_state(AdminPricingStates.waiting_discount_value)
    await message.answer(texts.ADMIN_ASK_DISCOUNT_VALUE)


@super_router.callback_query(F.data.startswith("discount_type:"))
async def discount_type_removed(callback: CallbackQuery, state: FSMContext) -> None:
    """کیبوردِ کهنهٔ «نوع تخفیف» (P24 و قبل‌تر): دکمهٔ مرده نمی‌ماند و مسیرِ تازه را توضیح می‌دهد."""
    await callback.answer(texts.ADMIN_DISCOUNT_TYPE_REMOVED, show_alert=True)
    await state.clear()


@super_router.message(AdminPricingStates.waiting_discount_value, F.text)
async def discount_value_entered(message: Message, state: FSMContext) -> None:
    try:
        value = Decimal(message.text.strip().replace(",", "").replace("،", ""))
    except InvalidOperation:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    if not (0 < value <= 100):
        await message.answer(texts.ADMIN_INVALID_PERCENT)
        return

    await state.update_data(discount_value=str(value))
    await state.set_state(AdminPricingStates.waiting_discount_max_uses)
    await message.answer(texts.ADMIN_ASK_DISCOUNT_MAX_USES)


@super_router.message(AdminPricingStates.waiting_discount_max_uses, F.text)
async def discount_max_uses_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = message.text.strip()
    max_uses: int | None
    if raw in ("نامحدود", "بی نهایت", "∞"):
        max_uses = None
    else:
        try:
            max_uses = int(raw)
            if max_uses <= 0:
                raise ValueError
        except ValueError:
            await message.answer(texts.ADMIN_INVALID_NUMBER)
            return

    data = await state.get_data()
    code = await discount_service.create_code(
        session, data["discount_code"], DiscountType.PERCENT, Decimal(data["discount_value"]), max_uses, None
    )

    await state.clear()
    await message.answer(texts.admin_discount_code_saved(code.code))
    codes = await discount_service.get_all_codes(session)
    await message.answer(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_discounts_list_keyboard(codes))


# =============================================================================
# تنظیمات کلیدها
# =============================================================================
_TEXT_FIELDS: dict[str, str] = {
    "sms_api_key": texts.ADMIN_ASK_SMS_API_KEY,
    "ai_api_key": texts.ADMIN_ASK_AI_API_KEY,
    "ai_model": texts.ADMIN_ASK_AI_MODEL,
    "ai_base_url": texts.ADMIN_ASK_AI_BASE_URL,
    "zarinpal_merchant_id": texts.ADMIN_ASK_ZARINPAL_MERCHANT_ID,
    "platform_card_number": texts.ADMIN_ASK_PLATFORM_CARD_NUMBER,
    "platform_card_holder_name": texts.ADMIN_ASK_PLATFORM_CARD_HOLDER,
}

_INT_FIELDS: dict[str, str] = {
    "grace_period_hours": texts.ADMIN_ASK_GRACE_PERIOD_HOURS,
    "periodic_report_frequency_days": texts.ADMIN_ASK_REPORT_FREQUENCY_DAYS,
    "nightly_report_hour_utc": texts.ADMIN_ASK_NIGHTLY_REPORT_HOUR,
    "conversation_history_limit": texts.ADMIN_ASK_CONVERSATION_HISTORY_LIMIT,
    "referral_reward_value": texts.ADMIN_ASK_REFERRAL_PERCENT,
    "wallet_cost_per_1k_tokens_toman": texts.ADMIN_ASK_WALLET_COST_PER_1K_TOKENS,
    # P18 · A4: تحلیلِ عکسِ عمومی حذف شد ⇒ این هزینه دیگر تنظیم نمی‌شود (ستون و داده می‌مانند).
    "wallet_cost_receipt_analysis_toman": texts.ADMIN_ASK_WALLET_COST_RECEIPT_ANALYSIS,
    "wallet_cost_voice_transcription_toman": texts.ADMIN_ASK_WALLET_COST_VOICE_TRANSCRIPTION,
    # P21-C (F3): قیمتِ منصفانه — هر دو با ۰ «خاموش» حساب می‌شوند، پس صفرِ مجاز هم هستند.
    "wallet_cost_voice_per_minute_toman": texts.ADMIN_ASK_WALLET_COST_VOICE_PER_MINUTE,
    "wallet_cost_receipt_per_1k_tokens": texts.ADMIN_ASK_WALLET_COST_RECEIPT_PER_1K_TOKENS,
    "wallet_cost_order_detection_toman": texts.ADMIN_ASK_WALLET_COST_ORDER_DETECTION,
    "wallet_topup_validity_months": texts.ADMIN_ASK_WALLET_TOPUP_VALIDITY_MONTHS,
    # PHASE 5A: کمترینِ مبلغِ شارژِ کیف‌پول (سمتِ سرور هم در payment_service چک می‌شود).
    "min_topup_amount_toman": texts.ADMIN_ASK_MIN_TOPUP_AMOUNT,
    "wallet_trial_credit_toman": texts.ADMIN_ASK_WALLET_TRIAL_CREDIT,
    "wallet_low_balance_warning_toman": texts.ADMIN_ASK_WALLET_LOW_BALANCE_WARNING,
    "usd_to_toman_rate": texts.ADMIN_ASK_USD_TO_TOMAN_RATE,
    # P21-A: فاصلهِ بازرسیِ بیو (دقیقه) — پیش‌تر ثابتِ ۶۰ در کد بود.
    "branding_check_minutes": texts.ADMIN_ASK_BRANDING_CHECK_MINUTES,
}

# فیلدهای اعشاری (Decimal) — برای مقادیری مثل هزینه‌ی دلاری یا ضریب که به
# دقتِ زیرِ ۱ واحد نیاز دارن؛ _INT_FIELDS برای این‌ها کافی نیست.
_DECIMAL_FIELDS: dict[str, str] = {
    "ai_cost_usd_per_1m_tokens": texts.ADMIN_ASK_AI_COST_USD,
    "wallet_markup_multiplier": texts.ADMIN_ASK_MARKUP_MULTIPLIER,
    # PHASE 5D: درصدِ کمیسیونِ سفارشِ موفق (اعشاری: ۰٫۵٪، ۱٪، ۱٫۵٪).
    "commission_percent": texts.ADMIN_ASK_COMMISSION_PERCENT,
}

# صفرِ این فیلدهایِ اعشاری معنا دارد (۰٪ = کمیسیون حذف شد)، برخلافِ هزینه/ضریب که صفر بی‌معناست.
_DECIMAL_FIELDS_ALLOW_ZERO: frozenset[str] = frozenset({"commission_percent"})
_DECIMAL_FIELDS_MAX: dict[str, Decimal] = {"commission_percent": Decimal("100")}

# این فیلدها استثنائاً اجازه‌ی صفر دارن (صفر یعنی «غیرفعال»، یا برایِ
# nightly_report_hour_utc، یعنی نیمه‌شبِ UTC — یه ساعتِ کاملاً معتبر).
_INT_FIELDS_ALLOW_ZERO: frozenset[str] = frozenset(
    {
        "referral_reward_value",
        "nightly_report_hour_utc",
        # P21-C (F3): ۰ یعنی «همان نرخِ ثابتِ قبل» ⇒ خاموش‌کردنِ قیمتِ دقیقه‌ای/توکنی.
        "wallet_cost_voice_per_minute_toman",
        "wallet_cost_receipt_per_1k_tokens",
    }
)

# سقفِ مجاز برایِ بعضی فیلدهایِ عددی (مثلاً ساعت باید ۰ تا ۲۳ باشه). فیلدهایی
# که اینجا نیستن سقف ندارن.
_INT_FIELDS_MAX: dict[str, int] = {
    "nightly_report_hour_utc": 23,
    "min_topup_amount_toman": 10_000_000,
    "branding_check_minutes": 1440,
    # سقفِ هزینه‌ها: یکِ اشتباهِ تایپی نباید «هر دقیقهٔ صوت ۱۰۰ میلیون» بسازد.
    "wallet_cost_voice_per_minute_toman": 1_000_000,
    "wallet_cost_receipt_per_1k_tokens": 1_000_000,
    # P24 (بهینه): بقیهٔ فیلدهایِ عددیِ پولی/درصدی هیچ سقفی نداشتند؛ یکِ صفرِ اضافه در
    # «پورسانتِ معرف» یا «اعتبارِ آزمایشی» مستقیم رویِ پولِ کاربر اثر می‌گذارد.
    "referral_reward_value": 100,  # درصد
    "wallet_cost_per_1k_tokens_toman": 1_000_000,
    "wallet_cost_receipt_analysis_toman": 1_000_000,
    "wallet_cost_voice_transcription_toman": 1_000_000,
    "wallet_cost_order_detection_toman": 1_000_000,
    "wallet_trial_credit_toman": 100_000_000,
    "wallet_low_balance_warning_toman": 100_000_000,
    "usd_to_toman_rate": 500_000,
    "grace_period_hours": 720,  # ۳۰ روز
    "periodic_report_frequency_days": 365,
    "conversation_history_limit": 1000,
    "wallet_topup_validity_months": 120,
}

# کفِ مجاز برایِ بعضی فیلدها (پیش‌فرضِ عمومی ۱ است). بازدیدِ بیو زیرِ ۵ دقیقه یعنی هر لوپِ
# زمان‌بند یک get_short_description به‌ازایِ هر ربات ⇒ با صدها ربات، خودِ بازرسی به بارِ
# بی‌دلیلِ شبکه تبدیل می‌شود.
_INT_FIELDS_MIN: dict[str, int] = {"branding_check_minutes": 5}

# فیلدهای متنیِ قابل‌خالی‌کردن: اگه کاربر «خالی» بفرسته، به‌جای اینکه رشته‌ی
# «خالی» ذخیره بشه، مقدار None ذخیره می‌شه (یعنی واقعاً پاک می‌شه).
_NULLABLE_TEXT_FIELDS: dict[str, str] = {
    "branding_text": texts.ADMIN_ASK_BRANDING_TEXT,
    "sms_sender_number": texts.ADMIN_ASK_SMS_SENDER,
    "sms_otp_template": texts.ADMIN_ASK_SMS_TEMPLATE,
    "global_ai_system_prompt": texts.ADMIN_ASK_GLOBAL_SYSTEM_PROMPT,
    "global_ai_prompt_sales": texts.ADMIN_ASK_PROMPT_SALES,
    "global_ai_prompt_consultation": texts.ADMIN_ASK_PROMPT_CONSULTATION,
    "reference_channel_link": texts.ADMIN_ASK_REFERENCE_CHANNEL_LINK,
    "ai_fallback_api_key": texts.ADMIN_ASK_AI_FALLBACK_API_KEY,
    "ai_fallback_model": texts.ADMIN_ASK_AI_FALLBACK_MODEL,
    "ai_fallback_base_url": texts.ADMIN_ASK_AI_FALLBACK_BASE_URL,
    # P18 · A1: هر دو توکنِ بله از پنل قابلِ تنظیم و پاک‌کردن‌اند (رمزنگاری‌شده، اعمال بدونِ ری‌استارت).
    "bale_bot_token": texts.ADMIN_ASK_BALE_BOT_TOKEN,
    "bale_provider_token": texts.ADMIN_ASK_BALE_PROVIDER_TOKEN,
}

# P18 · A1: بعدِ ذخیره‌یِ این فیلدها کشِ اعتبارهایِ بله تازه می‌شود ⇒ تغییر بدونِ ری‌استارت اعمال می‌شود.
# P18 · A3: اعتبارسنجیِ فرمتِ سرشماره و نامِ قالبِ کاوه‌نگار؛ مقدارِ نرمال‌شده را برمی‌گردانند.
_SMS_FORMAT_FIELDS = {
    "sms_sender_number": sms_service.normalize_sender_digits,
    "sms_otp_template": lambda v: v.strip(),
}
_SMS_SENDER_RE = re.compile(r"^\+?[0-9]{4,19}$")
_SMS_TEMPLATE_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _sms_value_error(field: str, raw: str) -> str | None:
    """None ⇒ معتبر. پیامِ فارسی و بدونِ هیچ رازِ فنی."""
    if field == "sms_sender_number":
        candidate = sms_service.normalize_sender_digits(raw) or ""
        return None if _SMS_SENDER_RE.match(candidate) else texts.ADMIN_INVALID_SMS_SENDER
    return None if _SMS_TEMPLATE_RE.match(raw.strip()) else texts.ADMIN_INVALID_SMS_TEMPLATE


_BALE_TOKEN_FIELDS: frozenset[str] = frozenset({"bale_bot_token", "bale_provider_token"})

# P24 (امنیت): این دو آدرس با `aiohttp.post` در app/services/ai_service.py زده می‌شوند و هدرِ
# Authorization را با خود می‌برند ⇒ اگر «آدرس سرویس هوش مصنوعی» به هاستِ داخلی برگردد، کلیدِ AI
# به آنجا می‌رود و SSRF به شبکهٔ داخلیِ سرور ممکن می‌شود. فقط https + ردِ آدرس‌هایِ لوکال.
_URL_FIELDS: frozenset[str] = frozenset({"ai_base_url", "ai_fallback_base_url"})
_INTERNAL_HOST_RE = re.compile(
    r"^(?:localhost|0\.0\.0\.0|::1|\[::1\]|127\.|10\.|192\.168\.|169\.254\.|172\.(?:1[6-9]|2\d|3[01])\.|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.)",
    re.IGNORECASE,
)


def _url_value_error(raw: str) -> str | None:
    """None ⇒ معتبر. آدرسِ سرویس باید httpsِ خالص باشد و به شبکهٔ داخلی نزند."""
    text = (raw or "").strip()
    if not text.startswith("https://"):
        return texts.ADMIN_INVALID_AI_URL
    host = text[len("https://") :].split("/", 1)[0]
    host = host.rsplit("@", 1)[-1].split(":", 1)[0]
    if not host or _INTERNAL_HOST_RE.match(host):
        return texts.ADMIN_INVALID_AI_URL
    return None


@super_router.message(F.text == "🔑 تنظیمات کلیدها")
async def open_settings_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    admin_settings = await admin_settings_service.get_admin_settings(session)
    await message.answer(texts.ADMIN_SETTINGS_MENU_INTRO, reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


async def _refresh_settings_menu(message: Message, session: AsyncSession, group: str | None = None) -> None:
    """بعد از ذخیره، همان صفحه‌ای را نشان می‌دهد که کاربر از آن آمده بود (دسته یا فهرستِ اصلی)."""
    admin_settings = await admin_settings_service.get_admin_settings(session)
    if group in texts.ADMIN_SETTINGS_GROUP_KEYS:
        await message.answer(
            texts.admin_settings_group_intro(group), reply_markup=keyboards.admin_settings_group_keyboard(group, admin_settings)
        )
        return
    await message.answer(texts.ADMIN_SETTINGS_MENU_INTRO, reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


def _setting_group(field: str) -> str | None:
    return texts.ADMIN_SETTING_GROUP.get(field)


@super_router.callback_query(F.data == "admin_settings_menu")
async def cb_admin_settings_menu(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await admin_settings_service.get_admin_settings(session)
    await callback.answer()
    await callback.message.edit_text(
        texts.ADMIN_SETTINGS_MENU_INTRO, reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings)
    )


@super_router.callback_query(F.data.startswith("admin_settings_group:"))
async def cb_admin_settings_group(callback: CallbackQuery, session: AsyncSession) -> None:
    group = (callback.data or "").split(":", 1)[1]
    if group not in texts.ADMIN_SETTINGS_GROUP_KEYS:
        await callback.answer(texts.ADMIN_SETTINGS_STALE_GROUP, show_alert=True)
        return
    admin_settings = await admin_settings_service.get_admin_settings(session)
    await callback.answer()
    await callback.message.edit_text(
        texts.admin_settings_group_intro(group), reply_markup=keyboards.admin_settings_group_keyboard(group, admin_settings)
    )


@super_router.callback_query(F.data == "admin_payment_events")
async def cb_payment_events(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    events = await payment_event_service.recent_events(session, limit=20)
    await callback.message.answer(texts.payment_events_text(events))


@super_router.callback_query(F.data == "admin_commission_debt")
async def cb_commission_debt(callback: CallbackQuery, session: AsyncSession) -> None:
    """P21-C (F4): «پلتفرم چقدر کمیسیونِ نگرفته‌شده دارد؟» — تا پیش‌ازاین فقط در لاگ دیده می‌شد."""
    await callback.answer()
    totals = await commission_receivable_service.summary(session)
    if not totals["open_count"]:
        await callback.message.answer(texts.COMMISSION_DEBT_EMPTY)
        return
    items = [
        fa_text(texts.COMMISSION_DEBT_ITEM, 
            owner=row["owner_label"],
            toman=format_toman(row["amount_toman"]),
            note=row["note"] or "بدونِ یادداشت",
        )
        for row in await commission_receivable_service.open_report(session)
    ]
    await callback.message.answer(
        fa_text(texts.COMMISSION_DEBT_REPORT, 
            count=totals["open_count"],
            toman=format_toman(totals["open_toman"]),
            settled_count=totals["settled_count"],
            items="\n".join(items),
        )
    )


@super_router.callback_query(F.data == "admin_notification_queue")
async def cb_notification_queue(callback: CallbackQuery, session: AsyncSession) -> None:
    """P20: «چند خبرِ پرداختی گم شده؟» — شمارشِ صفِ خروجی + نمونه‌یِ آخرین شکست‌ها (فقط خواندنی)."""
    await callback.answer()
    counts = await notification_service.stats(session)
    if not counts["pending"] and not counts["failed"]:
        await callback.message.answer(fa_text(texts.NOTIFICATION_QUEUE_ALL_CLEAR, sent=counts["sent"]))
        return
    detail = ""
    if counts["failed"]:
        items = [
            fa_text(texts.NOTIFICATION_QUEUE_ITEM, 
                label=row.label or "بی‌برچسب",
                error=(row.last_error or "بدونِ دلیلِ ثبت‌شده")[:90],
                attempts=row.attempts,
            )
            for row in await notification_service.recent_failed(session)
        ]
        when = await notification_service.next_attempt_time(session)
        detail = fa_text(texts.NOTIFICATION_QUEUE_DETAIL, 
            when=format_jalali_datetime(when) if when else "—",
            items="\n".join(items) or texts.NOTIFICATION_QUEUE_NO_ITEM,
        )
    markup = keyboards.notification_queue_retry_keyboard() if counts["failed"] else None
    await callback.message.answer(
        fa_text(texts.NOTIFICATION_QUEUE_REPORT, 
            pending=counts["pending"],
            failed=counts["failed"],
            sent=counts["sent"],
            max_attempts=notification_service.MAX_ATTEMPTS,
            detail=detail,
        ),
        reply_markup=markup,
    )


@super_router.callback_query(F.data == "admin_notification_retry")
async def cb_notification_retry(callback: CallbackQuery, session: AsyncSession) -> None:
    """تلاشِ دوباره با backoffِ تازه؛ بدونِ پاک‌کردنِ تاریخچهٔ شکست."""
    reset = await notification_service.retry_failed(session)
    await callback.answer()
    await callback.message.answer(
        fa_text(texts.NOTIFICATION_QUEUE_RETRY_DONE, count=reset) if reset else texts.NOTIFICATION_QUEUE_RETRY_NONE
    )


@super_router.callback_query(F.data == "admin_bale_selftest")
async def cb_bale_selftest(callback: CallbackQuery, session: AsyncSession) -> None:
    """B13 + A1(د): اول پیکربندی (توکنِ ربات / توکنِ درگاه / رازِ وب‌هوک) هر کدام جدا، بعد
    getMe ← getWebhookInfo ← createInvoiceLink (۱۰٬۰۰۰ ریال). هیچ مقدارِ خامی نمایش داده نمی‌شود."""
    await callback.answer()
    await bale_credentials_service.refresh(session)
    admin_settings = await get_admin_settings(session)
    token = bale_credentials_service.bot_token()
    steps: list[tuple[str, bool, str]] = texts.bale_selftest_config_steps(
        bot_token_set=bool(token),
        bot_token_source="پنلِ ادمین" if admin_settings.bale_bot_token else ".env",
        provider_set=bool(admin_settings.bale_provider_token),
        updates_mode=settings.bale_updates_mode,
        webhook_secret_set=bool(bale_credentials_service.webhook_secret()),
    )
    if not token:
        await callback.message.answer(texts.bale_selftest_report(steps))
        return
    try:
        me = await bale_service.get_me(token)
        steps.append(("getMe (توکنِ ربات و دسترسی به API)", True, f"@{(me or {}).get('username', '?')}"))
    except bale_service.BaleError as exc:
        steps.append(("getMe (توکنِ ربات و دسترسی به API)", False, str(exc)[:200]))
    try:
        info = await bale_service.get_webhook_info(token)
        steps.append(("getWebhookInfo", True, f"url={(info or {}).get('url') or 'تنظیم‌نشده'}"))
    except bale_service.BaleError as exc:
        steps.append(("getWebhookInfo", False, str(exc)[:200]))
    if not admin_settings.bale_provider_token:
        steps.append(("createInvoiceLink", False, "توکنِ درگاهِ بله‌پی در تنظیماتِ ادمین ثبت نشده."))
    else:
        try:
            invoice_result = await bale_service.create_invoice_link(
                token, admin_settings.bale_provider_token, "آزمایش", "آزمایشِ بله‌پی (پرداخت نکن)", f"selftest-{secrets.token_hex(6)}", 10_000
            )
            # P26: خروجیِ این متد شناسهٔ **مینی‌اپ** است، نه آدرس (MEASURED: `invoice_id=…`)؛
            # چیزی که کاربر رویِ آن کلیک می‌کند لینکِ چتِ ربات است و صورتحساب همان‌جا می‌آید.
            # پس «موفق» یعنی دو چیز: توکنِ درگاه کار کرد، و لینکِ پرداخت قابلِ ساخت است.
            await bale_credentials_service.refresh(session)
            link = bale_service.pay_chat_link(bale_credentials_service.bot_username(), f"selftest-{secrets.token_hex(4)}")
            if link is None:
                steps.append(
                    ("createInvoiceLink (۱۰٬۰۰۰ ریال)", False, f"شناسه آمد ولی ربات نامِ کاربری ندارد: «{invoice_result[:40]}»")
                )
            else:
                steps.append(("createInvoiceLink (۱۰٬۰۰۰ ریال)", True, f"{invoice_result[:40]} | لینکِ پرداخت: {link[:72]}"))
        except bale_service.BaleError as exc:
            steps.append(("createInvoiceLink (۱۰٬۰۰۰ ریال)", False, str(exc)[:200]))
    await callback.message.answer(texts.bale_selftest_report(steps))


@super_router.callback_query(F.data.startswith("admin_prompt_default:"))
async def cb_prompt_default(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    mode = callback.data.split(":", 1)[1]
    if mode not in ("sales", "consultation"):
        await callback.answer(texts.PROFILE_STALE, show_alert=True)
        return
    await callback.answer()
    await state.clear()
    await admin_settings_service.update_setting(session, f"global_ai_prompt_{mode}", prompt_defaults.default_prompt_for(mode))
    await callback.message.answer(texts.ADMIN_PROMPT_DEFAULT_LOADED)
    await _refresh_settings_menu(callback.message, session, "ai")


@super_router.callback_query(F.data.startswith("admin_setting_edit:"))
async def cb_setting_edit(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await callback.answer()

    if field == "rate_limit":
        await state.set_state(AdminSettingsStates.waiting_rate_limit_max)
        await callback.message.answer(texts.ADMIN_ASK_RATE_LIMIT_MAX_MESSAGES)
        return

    support_asks = {
        "platform_support_username": ("support_username", texts.ADMIN_ASK_SUPPORT_USERNAME),
        "platform_support_phone": ("support_phone", texts.ADMIN_ASK_SUPPORT_PHONE),
        "platform_support_text": ("nullable_text", texts.ADMIN_ASK_SUPPORT_TEXT),
    }
    if field in support_asks:
        kind, ask = support_asks[field]
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind=kind)
        await callback.message.answer(ask)
        return

    if field in _NULLABLE_TEXT_FIELDS:
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind="nullable_text")
        prompt_mode = {"global_ai_prompt_sales": "sales", "global_ai_prompt_consultation": "consultation"}.get(field)
        markup = keyboards.admin_prompt_default_keyboard(prompt_mode) if prompt_mode else None
        await callback.message.answer(_NULLABLE_TEXT_FIELDS[field], reply_markup=markup)
        return

    if field in _TEXT_FIELDS:
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind="text")
        await callback.message.answer(_TEXT_FIELDS[field])
        return

    if field in _INT_FIELDS:
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind="int")
        await callback.message.answer(_INT_FIELDS[field])
        return

    if field in _DECIMAL_FIELDS:
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind="decimal")
        await callback.message.answer(_DECIMAL_FIELDS[field])
        return

    # A5/A6: دکمه‌یِ کهنه از نسخه‌یِ قبلیِ منو (یا فیلدی که از پنلِ ادمین برداشته شده) ⇒ بی‌اثر نماند.
    await callback.message.answer(texts.ADMIN_SETTING_REMOVED)


@super_router.message(AdminSettingsStates.waiting_value, F.text)
async def setting_value_entered(
    message: Message, state: FSMContext, session: AsyncSession, bot_manager, bot: Bot
) -> None:
    data = await state.get_data()
    field = data["field"]
    raw = message.text.strip()

    if data["field_kind"] == "int":
        try:
            value = int(raw)
            minimum = _INT_FIELDS_MIN.get(field, 0 if field in _INT_FIELDS_ALLOW_ZERO else 1)
            maximum = _INT_FIELDS_MAX.get(field)
            if value < minimum or (maximum is not None and value > maximum):
                raise ValueError
        except ValueError:
            await message.answer(texts.ADMIN_INVALID_NUMBER)
            return
    elif data["field_kind"] == "decimal":
        try:
            value = Decimal(raw.replace(",", "."))
            # کمیسیون تنها فیلدِ اعشاری است که صفرِ معتبر دارد (۰٪ = برداشتنِ کاملِ کمیسیون).
            if value < 0 or (value == 0 and field not in _DECIMAL_FIELDS_ALLOW_ZERO):
                raise ValueError
            maximum = _DECIMAL_FIELDS_MAX.get(field)
            if maximum is not None and value > maximum:
                raise ValueError
        except (ValueError, InvalidOperation):
            await message.answer(texts.ADMIN_INVALID_NUMBER)
            return
    elif data["field_kind"] in ("support_username", "support_phone"):
        if raw in texts.SUPPORT_CLEAR_WORDS:
            value = None
        elif data["field_kind"] == "support_username":
            value = normalize_telegram_username(raw)
            if value is None:
                await message.answer(texts.INVALID_SUPPORT_USERNAME)
                return
        else:
            value = to_e164_iran(raw)
            if value is None:
                await message.answer(texts.INVALID_SUPPORT_PHONE)
                return
    elif data["field_kind"] == "nullable_text":
        value = None if raw in ("خالی", "پاک کن", "-") else raw
    else:
        value = raw

    if field in _URL_FIELDS and value is not None:
        error = _url_value_error(str(value))
        if error is not None:
            await message.answer(error)
            return  # state همان «منتظرِ مقدار» می‌ماند و دوباره می‌پرسد

    if field == "branding_text":
        # A2: متنِ ادمین حداکثر ۶۰ نویسه؛ اگر عوض شد، بیویِ همه‌یِ ربات‌ها در پس‌زمینه همگام می‌شود.
        cleaned = bot_branding_service.normalize_admin_text(None if value is None else str(value))
        if value is not None and cleaned is None:
            await message.answer(texts.ADMIN_INVALID_BRANDING_TEXT)
            return
        if cleaned is not None and not bot_branding_service.valid_admin_text(str(value)):
            await message.answer(texts.ADMIN_INVALID_BRANDING_TEXT)
            return
        previous = (await admin_settings_service.get_admin_settings(session)).branding_text
        await admin_settings_service.update_setting(session, field, cleaned)
        await audit_log_service.log(
            session,
            AuditEventType.BRANDING_TEXT_CHANGED,
            actor_telegram_id=message.from_user.id,
            details="تنظیم شد" if cleaned is None else f"قدیمی: {(previous or '—')[:60]} → جدید: {cleaned[:60]}",
        )
        await state.clear()
        counts = await bot_branding_service.sync_all(session, bot_manager, bot, force=True)
        if counts["total"]:
            await message.answer(
                fa_text(texts.BRANDING_SAVED_WITH_BOTS, count=counts["shops"])
                + "\n"
                + fa_text(texts.BRANDING_SYNC_RESULT, **counts)
            )
            if counts["error"]:
                await message.answer(fa_text(texts.BRANDING_SYNC_FAILED, error=counts["error"]))
        else:
            await message.answer(texts.BRANDING_SAVED_NO_BOTS)
        await _refresh_settings_menu(message, session, _setting_group(field))
        return

    if field in _SMS_FORMAT_FIELDS and value is not None:
        error = _sms_value_error(field, value)
        if error is not None:
            await message.answer(error)  # state همان «منتظرِ مقدار» می‌ماند و دوباره می‌پرسد
            return
        value = _SMS_FORMAT_FIELDS[field](value)

    if field in _BALE_TOKEN_FIELDS:
        if value is not None and not bale_credentials_service.valid_token_input(value):
            await message.answer(texts.ADMIN_INVALID_BALE_TOKEN)
            return
        await admin_settings_service.update_setting(session, field, value)
        # A1: تغییرِ توکن بدونِ ری‌استارت اعمال شود.
        await bale_credentials_service.refresh(session)
        await state.clear()
        await message.answer(texts.ADMIN_SETTING_SAVED)
        await _refresh_settings_menu(message, session, _setting_group(field))
        return

    await admin_settings_service.update_setting(session, field, value)
    await state.clear()
    await message.answer(texts.ADMIN_SETTING_SAVED)
    await _refresh_settings_menu(message, session, _setting_group(field))


@super_router.message(AdminSettingsStates.waiting_rate_limit_max, F.text)
async def rate_limit_max_entered(message: Message, state: FSMContext) -> None:
    try:
        max_messages = int(message.text.strip())
        if max_messages <= 0:
            raise ValueError
    except ValueError:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    await state.update_data(rate_limit_max=max_messages)
    await state.set_state(AdminSettingsStates.waiting_rate_limit_window)
    await message.answer(texts.ADMIN_ASK_RATE_LIMIT_WINDOW_SECONDS)


@super_router.message(AdminSettingsStates.waiting_rate_limit_window, F.text)
async def rate_limit_window_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        window_seconds = int(message.text.strip())
        if window_seconds <= 0:
            raise ValueError
    except ValueError:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    data = await state.get_data()
    admin_settings = await admin_settings_service.get_admin_settings(session)
    admin_settings.rate_limit_max_messages = data["rate_limit_max"]
    admin_settings.rate_limit_window_seconds = window_seconds
    await session.flush()

    await state.clear()
    await message.answer(texts.ADMIN_SETTING_SAVED)
    await _refresh_settings_menu(message, session, _setting_group("rate_limit"))


# =============================================================================
# مدیریت فروشگاه‌دارها
# =============================================================================
async def _owners_list_payload(session: AsyncSession, owners, page: int):
    """متن (با شمارِ کل و صفحه) + کیبوردِ فهرستِ فروشگاه‌دارها؛ هر دکمه «وضعیت + نام + @ربات» نشون می‌ده."""
    shop_bots = await shop_bot_service.get_map_by_owner_ids(session, [owner.id for owner in owners])
    keyboard = keyboards.admin_owners_list_keyboard(owners, page, shop_bots)
    total_pages = max(1, (len(owners) + keyboards.PAGE_SIZE - 1) // keyboards.PAGE_SIZE)
    shown_page = min(max(0, page), total_pages - 1)
    return texts.admin_shop_owners_intro(len(owners), shown_page, total_pages), keyboard


async def _visible_owners(session: AsyncSession, actor_telegram_id: int, owners):
    """P21-E (F8): ادمینِ عملیاتیِ دامنه‌دار فقط فروشگاه‌هایِ خودش را می‌بیند (و می‌تواند باز کند).

    فیلتر *قبل* از صفحه‌بندی انجام می‌شود، وگرنه شمارِ «N فروشگاه» و شمارهٔ صفحه‌ها
    به ردیف‌هایی اشاره می‌کردند که آن ادمین اجازه ندارد — یعنی نشتِ اطلاعات از راهِ عدد.
    """
    scope = await admin_role_service.scope_for(session, actor_telegram_id)
    if scope is None:
        return owners
    return [owner for owner in owners if admin_role_service.is_in_scope(scope, owner.id)]


@router.message(F.text == "👥 مدیریت فروشگاه‌دارها")
async def open_owners_management(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owners = await _visible_owners(session, message.from_user.id, await shop_owner_service.get_all_registered(session))
    if not owners:
        await message.answer(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    text, keyboard = await _owners_list_payload(session, owners, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("admin_owners_list"))
async def cb_owners_list(callback: CallbackQuery, session: AsyncSession) -> None:
    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":", 1)[1])
        except ValueError:
            page = 0

    owners = await _visible_owners(session, callback.from_user.id, await shop_owner_service.get_all_registered(session))
    await callback.answer()
    if not owners:
        await callback.message.edit_text(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    text, keyboard = await _owners_list_payload(session, owners, page)
    await callback.message.edit_text(text, reply_markup=keyboard)


def _cb_id(data: str) -> int | None:
    """شناسهٔ عددیِ داخلِ callback_data. رشتهٔ غیرِ عددی ⇒ None، نه استثنا (پیام‌هایِ قدیمی یا
    بازنشرشده می‌توانند هر چیزی در payload داشته باشند)."""
    part = data.split(":", 1)[1] if ":" in data else ""
    return int(part) if part.isascii() and part.isdecimal() else None


async def _scoped_owner(session: AsyncSession, actor_telegram_id: int, owner_id: int):
    """P21-E (F8): دامنهٔ ادمینِ عملیاتی. خروجی (owner, allowed) — اگر allowed نبود، پیام داده شده.

    عمداً پیامِ «خارج از دامنه» با «پیدا نشد» یکی نمی‌شود: ادمینِ تیم پشتیبانی باید بفهمد
    ردیف وجود دارد ولی مالِ او نیست (وگرنه ساعت‌ها دنبالِ باگِ «فروشگاه‌دار ثبت‌نام نکرده» می‌گردد).
    """
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        return None, False
    if not await admin_role_service.can_touch_owner(session, actor_telegram_id, owner.id):
        return owner, False
    return owner, True


async def _render_owner_detail(message: Message, session: AsyncSession, owner_id: int, actor_id: int | None = None) -> None:
    owner, allowed = await _scoped_owner(session, actor_id if actor_id is not None else getattr(message.from_user, "id", 0), owner_id)
    if owner is None:
        await message.edit_text(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    if not allowed:
        await message.edit_text(texts.ADMIN_OWNER_OUT_OF_SCOPE)
        return
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await message.edit_text(
        texts.admin_shop_owner_detail(owner, shop_bot, owner.wallet_balance_toman), reply_markup=keyboards.admin_owner_detail_keyboard(owner.id, shop_bot)
    )


@router.callback_query(F.data.startswith("admin_owner_view:"))
async def cb_owner_view(callback: CallbackQuery, session: AsyncSession) -> None:
    owner_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _render_owner_detail(callback.message, session, owner_id, callback.from_user.id)


@router.callback_query(F.data.startswith("admin_owner_suspend:"))
async def cb_owner_suspend(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    owner_id = int(callback.data.split(":")[1])
    owner, allowed = await _scoped_owner(session, callback.from_user.id, owner_id)
    if owner is not None and not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if owner is None or shop_bot is None:
        await callback.answer(texts.ADMIN_OWNER_NO_SHOP_BOT, show_alert=True)
        return

    # نکته: تغییرِ is_active همینجا روی همون session انجام می‌شه (نه داخل bot_manager)
    # تا شیِ shop_bot توی این session فعلی هم بلافاصله وضعیتِ درست رو نشون بده.
    shop_bot.is_active = False
    shop_bot.disabled_reason = "توسط ادمین معلق شد"
    await audit_log_service.log(
        session, AuditEventType.SHOP_SUSPENDED, shop_bot_id=shop_bot.id, actor_telegram_id=callback.from_user.id
    )
    await session.flush()
    await bot_manager.unregister(shop_bot.id, disable_in_db=False)

    await callback.answer()
    await callback.message.answer(texts.admin_owner_suspended_confirmation(_owner_display_name(owner)))
    await _render_owner_detail(callback.message, session, owner_id, callback.from_user.id)


@router.callback_query(F.data.startswith("admin_owner_unsuspend:"))
async def cb_owner_unsuspend(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    owner_id = int(callback.data.split(":")[1])
    owner, allowed = await _scoped_owner(session, callback.from_user.id, owner_id)
    if owner is not None and not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if owner is None or shop_bot is None:
        await callback.answer(texts.ADMIN_OWNER_NO_SHOP_BOT, show_alert=True)
        return

    shop_bot.is_active = True
    shop_bot.disabled_reason = None
    await audit_log_service.log(
        session, AuditEventType.SHOP_UNSUSPENDED, shop_bot_id=shop_bot.id, actor_telegram_id=callback.from_user.id
    )
    await session.flush()
    await bot_manager.register(shop_bot)

    await callback.answer()
    await callback.message.answer(texts.admin_owner_unsuspended_confirmation(_owner_display_name(owner)))
    await _render_owner_detail(callback.message, session, owner_id, callback.from_user.id)


# --- اعطای اشتراک هدیه (این‌جلسه) ---
@router.callback_query(F.data.startswith("admin_owner_gift:"))
async def cb_owner_gift_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner_id = _cb_id(callback.data)
    if owner_id is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    _owner, allowed = await _scoped_owner(session, callback.from_user.id, owner_id)
    if not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return
    await state.set_state(AdminGiftStates.waiting_amount)
    await state.update_data(gift_owner_id=owner_id)
    await callback.answer()
    await callback.message.answer(texts.ADMIN_ASK_GIFT_AMOUNT)


@router.message(AdminGiftStates.waiting_amount, F.text)
async def owner_gift_amount_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        amount_toman = int(message.text.strip())
        if amount_toman <= 0:
            raise ValueError
    except ValueError:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    if not credit_batch_service.GIFT_MIN_TOMAN <= amount_toman <= credit_batch_service.GIFT_MAX_TOMAN:
        # همان سقفِ هدیهٔ گروهی (K1). قبلاً این مسیر تک‌نفره هیچ حدی نداشت ⇒ یک اشتباهِ تایپی
        # می‌توانست اعتبارِ نامحدود بسازد در حالی که نسخهٔ گروهی محدود بود.
        await message.answer(
            fa_text(texts.ADMIN_GIFT_OUT_OF_RANGE, 
                min=format_toman(credit_batch_service.GIFT_MIN_TOMAN), max=format_toman(credit_batch_service.GIFT_MAX_TOMAN)
            )
        )
        return

    data = await state.get_data()
    owner_id = data["gift_owner_id"]
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await state.clear()
        await message.answer(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return

    await state.update_data(gift_amount_toman=amount_toman, gift_nonce=secrets.token_hex(8))
    await state.set_state(AdminGiftStates.waiting_confirmation)
    await message.answer(
        texts.admin_gift_preview(_owner_display_name(owner), amount_toman, credit_batch_service.GIFT_MIN_TOMAN, credit_batch_service.GIFT_MAX_TOMAN),
        reply_markup=keyboards.yes_no_keyboard("admin_gift_confirm", "admin_gift_cancel"),
    )


@router.callback_query(AdminGiftStates.waiting_confirmation, F.data == "admin_gift_cancel")
async def owner_gift_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.ADMIN_GIFT_CANCELLED)


@router.callback_query(AdminGiftStates.waiting_confirmation, F.data == "admin_gift_confirm")
async def owner_gift_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner_id = data.get("gift_owner_id")
    amount_toman = data.get("gift_amount_toman")
    nonce = data.get("gift_nonce")
    # state پیش ازِ نوشتن پاک می‌شود: دابل‌تپِ همین دکمه (یا بازنشرِ همان کال‌بک) دیگر به این
    # nonce نمی‌رسد، و حتی اگر برسد قیدِ یکتای `idempotency_key` در دفتر جلویِ دومین شارژ را می‌گیرد.
    await state.clear()
    if not owner_id or not amount_toman or not nonce:
        await callback.answer(texts.ADMIN_GIFT_STALE, show_alert=True)
        return

    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await callback.answer(texts.ADMIN_SHOP_OWNERS_EMPTY, show_alert=True)
        return
    # P21-F: دامنه در لحظهٔ نوشتنِ پول دوباره سنجیده می‌شود (شروعِ فرم شاید ساعتی قبل بوده باشد).
    if not await admin_role_service.can_touch_owner(session, callback.from_user.id, owner.id):
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return

    await wallet_service.add_charge(
        session, owner, amount_toman, reason=WalletTransactionReason.ADMIN_GRANT, reference=f"gift:{nonce}"
    )
    gift_shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_GIFT_GRANTED,
        shop_bot_id=gift_shop_bot.id if gift_shop_bot else None,
        actor_telegram_id=callback.from_user.id,
        details=f"owner_id={owner_id}, amount_toman={amount_toman}, ref=gift:{nonce}",
    )

    await callback.answer()
    await callback.message.edit_text(
        texts.admin_gift_confirmation(_owner_display_name(owner), amount_toman), reply_markup=NO_INLINE_KEYBOARD
    )

    try:
        await callback.bot.send_message(owner.telegram_id, texts.owner_gift_notification(amount_toman))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ هدیه‌ی کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


# --- استرداد/اصلاحِ تراکنشِ کیف‌پول (فازِ ۲-ب، زیربخشِ ۳) ---
@router.callback_query(F.data.startswith("admin_owner_wallet_correction:"))
async def cb_owner_wallet_correction_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner_id = _cb_id(callback.data)
    if owner_id is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    owner, allowed = await _scoped_owner(session, callback.from_user.id, owner_id)
    if owner is None:
        await callback.answer(texts.ADMIN_SHOP_OWNERS_EMPTY, show_alert=True)
        return
    # P21-F: آخرین مسیری که دامنه را نمی‌سنجید همین بود؛ «دیدنِ دفترِ این فروشگاه» و
    # «کم/زیاد کردنِ پولش» هر دو با یکِ شناسه از callback_data ممکن می‌شد.
    if not allowed:
        await callback.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST, show_alert=True)
        return

    transactions = await wallet_service.get_recent_transactions(session, owner.id)
    await state.set_state(AdminWalletCorrectionStates.waiting_amount)
    await state.update_data(correction_owner_id=owner_id)
    await callback.answer()
    await callback.message.answer(texts.admin_wallet_correction_intro(_owner_display_name(owner), transactions))


@router.message(AdminWalletCorrectionStates.waiting_amount, F.text)
async def owner_wallet_correction_amount_entered(message: Message, state: FSMContext) -> None:
    amount_toman = parse_signed_toman_amount(message.text.strip())
    if amount_toman is None:
        await message.answer(texts.ADMIN_INVALID_SIGNED_AMOUNT)
        return

    await state.update_data(correction_amount=amount_toman, correction_nonce=secrets.token_hex(8))
    await state.set_state(AdminWalletCorrectionStates.waiting_reason)
    await message.answer(texts.ADMIN_ASK_WALLET_CORRECTION_REASON)


@router.message(AdminWalletCorrectionStates.waiting_reason, F.text)
async def owner_wallet_correction_reason_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    note = message.text.strip()
    if not note:
        await message.answer(texts.ADMIN_WALLET_CORRECTION_EMPTY_REASON)
        return
    if len(note) > 255:
        await message.answer(texts.ADMIN_WALLET_CORRECTION_REASON_TOO_LONG)
        return

    data = await state.get_data()
    owner_id = data["correction_owner_id"]
    amount_toman = data["correction_amount"]
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await state.clear()
        await message.answer(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    # P21-F: دامنه در لحظهٔ *نوشتنِ* پول دوباره سنجیده می‌شود، نه فقط در شروعِ مسیر:
    # دامنه ممکن است وسطِ فرم عوض شده باشد و آپدیتِ قدیمی هنوز state را زنده نگه دارد.
    if not await admin_role_service.can_touch_owner(session, message.from_user.id, owner.id):
        await state.clear()
        await message.answer(texts.ADMIN_OWNER_OUT_OF_SCOPE_TOAST)
        return

    # کلیدِ ایدمپوتنسی از nonce همانِ جلسهٔ فرم می‌آید، نه از «یادداشتِ» آزادِ ادمین (تا پیشِ این
    # یادداشت کلید بود ⇒ دو اصلاحِ جدا با دلیلِ یکسانِ همان فروشگاه با نقضِ قیدِ یکتا می‌شکست).
    # دوبار-رسیدنِ همان آپدیت هم همین‌جا می‌شکند: هر دو تلاش همان nonce را می‌خوانند.
    correction_key = f"wallet-correction:{owner_id}:{data.get('correction_nonce') or secrets.token_hex(8)}"
    if amount_toman > 0:
        await wallet_service.add_charge(
            session, owner, amount_toman, reason=WalletTransactionReason.ADMIN_CORRECTION,
            reference=note, idempotency_key=correction_key,
        )
    else:
        applied = await wallet_service.deduct(
            session, owner, abs(amount_toman), reason=WalletTransactionReason.ADMIN_CORRECTION,
            reference=note, idempotency_key=correction_key,
        )
        if not applied:
            await state.set_state(AdminWalletCorrectionStates.waiting_amount)
            await message.answer(texts.ADMIN_WALLET_CORRECTION_INSUFFICIENT_BALANCE)
            return

    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_WALLET_CORRECTED,
        shop_bot_id=shop_bot.id if shop_bot else None,
        actor_telegram_id=message.from_user.id,
        details=f"owner_id={owner_id}, amount_toman={amount_toman}, note={note}",
    )

    await state.clear()
    await message.answer(
        texts.admin_wallet_correction_confirmation(_owner_display_name(owner), amount_toman, owner.wallet_balance_toman)
    )

    try:
        await message.bot.send_message(owner.telegram_id, texts.owner_wallet_correction_notification(amount_toman, note))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ اصلاحِ کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)


@router.message(AdminWalletCorrectionStates.waiting_reason)
async def owner_wallet_correction_reason_wrong_type(message: Message) -> None:
    await message.answer(texts.ADMIN_WALLET_CORRECTION_EMPTY_REASON)


# =============================================================================
# نگهبانِ محتوا (Moderation)
# =============================================================================
@router.message(F.text == "🛡 نگهبانِ محتوا")
async def open_moderation_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    rules = await moderation_service.get_all_rules(session)
    if not rules:
        await message.answer(texts.MODERATION_MENU_INTRO + "\n\n" + texts.MODERATION_RULES_EMPTY, reply_markup=keyboards.moderation_rules_list_keyboard([]))
        return
    await message.answer(texts.MODERATION_MENU_INTRO, reply_markup=keyboards.moderation_rules_list_keyboard(rules))


@router.callback_query(F.data == "mod_rules_list")
async def cb_moderation_rules_list(callback: CallbackQuery, session: AsyncSession) -> None:
    rules = await moderation_service.get_all_rules(session)
    await callback.answer()
    text = texts.MODERATION_MENU_INTRO if rules else texts.MODERATION_MENU_INTRO + "\n\n" + texts.MODERATION_RULES_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.moderation_rules_list_keyboard(rules))


@router.callback_query(F.data == "mod_rule_add")
async def cb_moderation_rule_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(ModerationStates.waiting_pattern)
    await callback.message.answer(texts.ASK_MODERATION_PATTERN)


@router.message(ModerationStates.waiting_pattern, F.text)
async def moderation_pattern_received(message: Message, state: FSMContext) -> None:
    await state.update_data(pattern=message.text.strip())
    await message.answer(texts.ASK_MODERATION_ACTION, reply_markup=keyboards.moderation_rule_action_keyboard())


@router.callback_query(F.data.startswith("mod_rule_action:"))
async def cb_moderation_rule_action(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    pattern = data.get("pattern")
    if not pattern:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    action = callback.data.split(":")[1]
    await moderation_service.create_rule(session, pattern, is_regex=False, action=action)
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.moderation_rule_added_confirmation(pattern, action))

    rules = await moderation_service.get_all_rules(session)
    await callback.message.answer(texts.MODERATION_MENU_INTRO, reply_markup=keyboards.moderation_rules_list_keyboard(rules))


@router.callback_query(F.data.startswith("mod_rule_view:"))
async def cb_moderation_rule_view(callback: CallbackQuery, session: AsyncSession) -> None:
    rule_id = int(callback.data.split(":")[1])
    rule = await moderation_service.get_by_id(session, rule_id)
    if rule is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(texts.moderation_rule_detail_text(rule), reply_markup=keyboards.moderation_rule_detail_keyboard(rule.id, rule.is_active))


@router.callback_query(F.data.startswith("mod_rule_toggle:"))
async def cb_moderation_rule_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    rule_id = int(callback.data.split(":")[1])
    rule = await moderation_service.get_by_id(session, rule_id)
    if rule is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await moderation_service.toggle_active(session, rule)
    await callback.answer(texts.moderation_rule_toggled_confirmation(rule.is_active))
    await callback.message.edit_text(texts.moderation_rule_detail_text(rule), reply_markup=keyboards.moderation_rule_detail_keyboard(rule.id, rule.is_active))


@router.callback_query(F.data.startswith("mod_rule_delete:"))
async def cb_moderation_rule_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    rule_id = int(callback.data.split(":")[1])
    rule = await moderation_service.get_by_id(session, rule_id)
    if rule is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await moderation_service.delete_rule(session, rule)
    await callback.answer(texts.MODERATION_RULE_DELETED)

    rules = await moderation_service.get_all_rules(session)
    text = texts.MODERATION_MENU_INTRO if rules else texts.MODERATION_MENU_INTRO + "\n\n" + texts.MODERATION_RULES_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.moderation_rules_list_keyboard(rules))


# استخرِ کلیدهایِ AI (AI Key Pool)


@super_router.message(F.text == "🔑 استخرِ کلیدهایِ AI")
async def open_ai_pool(message: Message, session: AsyncSession) -> None:
    entries = await ai_pool_service.get_all_entries(session)
    text = (texts.AI_POOL_MENU_INTRO if entries else texts.AI_POOL_MENU_INTRO + "\n\n" + texts.AI_POOL_EMPTY) + texts.ai_pool_health_line(
        ai_service.circuit_health()
    )
    await message.answer(text, reply_markup=keyboards.ai_pool_list_keyboard(entries))


@super_router.callback_query(F.data == "ai_pool_list")
async def cb_ai_pool_list(callback: CallbackQuery, session: AsyncSession) -> None:
    entries = await ai_pool_service.get_all_entries(session)
    await callback.answer()
    text = (texts.AI_POOL_MENU_INTRO if entries else texts.AI_POOL_MENU_INTRO + "\n\n" + texts.AI_POOL_EMPTY) + texts.ai_pool_health_line(
        ai_service.circuit_health()
    )
    await callback.message.edit_text(text, reply_markup=keyboards.ai_pool_list_keyboard(entries))


@super_router.callback_query(F.data == "ai_pool_add")
async def cb_ai_pool_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AiPoolStates.waiting_entry_details)
    await callback.message.answer(texts.ASK_AI_POOL_ENTRY)


@super_router.message(AiPoolStates.waiting_entry_details, F.text)
async def ai_pool_entry_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    lines = [line.strip() for line in message.text.strip().splitlines() if line.strip()]
    if len(lines) not in (5, 6):
        await message.answer(texts.AI_POOL_ENTRY_INVALID_FORMAT)
        return

    label, api_key, model, base_url, capability_raw = lines[:5]
    fallback_raw = lines[5] if len(lines) == 6 else None
    capability = capability_raw.lower()
    if capability not in {item.value for item in AiKeyCapability}:
        await message.answer(texts.AI_POOL_ENTRY_INVALID_CAPABILITY)
        return

    entry = await ai_pool_service.add_entry(session, label, api_key, model, base_url, capability, fallback_raw)
    await state.clear()
    await message.answer(texts.ai_pool_entry_added_confirmation(label))
    await message.answer(
        texts.ai_pool_entry_detail_text(entry), reply_markup=keyboards.ai_pool_entry_detail_keyboard(entry.id, entry.is_active)
    )

    entries = await ai_pool_service.get_all_entries(session)
    await message.answer(texts.AI_POOL_MENU_INTRO, reply_markup=keyboards.ai_pool_list_keyboard(entries))


@super_router.callback_query(F.data.startswith("ai_pool_models:"))
async def cb_ai_pool_models(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    entry_id = int(callback.data.split(":")[1])
    entry = await ai_pool_service.get_by_id(session, entry_id)
    if entry is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await callback.answer()
    await state.set_state(AiPoolStates.waiting_fallback_models)
    await state.update_data(pool_entry_id=entry.id)
    current = (entry.fallback_models or "").strip()
    await callback.message.answer(
        texts.ASK_AI_POOL_FALLBACK_MODELS + "\n\n" + f"مدلِ اصلی: {entry.model}\nپشتیبان‌هایِ فعلی: {current or '—'}"
    )


@super_router.message(AiPoolStates.waiting_fallback_models, F.text)
async def ai_pool_models_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    raw = message.text.strip()
    if raw in ("انصراف", "لغو", "/cancel"):
        await state.clear()
        await message.answer("↩️ لغو شد؛ فهرستِ مدل‌هایِ پشتیبان عوض نشد.")
        return
    entry = await ai_pool_service.get_by_id(session, int(data["pool_entry_id"]))
    if entry is None:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    # «خالی» یعنی بدونِ پشتیبان؛ هر چیزِ دیگر نرمال و تا ۵ مورد بریده می‌شود (سقفِ هزینه/تأخیر).
    saved = await ai_pool_service.set_fallback_models(session, entry, None if raw in ("خالی", "پاک کن", "-") else raw)
    await state.clear()
    await message.answer(texts.AI_POOL_FALLBACK_SAVED)
    await message.answer(
        texts.ai_pool_entry_detail_text(entry) + ("\nترتیبِ امتحان: " + " ← ".join([entry.model, *saved]) if saved else ""),
        reply_markup=keyboards.ai_pool_entry_detail_keyboard(entry.id, entry.is_active),
    )


@super_router.callback_query(F.data.startswith("ai_pool_view:"))
async def cb_ai_pool_view(callback: CallbackQuery, session: AsyncSession) -> None:
    entry_id = int(callback.data.split(":")[1])
    entry = await ai_pool_service.get_by_id(session, entry_id)
    if entry is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(
        texts.ai_pool_entry_detail_text(entry), reply_markup=keyboards.ai_pool_entry_detail_keyboard(entry.id, entry.is_active)
    )


@super_router.callback_query(F.data.startswith("ai_pool_toggle:"))
async def cb_ai_pool_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    entry_id = int(callback.data.split(":")[1])
    entry = await ai_pool_service.get_by_id(session, entry_id)
    if entry is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await ai_pool_service.toggle_active(session, entry)
    await callback.answer(texts.ai_pool_entry_toggled_confirmation(entry.is_active))
    await callback.message.edit_text(
        texts.ai_pool_entry_detail_text(entry), reply_markup=keyboards.ai_pool_entry_detail_keyboard(entry.id, entry.is_active)
    )


@super_router.callback_query(F.data.startswith("ai_pool_delete:"))
async def cb_ai_pool_delete(callback: CallbackQuery, session: AsyncSession) -> None:
    entry_id = int(callback.data.split(":")[1])
    entry = await ai_pool_service.get_by_id(session, entry_id)
    if entry is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await ai_pool_service.delete_entry(session, entry)
    await callback.answer(texts.AI_POOL_ENTRY_DELETED)

    entries = await ai_pool_service.get_all_entries(session)
    text = texts.AI_POOL_MENU_INTRO if entries else texts.AI_POOL_MENU_INTRO + "\n\n" + texts.AI_POOL_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.ai_pool_list_keyboard(entries))


# =============================================================================
# گزارشِ ممیزی (Audit Log)
# =============================================================================
AUDIT_PAGE_LIMIT = 25
AUDIT_CSV_LIMIT = 500


async def _audit_filter_state(state: FSMContext) -> tuple[str | None, str | None]:
    data = await state.get_data()
    return data.get("audit_group"), data.get("audit_window")


async def _render_audit_log(message: Message, state: FSMContext, session: AsyncSession) -> None:
    group, window = await _audit_filter_state(state)
    # P21-F: ادمینِ دامنه‌دار ردیف‌هایِ فروشگاه‌هایِ دیگر را نمی‌بیند (جزئیاتِ آن ردیف‌ها مبلغ و
    # شناسهٔ فروشگاه‌دارِ مشتریِ دیگر را دارد). سوپرادمین scope=None ⇒ همان دفترِ کامل.
    scope = await admin_role_service.scope_for(session, getattr(message.from_user, "id", 0))
    entries = await audit_log_service.query(
        session, group=group, window=window, limit=AUDIT_PAGE_LIMIT, allowed_owner_ids=scope
    )
    markup = keyboards.audit_filter_keyboard(group, window)
    if not entries:
        await message.answer(texts.AUDIT_FILTER_EMPTY if (group or window) else texts.AUDIT_LOG_EMPTY, reply_markup=markup)
        return
    lines = [texts.audit_report_intro(group, window, len(entries), scoped=scope is not None), ""]
    lines.extend(texts.audit_log_entry_line(entry) for entry in entries)
    await message.answer("\n\n".join(lines), reply_markup=markup)


@router.message(F.text == "📜 گزارشِ ممیزی")
async def open_audit_log(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    await _render_audit_log(message, state, session)


@router.callback_query(F.data.startswith("audit_filter:"))
async def cb_audit_filter(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    group = callback.data.split(":", 1)[1]
    if group not in audit_log_service.FILTER_GROUPS and group != "all":
        await callback.answer("این دسته شناخته‌شده نیست.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(audit_group=None if group == "all" else group)
    await _render_audit_log(callback.message, state, session)


@router.callback_query(F.data.startswith("audit_window:"))
async def cb_audit_window(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    window = callback.data.split(":", 1)[1]
    if window not in audit_log_service.WINDOW_HOURS and window != "all":
        await callback.answer("این بازه شناخته‌شده نیست.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(audit_window=None if window == "all" else window)
    await _render_audit_log(callback.message, state, session)


@super_router.callback_query(F.data == "audit_csv")
async def cb_audit_csv(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """F9: خروجیِ CSVِ همان فیلتر. فقط سوپرادمین، و خودِ «گرفتنِ خروجی» هم ممیزی می‌شود."""
    group, window = await _audit_filter_state(state)
    entries = await audit_log_service.query(session, group=group, window=window, limit=AUDIT_CSV_LIMIT)
    if not entries:
        await callback.answer(texts.AUDIT_CSV_EMPTY, show_alert=True)
        return
    shop_labels = {
        bot.id: "@" + (bot.bot_username or "").lstrip("@")
        for bot in await shop_bot_service.list_by_ids(session, sorted({entry.shop_bot_id for entry in entries if entry.shop_bot_id}))
    }
    rows = [
        [
            entry.id,
            format_jalali_datetime(entry.created_at) if entry.created_at else "",
            texts.audit_event_label(entry.event_type),
            entry.actor_telegram_id or "",
            shop_labels.get(entry.shop_bot_id, "") if entry.shop_bot_id else "",
            entry.shop_bot_id or "",
            entry.details or "",
            entry.row_hash or "",
        ]
        for entry in entries
    ]
    content = csv_export.build_csv(texts.audit_csv_headers(), rows)
    await audit_log_service.log(
        session,
        AuditEventType.AUDIT_EXPORTED,
        actor_telegram_id=callback.from_user.id,
        details=f"خروجیِ CSV ({len(rows)} ردیف) · دسته={group or 'all'} · بازه={window or 'all'}",
    )
    await callback.answer()
    await callback.message.answer_document(
        BufferedInputFile(content, filename="audit-log.csv"),
        caption=fa_text(texts.AUDIT_CSV_READY, count=len(rows)),
    )


# =============================================================================
# دفترِ کیف‌پول (اکسل) — فقط سوپرادمین، فقط‌خواندنی (فازِ ۴-ه)
# PHASE 5E: سقفِ تعدادِ اختلافِ نمایش‌داده‌شده در پنل (کوئری هم با همان سقف محدود می‌ماند).
RECONCILE_LIMIT = 100
# =============================================================================
@super_router.message(F.text == "📤 دفترِ کیف‌پول (اکسل)")
async def export_wallet_ledger(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    content = await excel_export_service.build_wallet_ledger_workbook(session)
    await audit_log_service.log(
        session,
        AuditEventType.WALLET_LEDGER_EXPORTED,
        actor_telegram_id=message.from_user.id,
        details="خروجیِ اکسلِ دفترِ کیف‌پول",
    )
    await message.answer_document(
        BufferedInputFile(content, filename="wallet-ledger.xlsx"),
        caption=texts.ADMIN_WALLET_LEDGER_READY,
        reply_markup=keyboards.wallet_ledger_keyboard(),
    )


@super_router.callback_query(F.data == "admin_reconcile_wallets")
async def cb_admin_reconcile_wallets(callback: CallbackQuery, session: AsyncSession) -> None:
    """PHASE 5E: نگاهِ ادمین به همسنجیِ دفتر (فقط‌خواندنی و ممیزی‌شده؛ هیچ داده‌ای عوض نمی‌شود)."""
    gaps = await wallet_service.reconcile_balances(session, limit=RECONCILE_LIMIT)
    await callback.answer()
    await audit_log_service.log(
        session,
        AuditEventType.WALLET_RECONCILED,
        actor_telegram_id=callback.from_user.id,
        details="اختلافی نیست" if not gaps else f"{len(gaps)} اختلاف؛ نمونهٔ shop_owner_id={gaps[0]['owner_id']}",
    )
    await callback.message.answer(texts.ADMIN_RECONCILE_CLEAN if not gaps else texts.admin_reconcile_gaps(gaps, RECONCILE_LIMIT))


# =============================================================================
# مدیریتِ ادمین‌ها (RBAC) — فقط سوپرادمین
# =============================================================================
def _admin_roles_menu_text(roles: list) -> str:
    if roles:
        return texts.ADMIN_ROLES_MENU_INTRO
    return texts.ADMIN_ROLES_MENU_INTRO + "\n\n" + texts.ADMIN_ROLES_EMPTY


@super_router.message(F.text == "👑 مدیریتِ ادمین‌ها")
async def open_admin_roles(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    roles = await admin_role_service.get_all(session)
    await message.answer(_admin_roles_menu_text(roles), reply_markup=await _roles_keyboard(session, roles))


@super_router.callback_query(F.data == "admin_role_list")
async def cb_admin_role_list(callback: CallbackQuery, session: AsyncSession) -> None:
    roles = await admin_role_service.get_all(session)
    await callback.answer()
    await callback.message.edit_text(_admin_roles_menu_text(roles), reply_markup=await _roles_keyboard(session, roles))


@super_router.callback_query(F.data == "admin_role_add")
async def cb_admin_role_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AdminRoleStates.waiting_telegram_id)
    await callback.message.answer(texts.ASK_ADMIN_ROLE_TELEGRAM_ID)


@super_router.message(AdminRoleStates.waiting_telegram_id, F.text)
async def admin_role_telegram_id_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    raw = message.text.strip()
    try:
        telegram_id = int(raw)
    except ValueError:
        await message.answer(texts.ADMIN_ROLE_INVALID_TELEGRAM_ID)
        return

    if telegram_id in settings.admin_ids:
        await message.answer(texts.ADMIN_ROLE_ALREADY_SUPER_ADMIN)
        return

    existing = await admin_role_service.get_by_telegram_id(session, telegram_id)
    if existing is not None:
        await message.answer(texts.ADMIN_ROLE_ALREADY_OPERATOR)
        return

    await admin_role_service.grant_operator(session, telegram_id, message.from_user.id)
    await audit_log_service.log(
        session,
        AuditEventType.OPERATOR_ADMIN_GRANTED,
        actor_telegram_id=message.from_user.id,
        details=f"telegram_id={telegram_id}",
    )
    await state.clear()
    added = (await _identity_labels(session, [telegram_id]))[telegram_id]
    await message.answer(texts.admin_role_added_confirmation(added))

    roles = await admin_role_service.get_all(session)
    await message.answer(_admin_roles_menu_text(roles), reply_markup=await _roles_keyboard(session, roles))


@super_router.callback_query(F.data.startswith("admin_role_view:"))
async def cb_admin_role_view(callback: CallbackQuery, session: AsyncSession) -> None:
    role_id = int(callback.data.split(":")[1])
    role = await admin_role_service.get_by_id(session, role_id)
    if role is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await callback.answer()
    names = await _identity_labels(session, [role.telegram_id, role.granted_by_telegram_id])
    await callback.message.edit_text(
        texts.admin_role_detail_text(role, names[role.telegram_id], names[role.granted_by_telegram_id]),
        reply_markup=keyboards.admin_role_detail_keyboard(role.id),
    )


@super_router.callback_query(F.data.startswith("admin_role_scope:"))
async def cb_admin_role_scope(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """P21-E (F8): دامنهٔ فروشگاه‌دارهایِ یکِ ادمینِ عملیاتی."""
    role_id = _cb_id(callback.data)
    if role_id is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    role = await admin_role_service.get_by_id(session, role_id)
    if role is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminRoleStates.waiting_scope)
    await state.update_data(scope_role_id=role.id)
    await callback.answer()
    await callback.message.answer(texts.ASK_ROLE_SCOPE)


@super_router.message(AdminRoleStates.waiting_scope, F.text)
async def admin_role_scope_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    role = await admin_role_service.get_by_id(session, int(data.get("scope_role_id", 0)))
    if role is None:
        await state.clear()
        await message.answer(texts.GENERIC_ERROR)
        return
    raw = message.text.strip()
    if raw in {"همه", "all", "خالی", "-"}:
        await admin_role_service.set_scope(session, role, None)
        await audit_log_service.log(
            session, AuditEventType.OPERATOR_ADMIN_GRANTED, actor_telegram_id=message.from_user.id,
            details=f"دامنهٔ ادمینِ عملیاتی {role.telegram_id} ⇒ همهٔ فروشگاه‌ها",
        )
        await state.clear()
        await message.answer(fa_text(texts.ROLE_SCOPE_SAVED, detail=texts.ROLE_SCOPE_UNLIMITED_LABEL))
        return
    if raw in {"هیچ", "هیچکس", "none"}:
        # P21-F: «بستنِ کاملِ دسترسی» باید راهِ صریح داشته باشد، وگرنه دامنهٔ تهی با
        # «بدونِ دامنه» یکی به نظر می‌رسید و نتیجهٔ عملِ ادمین برعکسِ قصدش می‌شد.
        await admin_role_service.set_scope(session, role, [])
        await audit_log_service.log(
            session, AuditEventType.OPERATOR_ADMIN_GRANTED, actor_telegram_id=message.from_user.id,
            details=f"دامنهٔ ادمینِ عملیاتی {role.telegram_id} ⇒ هیچِ فروشگاه",
        )
        await state.clear()
        await message.answer(fa_text(texts.ROLE_SCOPE_SAVED, detail=texts.ROLE_SCOPE_EMPTY_LABEL))
        return

    wanted = {int(part) for part in re.split(r"[,\s]+", raw) if part.strip().lstrip("+").isdigit()}
    if not wanted:
        await message.answer(texts.ADMIN_INVALID_NUMBER)  # state می‌ماند تا دوباره بنویسد
        return
    known_ids = await shop_owner_service.ids_by_telegram_ids(session, list(wanted))
    if not known_ids:
        # P21-F: دامنهٔ تهی ذخیره نمی‌شود. یک فهرستِ اشتباه/تایپی نباید به «دسترسیِ کامل»
        # یا «دسترسیِ صفر» تعبیر شود؛ از ادمین می‌خواهید دوباره بنویسد.
        await message.answer(texts.ROLE_SCOPE_NO_MATCH)
        return
    await admin_role_service.set_scope(session, role, sorted(known_ids.values()))
    unknown = sorted(wanted - set(known_ids))
    await audit_log_service.log(
        session, AuditEventType.OPERATOR_ADMIN_GRANTED, actor_telegram_id=message.from_user.id,
        details=f"دامنهٔ ادمینِ عملیاتی {role.telegram_id} ⇒ {len(known_ids)} فروشگاه",
    )
    await state.clear()
    await message.answer(
        fa_text(texts.ROLE_SCOPE_SAVED, detail=fa_text(texts.ROLE_SCOPE_COUNT_LABEL, count=len(known_ids)))
        + (fa_text(texts.ROLE_SCOPE_UNKNOWN_IDS, ids="، ".join(str(pk) for pk in unknown)) if unknown else "")
    )


@super_router.callback_query(F.data.startswith("admin_role_revoke:"))
async def cb_admin_role_revoke(callback: CallbackQuery, session: AsyncSession) -> None:
    role_id = int(callback.data.split(":")[1])
    role = await admin_role_service.get_by_id(session, role_id)
    if role is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    revoked_telegram_id = role.telegram_id
    await admin_role_service.revoke(session, role)
    await audit_log_service.log(
        session,
        AuditEventType.OPERATOR_ADMIN_REVOKED,
        actor_telegram_id=callback.from_user.id,
        details=f"telegram_id={revoked_telegram_id}",
    )
    await callback.answer(texts.ADMIN_ROLE_REVOKED)

    roles = await admin_role_service.get_all(session)
    await callback.message.edit_text(_admin_roles_menu_text(roles), reply_markup=await _roles_keyboard(session, roles))
