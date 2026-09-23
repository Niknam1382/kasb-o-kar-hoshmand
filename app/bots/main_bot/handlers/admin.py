from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.filters import IsAdmin, IsSuperAdmin
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
    audit_log_service,
    channel_service,
    discount_service,
    moderation_service,
    payment_service,
    shop_bot_service,
    shop_owner_service,
    stats_service,
    subscription_plan_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import parse_signed_toman_amount

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
    if stripped.lstrip("-").isdigit():
        return int(stripped)
    return stripped


def _owner_display_name(owner) -> str:
    return f"{owner.first_name or ''} {owner.last_name or ''}".strip() or str(owner.telegram_id)


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
    payment_id = int(callback.data.split(":")[1])
    payment = await payment_service.get_by_id(session, payment_id)
    if payment is None or payment.status != PaymentStatus.PENDING:
        await callback.answer("این پرداخت قبلاً بررسی شده.", show_alert=True)
        return

    owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
    is_topup = payment.purpose == PaymentPurpose.WALLET_TOPUP
    _effect, reward_info = await payment_service.approve_payment(session, payment, callback.from_user.id)

    await callback.answer()
    new_caption = (callback.message.caption or "") + f"\n\n{texts.admin_payment_approved_confirmation(_owner_display_name(owner))}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)

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
    payment_id = int(callback.data.split(":")[1])
    payment = await payment_service.get_by_id(session, payment_id)
    if payment is None or payment.status != PaymentStatus.PENDING:
        await callback.answer("این پرداخت قبلاً بررسی شده.", show_alert=True)
        return

    owner = await shop_owner_service.get_by_id(session, payment.shop_owner_id)
    await payment_service.reject_payment(session, payment, callback.from_user.id)

    await callback.answer()
    new_caption = (callback.message.caption or "") + f"\n\n{texts.admin_payment_rejected_confirmation(_owner_display_name(owner))}"
    await callback.message.edit_caption(caption=new_caption, reply_markup=None)

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


@router.callback_query(BroadcastStates.waiting_confirmation, F.data == "broadcast_confirm")
async def broadcast_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owners = await shop_owner_service.get_all_registered(session)

    sent = 0
    for owner in owners:
        try:
            await callback.bot.send_message(owner.telegram_id, data["broadcast_text"])
            sent += 1
        except TelegramAPIError:
            logger.info("ارسالِ پیام همگانی به %s ناموفق بود.", owner.telegram_id)

    await state.clear()
    await callback.answer()
    await callback.message.edit_text(texts.broadcast_sent_confirmation(sent))


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


# --- طرح‌های اشتراک ---
async def _render_plans_list(message: Message, session: AsyncSession) -> None:
    plans = await subscription_plan_service.get_all_plans(session)
    await message.edit_text(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_plans_list_keyboard(plans))


@super_router.callback_query(F.data == "admin_pricing_plans")
async def cb_pricing_plans(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    await _render_plans_list(callback.message, session)


@super_router.callback_query(F.data == "admin_toggle_zarinpal")
async def cb_toggle_zarinpal(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    admin_settings.zarinpal_enabled = not admin_settings.zarinpal_enabled
    await session.flush()
    await callback.answer("زرین‌پال " + ("فعال شد ✅" if admin_settings.zarinpal_enabled else "پنهان شد 🙈"))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data == "admin_toggle_bale_pay")
async def cb_toggle_bale_pay(callback: CallbackQuery, session: AsyncSession) -> None:
    admin_settings = await get_admin_settings(session)
    if not admin_settings.bale_pay_enabled and not admin_settings.bale_provider_token:
        await callback.answer("اول باید provider_tokenِ بله‌پی رو از «تنظیمات کلیدها» ثبت کنی.", show_alert=True)
        return
    admin_settings.bale_pay_enabled = not admin_settings.bale_pay_enabled
    await session.flush()
    await callback.answer("بله‌پی " + ("فعال شد ✅" if admin_settings.bale_pay_enabled else "پنهان شد 🙈"))
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
    await callback.answer("ثبت‌نامِ کاربرانِ جدید " + ("باز شد ✅" if admin_settings.allow_new_registrations else "بسته شد ⛔️"))
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
    await callback.answer("شارژِ کیف‌پول " + ("فعال شد ✅" if admin_settings.allow_wallet_topups else "غیرفعال شد ⛔️"))
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
    await callback.answer("حالتِ تعمیر " + ("فعال شد 🚧 — همه‌ی ربات‌ها موقتاً پاسخ نمی‌دن" if admin_settings.maintenance_mode else "غیرفعال شد ✅"))
    await callback.message.edit_reply_markup(reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data.startswith("admin_plan_toggle:"))
async def cb_plan_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    plan_id = int(callback.data.split(":")[1])
    await subscription_plan_service.toggle_plan_active(session, plan_id)
    await callback.answer()
    await _render_plans_list(callback.message, session)


@super_router.callback_query(F.data == "admin_plan_add")
async def cb_plan_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminPricingStates.waiting_plan_duration)
    await callback.answer()
    await callback.message.answer(texts.ADMIN_ASK_PLAN_DURATION)


