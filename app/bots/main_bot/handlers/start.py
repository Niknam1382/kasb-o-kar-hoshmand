from __future__ import annotations

import logging

from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram import F, Router
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import RegistrationStates
from app.config import AuthMode, settings
from app.database.models import ShopOwner, WalletTransactionReason
from app.services import (
    channel_service,
    email_service,
    otp_service,
    shop_bot_service,
    shop_owner_service,
    sms_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import is_valid_email, normalize_iran_phone

logger = logging.getLogger(__name__)

router = Router(name="start")


async def _show_gate_or_continue(message: Message, session: AsyncSession) -> bool:
    """اگه کاربر عضوِ همه‌ی کانال‌های اجباری نباشه، پیامِ گیت رو نشون می‌ده و False برمی‌گردونه."""
    channels = await channel_service.get_mandatory_channels(session)
    if not channels:
        return True

    missing = await channel_service.get_missing_channels(message.bot, channels, message.from_user.id)
    if not missing:
        return True

    await message.answer(texts.channels_gate_intro(missing), reply_markup=keyboards.channels_gate_keyboard(missing, "check_channels_membership"))
    return False


async def _start_registration(message: Message, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.waiting_first_name)
    await message.answer(texts.ASK_FIRST_NAME, reply_markup=ReplyKeyboardRemove())


async def _offer_trial_or_panel(message: Message, session: AsyncSession, owner: ShopOwner) -> None:
    has_had_wallet_activity = await wallet_service.has_ever_had_wallet_activity(session, owner)
    if not has_had_wallet_activity:
        admin_settings = await get_admin_settings(session)
        await message.answer(
            texts.trial_offer_text(admin_settings.reference_channel_link, admin_settings.wallet_trial_credit_toman),
            reply_markup=keyboards.offer_trial_keyboard(),
        )
    else:
        shop_bot = await shop_bot_service.get_by_owner(session, owner)
        tenant_mode = shop_bot.tenant_mode if shop_bot else None
        await message.answer(texts.PANEL_WELCOME_BACK, reply_markup=keyboards.shop_owner_panel_keyboard(tenant_mode))


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, session: AsyncSession, state: FSMContext) -> None:
    if command.args:
        await state.update_data(referred_by_code=command.args.strip())

    if not await _show_gate_or_continue(message, session):
        return

    existing_owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if existing_owner is None:
        admin_settings = await get_admin_settings(session)
        if not admin_settings.allow_new_registrations:
            await message.answer(texts.REGISTRATION_CLOSED)
            return

    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))

    if not owner.registration_completed:
        await _start_registration(message, state)
        return

    await state.clear()
    await _offer_trial_or_panel(message, session, owner)


@router.callback_query(F.data == "check_channels_membership")
async def cb_check_channels_membership(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    channels = await channel_service.get_mandatory_channels(session)
    missing = await channel_service.get_missing_channels(callback.bot, channels, callback.from_user.id)

    if missing:
        await callback.answer(texts.CHANNELS_GATE_STILL_NOT_MEMBER, show_alert=True)
        return

    await callback.answer(texts.CHANNELS_GATE_PASSED)
    await callback.message.delete()

    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, callback.from_user.id, data.get("referred_by_code"))

    if not owner.registration_completed:
        await _start_registration(callback.message, state)
        return

    await state.clear()
    await _offer_trial_or_panel(callback.message, session, owner)


@router.message(RegistrationStates.waiting_first_name, F.text)
async def reg_first_name(message: Message, state: FSMContext) -> None:
    await state.update_data(first_name=message.text.strip())
    await state.set_state(RegistrationStates.waiting_last_name)
    await message.answer(texts.ASK_LAST_NAME)


@router.message(RegistrationStates.waiting_last_name, F.text)
async def reg_last_name(message: Message, state: FSMContext) -> None:
    await state.update_data(last_name=message.text.strip())
    await state.set_state(RegistrationStates.waiting_phone)
    await message.answer(texts.ASK_PHONE, reply_markup=keyboards.request_phone_keyboard())


@router.message(RegistrationStates.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext) -> None:
    await _handle_phone_input(message, state, message.contact.phone_number)


@router.message(RegistrationStates.waiting_phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext) -> None:
    await _handle_phone_input(message, state, message.text)