@super_router.message(AdminPricingStates.waiting_plan_duration, F.text)
async def plan_duration_entered(message: Message, state: FSMContext) -> None:
    try:
        months = int(message.text.strip())
        if months <= 0:
            raise ValueError
    except ValueError:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    await state.update_data(plan_duration=months)
    await state.set_state(AdminPricingStates.waiting_plan_price)
    await message.answer(texts.ADMIN_ASK_PLAN_PRICE)


@super_router.message(AdminPricingStates.waiting_plan_price, F.text)
async def plan_price_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    try:
        price = int(message.text.strip().replace(",", "").replace("،", ""))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    data = await state.get_data()
    months = data["plan_duration"]
    existing = await subscription_plan_service.get_by_duration(session, months)
    if existing is not None:
        await subscription_plan_service.update_price(session, existing, price)
    else:
        await subscription_plan_service.create_plan(session, months, price)

    await state.clear()
    await message.answer(texts.admin_plan_saved(months, price))
    plans = await subscription_plan_service.get_all_plans(session)
    await message.answer(texts.ADMIN_PRICING_MENU_INTRO, reply_markup=keyboards.admin_plans_list_keyboard(plans))


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
    await discount_service.toggle_code_active(session, code_id)
    await callback.answer()
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
    await state.set_state(AdminPricingStates.waiting_discount_type)
    await message.answer(texts.ADMIN_ASK_DISCOUNT_TYPE, reply_markup=keyboards.discount_type_keyboard())


@super_router.callback_query(AdminPricingStates.waiting_discount_type, F.data.startswith("discount_type:"))
async def discount_type_chosen(callback: CallbackQuery, state: FSMContext) -> None:
    discount_type = callback.data.split(":")[1]
    await state.update_data(discount_type=discount_type)
    await state.set_state(AdminPricingStates.waiting_discount_value)
    await callback.answer()
    await callback.message.answer(texts.ADMIN_ASK_DISCOUNT_VALUE)


@super_router.message(AdminPricingStates.waiting_discount_value, F.text)
async def discount_value_entered(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    try:
        value = Decimal(message.text.strip().replace(",", "").replace("،", ""))
    except InvalidOperation:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
        return

    if data["discount_type"] == "percent" and not (0 < value <= 100):
        await message.answer(texts.ADMIN_INVALID_PERCENT)
        return
    if value <= 0:
        await message.answer(texts.ADMIN_INVALID_NUMBER)
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
    discount_type = DiscountType.PERCENT if data["discount_type"] == "percent" else DiscountType.FIXED
    code = await discount_service.create_code(session, data["discount_code"], discount_type, Decimal(data["discount_value"]), max_uses, None)

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
    "bale_provider_token": texts.ADMIN_ASK_BALE_PROVIDER_TOKEN,
    "platform_card_number": texts.ADMIN_ASK_PLATFORM_CARD_NUMBER,
    "platform_card_holder_name": texts.ADMIN_ASK_PLATFORM_CARD_HOLDER,
}

_INT_FIELDS: dict[str, str] = {
    "grace_period_hours": texts.ADMIN_ASK_GRACE_PERIOD_HOURS,
    "payment_reservation_minutes": texts.ADMIN_ASK_PAYMENT_RESERVATION_MINUTES,
    "order_reservation_minutes": texts.ADMIN_ASK_ORDER_RESERVATION_MINUTES,
    "periodic_report_frequency_days": texts.ADMIN_ASK_REPORT_FREQUENCY_DAYS,
    "conversation_history_limit": texts.ADMIN_ASK_CONVERSATION_HISTORY_LIMIT,
    "knowledge_items_limit": texts.ADMIN_ASK_KNOWLEDGE_ITEMS_LIMIT,
    "referral_reward_value": texts.ADMIN_ASK_REFERRAL_PERCENT,
    "wallet_cost_per_1k_tokens_toman": texts.ADMIN_ASK_WALLET_COST_PER_1K_TOKENS,
    "wallet_cost_photo_analysis_toman": texts.ADMIN_ASK_WALLET_COST_PHOTO_ANALYSIS,
    "wallet_cost_voice_transcription_toman": texts.ADMIN_ASK_WALLET_COST_VOICE_TRANSCRIPTION,
    "wallet_cost_order_detection_toman": texts.ADMIN_ASK_WALLET_COST_ORDER_DETECTION,
    "wallet_topup_validity_months": texts.ADMIN_ASK_WALLET_TOPUP_VALIDITY_MONTHS,
    "wallet_trial_credit_toman": texts.ADMIN_ASK_WALLET_TRIAL_CREDIT,
    "wallet_low_balance_warning_toman": texts.ADMIN_ASK_WALLET_LOW_BALANCE_WARNING,
    "conversation_retention_days": texts.ADMIN_ASK_CONVERSATION_RETENTION_DAYS,
    "usd_to_toman_rate": texts.ADMIN_ASK_USD_TO_TOMAN_RATE,
}