async def _handle_phone_input(message: Message, state: FSMContext, raw_phone: str) -> None:
    normalized = normalize_iran_phone(raw_phone)
    if normalized is None:
        await message.answer(texts.INVALID_PHONE)
        return

    await state.update_data(phone_number=normalized)
    await state.set_state(RegistrationStates.waiting_email)
    await message.answer(texts.ASK_EMAIL, reply_markup=ReplyKeyboardRemove())


@router.message(RegistrationStates.waiting_email, F.text)
async def reg_email(message: Message, state: FSMContext, session: AsyncSession) -> None:
    email = message.text.strip()
    if not is_valid_email(email):
        await message.answer(texts.INVALID_EMAIL)
        return

    await state.update_data(email=email)

    if settings.auth_mode == AuthMode.TEST:
        await _complete_registration_test_mode(message, state, session)
    elif settings.auth_mode == AuthMode.SMS:
        await _send_phone_otp(message, state, session)
    else:
        await _send_email_otp(message, state, session)


async def _complete_registration_test_mode(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))
    owner = await shop_owner_service.complete_registration(
        session, owner, data["first_name"], data["last_name"], data["phone_number"], data["email"], True, True
    )
    await state.clear()
    await message.answer(texts.registration_complete_welcome(owner.first_name))
    await _offer_trial_or_panel(message, session, owner)


async def _send_phone_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))
    code = await otp_service.generate_otp(session, owner.id, "registration_phone")

    admin_settings_row = await get_admin_settings(session)
    if admin_settings_row.sms_api_key:
        try:
            await sms_service.get_sms_service(admin_settings_row.sms_api_key).send_otp(data["phone_number"], code)
            await message.answer(texts.otp_sent_sms(data["phone_number"]))
        except sms_service.SmsServiceError:
            logger.exception("ارسال پیامکِ OTP ناموفق بود.")
            await message.answer(texts.test_mode_otp_notice(code))
    else:
        await message.answer(texts.test_mode_otp_notice(code))

    await state.set_state(RegistrationStates.waiting_phone_otp)


async def _send_email_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))
    code = await otp_service.generate_otp(session, owner.id, "registration_email")

    try:
        await email_service.send_otp_email(data["email"], code)
        await message.answer(texts.otp_sent_email(data["email"]))
    except email_service.EmailServiceError:
        logger.exception("ارسال ایمیلِ OTP ناموفق بود.")
        await message.answer(texts.test_mode_otp_notice(code))

    await state.set_state(RegistrationStates.waiting_email_otp)


@router.message(RegistrationStates.waiting_phone_otp, F.text)
async def reg_phone_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))

    if not await otp_service.verify_otp(session, owner.id, "registration_phone", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return

    owner = await shop_owner_service.complete_registration(
        session, owner, data["first_name"], data["last_name"], data["phone_number"], data["email"], True, False
    )
    await state.clear()
    await message.answer(texts.registration_complete_welcome(owner.first_name))
    await _offer_trial_or_panel(message, session, owner)


@router.message(RegistrationStates.waiting_email_otp, F.text)
async def reg_email_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))

    if not await otp_service.verify_otp(session, owner.id, "registration_email", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return

    owner = await shop_owner_service.complete_registration(
        session, owner, data["first_name"], data["last_name"], data["phone_number"], data["email"], False, True
    )
    await state.clear()
    await message.answer(texts.registration_complete_welcome(owner.first_name))
    await _offer_trial_or_panel(message, session, owner)


@router.callback_query(F.data == "activate_trial")
async def cb_activate_trial(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    if await wallet_service.has_ever_had_wallet_activity(session, owner):
        await callback.answer("قبلاً از اعتبار آزمایشی استفاده کرده‌ای.", show_alert=True)
        return
    admin_settings = await get_admin_settings(session)
    await wallet_service.add_charge(
        session, owner, admin_settings.wallet_trial_credit_toman, reason=WalletTransactionReason.TRIAL
    )
    await callback.answer()
    await callback.message.edit_text(texts.trial_activated(admin_settings.wallet_trial_credit_toman))
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    tenant_mode = shop_bot.tenant_mode if shop_bot else None
    await callback.message.answer(texts.PANEL_WELCOME_BACK, reply_markup=keyboards.shop_owner_panel_keyboard(tenant_mode))


@router.message(Command("panel"))
async def cmd_panel(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if owner is None or not owner.registration_completed:
        await message.answer(texts.ASK_TO_USE_PANEL_BUTTONS)
        return
    await _offer_trial_or_panel(message, session, owner)