# فیلدهای اعشاری (Decimal) — برای مقادیری مثل هزینه‌ی دلاری یا ضریب که به
# دقتِ زیرِ ۱ واحد نیاز دارن؛ _INT_FIELDS برای این‌ها کافی نیست.
_DECIMAL_FIELDS: dict[str, str] = {
    "ai_cost_usd_per_1m_tokens": texts.ADMIN_ASK_AI_COST_USD,
    "wallet_markup_multiplier": texts.ADMIN_ASK_MARKUP_MULTIPLIER,
}

# این فیلدها استثنائاً اجازه‌ی صفر دارن (صفر یعنی «غیرفعال»)؛ بقیه‌ی فیلدهای
# عددیِ بالا باید مثبت باشن.
_INT_FIELDS_ALLOW_ZERO: frozenset[str] = frozenset({"conversation_retention_days", "referral_reward_value"})

# فیلدهای متنیِ قابل‌خالی‌کردن: اگه کاربر «خالی» بفرسته، به‌جای اینکه رشته‌ی
# «خالی» ذخیره بشه، مقدار None ذخیره می‌شه (یعنی واقعاً پاک می‌شه).
_NULLABLE_TEXT_FIELDS: dict[str, str] = {
    "global_ai_system_prompt": texts.ADMIN_ASK_GLOBAL_SYSTEM_PROMPT,
    "reference_channel_link": texts.ADMIN_ASK_REFERENCE_CHANNEL_LINK,
    "ai_fallback_api_key": texts.ADMIN_ASK_AI_FALLBACK_API_KEY,
    "ai_fallback_model": texts.ADMIN_ASK_AI_FALLBACK_MODEL,
    "ai_fallback_base_url": texts.ADMIN_ASK_AI_FALLBACK_BASE_URL,
}


@super_router.message(F.text == "🔑 تنظیمات کلیدها")
async def open_settings_menu(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    admin_settings = await admin_settings_service.get_admin_settings(session)
    await message.answer(texts.ADMIN_SETTINGS_MENU_INTRO, reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


async def _refresh_settings_menu(message: Message, session: AsyncSession) -> None:
    admin_settings = await admin_settings_service.get_admin_settings(session)
    await message.answer(texts.ADMIN_SETTINGS_MENU_INTRO, reply_markup=keyboards.admin_settings_menu_keyboard(admin_settings))


@super_router.callback_query(F.data.startswith("admin_setting_edit:"))
async def cb_setting_edit(callback: CallbackQuery, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    await callback.answer()

    if field == "rate_limit":
        await state.set_state(AdminSettingsStates.waiting_rate_limit_max)
        await callback.message.answer(texts.ADMIN_ASK_RATE_LIMIT_MAX_MESSAGES)
        return

    if field in _NULLABLE_TEXT_FIELDS:
        await state.set_state(AdminSettingsStates.waiting_value)
        await state.update_data(field=field, field_kind="nullable_text")
        await callback.message.answer(_NULLABLE_TEXT_FIELDS[field])
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


@super_router.message(AdminSettingsStates.waiting_value, F.text)
async def setting_value_entered(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    field = data["field"]
    raw = message.text.strip()

    if data["field_kind"] == "int":
        try:
            value = int(raw)
            minimum = 0 if field in _INT_FIELDS_ALLOW_ZERO else 1
            if value < minimum:
                raise ValueError
        except ValueError:
            await message.answer(texts.ADMIN_INVALID_NUMBER)
            return
    elif data["field_kind"] == "decimal":
        try:
            value = Decimal(raw.replace(",", "."))
            if value <= 0:
                raise ValueError
        except (ValueError, InvalidOperation):
            await message.answer(texts.ADMIN_INVALID_NUMBER)
            return
    elif data["field_kind"] == "nullable_text":
        value = None if raw in ("خالی", "پاک کن", "-") else raw
    else:
        value = raw

    await admin_settings_service.update_setting(session, field, value)
    await state.clear()
    await message.answer(texts.ADMIN_SETTING_SAVED)
    await _refresh_settings_menu(message, session)


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
    await _refresh_settings_menu(message, session)


# =============================================================================
# مدیریت فروشگاه‌دارها
# =============================================================================
@router.message(F.text == "👥 مدیریت فروشگاه‌دارها")
async def open_owners_management(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    owners = await shop_owner_service.get_all_registered(session)
    if not owners:
        await message.answer(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    await message.answer(texts.ADMIN_SHOP_OWNERS_INTRO, reply_markup=keyboards.admin_owners_list_keyboard(owners))


@router.callback_query(F.data.startswith("admin_owners_list"))
async def cb_owners_list(callback: CallbackQuery, session: AsyncSession) -> None:
    page = 0
    if ":" in callback.data:
        try:
            page = int(callback.data.split(":", 1)[1])
        except ValueError:
            page = 0

    owners = await shop_owner_service.get_all_registered(session)
    await callback.answer()
    if not owners:
        await callback.message.edit_text(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    await callback.message.edit_text(texts.ADMIN_SHOP_OWNERS_INTRO, reply_markup=keyboards.admin_owners_list_keyboard(owners, page))


async def _render_owner_detail(message: Message, session: AsyncSession, owner_id: int) -> None:
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await message.edit_text(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await message.edit_text(
        texts.admin_shop_owner_detail(owner, shop_bot, owner.wallet_balance_toman), reply_markup=keyboards.admin_owner_detail_keyboard(owner.id, shop_bot)
    )


@router.callback_query(F.data.startswith("admin_owner_view:"))
async def cb_owner_view(callback: CallbackQuery, session: AsyncSession) -> None:
    owner_id = int(callback.data.split(":")[1])
    await callback.answer()
    await _render_owner_detail(callback.message, session, owner_id)


@router.callback_query(F.data.startswith("admin_owner_suspend:"))
async def cb_owner_suspend(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    owner_id = int(callback.data.split(":")[1])
    owner = await shop_owner_service.get_by_id(session, owner_id)
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
    await _render_owner_detail(callback.message, session, owner_id)


@router.callback_query(F.data.startswith("admin_owner_unsuspend:"))
async def cb_owner_unsuspend(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    owner_id = int(callback.data.split(":")[1])
    owner = await shop_owner_service.get_by_id(session, owner_id)
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
    await _render_owner_detail(callback.message, session, owner_id)


# --- اعطای اشتراک هدیه (این‌جلسه) ---
@router.callback_query(F.data.startswith("admin_owner_gift:"))
async def cb_owner_gift_start(callback: CallbackQuery, state: FSMContext) -> None:
    owner_id = int(callback.data.split(":")[1])
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

    data = await state.get_data()
    owner_id = data["gift_owner_id"]
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await state.clear()
        await message.answer(texts.ADMIN_SHOP_OWNERS_EMPTY)
        return

    await wallet_service.add_charge(session, owner, amount_toman, reason=WalletTransactionReason.ADMIN_GRANT)
    gift_shop_bot = await shop_bot_service.get_by_owner(session, owner)
    await audit_log_service.log(
        session,
        AuditEventType.OWNER_GIFT_GRANTED,
        shop_bot_id=gift_shop_bot.id if gift_shop_bot else None,
        actor_telegram_id=message.from_user.id,
        details=f"owner_id={owner_id}, amount_toman={amount_toman}",
    )

    await state.clear()
    await message.answer(texts.admin_gift_confirmation(_owner_display_name(owner), amount_toman))

    try:
        await message.bot.send_message(owner.telegram_id, texts.owner_gift_notification(amount_toman))
    except TelegramAPIError:
        logger.exception("اطلاع‌رسانیِ هدیه‌ی کیف‌پول به فروشگاه‌دار %s ناموفق بود.", owner.telegram_id)

    # نکته: اینجا از _render_owner_detail استفاده نمی‌کنیم چون اون از .edit_text
    # استفاده می‌کنه که فقط روی پیام‌های خودِ ربات کار می‌کنه، نه پیام ورودیِ ادمین.


# --- استرداد/اصلاحِ تراکنشِ کیف‌پول (فازِ ۲-ب، زیربخشِ ۳) ---
@router.callback_query(F.data.startswith("admin_owner_wallet_correction:"))
async def cb_owner_wallet_correction_start(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    owner_id = int(callback.data.split(":")[1])
    owner = await shop_owner_service.get_by_id(session, owner_id)
    if owner is None:
        await callback.answer(texts.ADMIN_SHOP_OWNERS_EMPTY, show_alert=True)
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

    await state.update_data(correction_amount=amount_toman)
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

    if amount_toman > 0:
        await wallet_service.add_charge(session, owner, amount_toman, reason=WalletTransactionReason.ADMIN_CORRECTION, reference=note)
    else:
        applied = await wallet_service.deduct(
            session, owner, abs(amount_toman), reason=WalletTransactionReason.ADMIN_CORRECTION, reference=note
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
    text = texts.AI_POOL_MENU_INTRO if entries else texts.AI_POOL_MENU_INTRO + "\n\n" + texts.AI_POOL_EMPTY
    await message.answer(text, reply_markup=keyboards.ai_pool_list_keyboard(entries))


@super_router.callback_query(F.data == "ai_pool_list")
async def cb_ai_pool_list(callback: CallbackQuery, session: AsyncSession) -> None:
    entries = await ai_pool_service.get_all_entries(session)
    await callback.answer()
    text = texts.AI_POOL_MENU_INTRO if entries else texts.AI_POOL_MENU_INTRO + "\n\n" + texts.AI_POOL_EMPTY
    await callback.message.edit_text(text, reply_markup=keyboards.ai_pool_list_keyboard(entries))


@super_router.callback_query(F.data == "ai_pool_add")
async def cb_ai_pool_add(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(AiPoolStates.waiting_entry_details)
    await callback.message.answer(texts.ASK_AI_POOL_ENTRY)


@super_router.message(AiPoolStates.waiting_entry_details, F.text)
async def ai_pool_entry_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    lines = [line.strip() for line in message.text.strip().splitlines() if line.strip()]
    if len(lines) != 5:
        await message.answer(texts.AI_POOL_ENTRY_INVALID_FORMAT)
        return

    label, api_key, model, base_url, capability_raw = lines
    capability = capability_raw.lower()
    if capability not in (AiKeyCapability.CHAT.value, AiKeyCapability.VISION.value, AiKeyCapability.BOTH.value):
        await message.answer(texts.AI_POOL_ENTRY_INVALID_CAPABILITY)
        return

    await ai_pool_service.add_entry(session, label, api_key, model, base_url, capability)
    await state.clear()
    await message.answer(texts.ai_pool_entry_added_confirmation(label))

    entries = await ai_pool_service.get_all_entries(session)
    await message.answer(texts.AI_POOL_MENU_INTRO, reply_markup=keyboards.ai_pool_list_keyboard(entries))


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
@router.message(F.text == "📜 گزارشِ ممیزی")
async def open_audit_log(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    entries = await audit_log_service.get_recent(session, limit=20)
    if not entries:
        await message.answer(texts.AUDIT_LOG_EMPTY)
        return
    lines = [texts.AUDIT_LOG_INTRO, ""]
    lines.extend(texts.audit_log_entry_line(entry) for entry in entries)
    await message.answer("\n\n".join(lines))


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
    await message.answer(_admin_roles_menu_text(roles), reply_markup=keyboards.admin_roles_list_keyboard(roles))


@super_router.callback_query(F.data == "admin_role_list")
async def cb_admin_role_list(callback: CallbackQuery, session: AsyncSession) -> None:
    roles = await admin_role_service.get_all(session)
    await callback.answer()
    await callback.message.edit_text(_admin_roles_menu_text(roles), reply_markup=keyboards.admin_roles_list_keyboard(roles))


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
    await message.answer(texts.admin_role_added_confirmation(telegram_id))

    roles = await admin_role_service.get_all(session)
    await message.answer(_admin_roles_menu_text(roles), reply_markup=keyboards.admin_roles_list_keyboard(roles))


@super_router.callback_query(F.data.startswith("admin_role_view:"))
async def cb_admin_role_view(callback: CallbackQuery, session: AsyncSession) -> None:
    role_id = int(callback.data.split(":")[1])
    role = await admin_role_service.get_by_id(session, role_id)
    if role is None:
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(texts.admin_role_detail_text(role), reply_markup=keyboards.admin_role_detail_keyboard(role.id))


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
    await callback.message.edit_text(_admin_roles_menu_text(roles), reply_markup=keyboards.admin_roles_list_keyboard(roles))
