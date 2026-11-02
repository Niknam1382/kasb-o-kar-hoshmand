from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.common.keyboard_utils import NO_INLINE_KEYBOARD
from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.states import RegistrationStates as RS
from app.config import AuthMode, settings
from app.database.models import ShopOwner, WalletTransactionReason
from app.services import (
    bale_bot_service,
    channel_service,
    email_service,
    otp_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import is_valid_email, normalize_iran_phone, split_last_word, validate_person_name

logger = logging.getLogger(__name__)

router = Router(name="start")

# ترتیبِ قدم‌هایِ ویزارد (A1). «مرور» آخرین قدمه؛ OTPها زیرمجموعه‌یِ قدمِ موبایل/ایمیل‌ان.
_ORDER = ["mode", "first_name", "last_name", "phone", "email", "review"]
_PREVIOUS = {"first_name": "mode", "last_name": "first_name", "phone": "last_name", "email": "phone"}
_STATE_STEP = {
    RS.choosing_mode.state: "mode",
    RS.waiting_first_name.state: "first_name",
    RS.confirming_first_name.state: "first_name",
    RS.waiting_last_name.state: "last_name",
    RS.waiting_phone.state: "phone",
    RS.waiting_phone_otp.state: "phone",
    RS.waiting_email.state: "email",
    RS.waiting_email_otp.state: "email",
    RS.reviewing.state: "review",
}
_ALL_REG_STATES = (
    RS.choosing_mode, RS.waiting_first_name, RS.confirming_first_name, RS.waiting_last_name,
    RS.waiting_phone, RS.waiting_phone_otp, RS.waiting_email, RS.waiting_email_otp, RS.reviewing,
)


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


async def _prompt(message: Message, state: FSMContext, step: str) -> None:
    """پرسشِ یک قدم رو می‌فرسته و stateِ متناظر رو ست می‌کنه (مقدارِ قبلی به‌عنوانِ راهنما نشون داده می‌شه)."""
    data = await state.get_data()
    if step == "mode":
        await state.set_state(RS.choosing_mode)
        await message.answer(texts.REG_ASK_MODE, reply_markup=keyboards.reg_mode_keyboard())
    elif step == "first_name":
        await state.set_state(RS.waiting_first_name)
        await message.answer(texts.ASK_FIRST_NAME + texts.reg_hint_previous(data.get("first_name")), reply_markup=keyboards.reg_nav_keyboard())
    elif step == "last_name":
        await state.set_state(RS.waiting_last_name)
        await message.answer(texts.ASK_LAST_NAME + texts.reg_hint_previous(data.get("last_name")), reply_markup=keyboards.reg_nav_keyboard())
    elif step == "phone":
        await state.set_state(RS.waiting_phone)
        await message.answer(texts.ASK_PHONE, reply_markup=keyboards.reg_nav_keyboard(with_contact=True))
    elif step == "email":
        await state.set_state(RS.waiting_email)
        await message.answer(texts.ASK_EMAIL + texts.reg_hint_previous(data.get("email")), reply_markup=keyboards.reg_nav_keyboard())
    else:
        await state.update_data(return_to_review=False)
        await state.set_state(RS.reviewing)
        data = await state.get_data()
        await message.answer(texts.reg_review_text(data), reply_markup=keyboards.reg_review_keyboard())


async def _advance(message: Message, state: FSMContext, done: str) -> None:
    """بعد از تمامِ‌شدنِ یک قدم: اگه از «مرور» برای اصلاح اومده بودیم برمی‌گردیم به مرور، وگرنه قدمِ بعدی."""
    data = await state.get_data()
    if data.get("return_to_review"):
        await _prompt(message, state, "review")
        return
    await _prompt(message, state, _ORDER[_ORDER.index(done) + 1])


async def _start_registration(message: Message, state: FSMContext) -> None:
    await state.update_data(return_to_review=False)
    await _prompt(message, state, "mode")


async def _resume(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    await message.answer(texts.REG_RESUME)
    await _prompt(message, state, _STATE_STEP.get(current, "mode"))


async def _offer_trial_or_panel(message: Message, session: AsyncSession, owner: ShopOwner) -> None:
    has_had_wallet_activity = await wallet_service.has_ever_had_wallet_activity(session, owner)
    if not has_had_wallet_activity:
        admin_settings = await get_admin_settings(session)
        await message.answer(
            texts.trial_offer_text(admin_settings.reference_channel_link, admin_settings.wallet_trial_credit_toman),
            reply_markup=keyboards.offer_trial_keyboard(),
        )
    else:
        await message.answer(texts.PANEL_WELCOME_BACK, reply_markup=keyboards.shop_owner_panel_keyboard(owner.business_mode, bale_visible=await bale_bot_service.visible_for(session)))


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
            await message.answer(texts.registration_closed_text(admin_settings))
            return

    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))

    if not owner.registration_completed:
        if await state.get_state() in _STATE_STEP:
            await _resume(message, state)  # /start وسطِ ویزارد: از همون قدم ادامه بده، از صفر شروع نکن
        else:
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


# ------------------------------------------------------------------ ناوبری (برگشت / انصراف) — قبلِ هندلرهایِ عمومیِ متن
@router.message(StateFilter(*_ALL_REG_STATES), F.text == texts.REG_BACK_BUTTON)
async def reg_back(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    data = await state.get_data()
    step = _STATE_STEP.get(current, "mode")
    if data.get("return_to_review") and current != RS.reviewing.state:
        await _prompt(message, state, "review")  # اصلاحِ یک فیلد رو رها کرد
    elif current in (RS.waiting_phone_otp.state, RS.waiting_email_otp.state, RS.confirming_first_name.state):
        await _prompt(message, state, step)  # برگشت = اصلاحِ همون شماره/ایمیل/نام
    else:
        await _prompt(message, state, _PREVIOUS.get(step, step))


@router.message(StateFilter(*_ALL_REG_STATES), F.text == texts.REG_CANCEL_BUTTON)
async def reg_cancel_text(message: Message) -> None:
    await message.answer(texts.REG_CANCEL_ASK, reply_markup=keyboards.reg_cancel_confirm_keyboard())


@router.callback_query(StateFilter(*_ALL_REG_STATES), F.data == "reg_cancel")
async def cb_reg_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    await callback.message.answer(texts.REG_CANCEL_ASK, reply_markup=keyboards.reg_cancel_confirm_keyboard())


@router.callback_query(StateFilter(*_ALL_REG_STATES), F.data == "reg_cancel_yes")
async def cb_reg_cancel_yes(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await callback.message.answer(texts.REG_CANCELLED, reply_markup=ReplyKeyboardRemove())


@router.callback_query(StateFilter(*_ALL_REG_STATES), F.data == "reg_cancel_no")
async def cb_reg_cancel_no(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _resume(callback.message, state)


# ------------------------------------------------------------------ قدمِ ۰: مود (A3)
@router.callback_query(RS.choosing_mode, F.data.startswith("reg_mode:"))
async def cb_reg_mode(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        mode = shop_owner_service.normalize_business_mode(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer(texts.REG_STALE_BUTTON, show_alert=True)
        return
    await callback.answer()
    await state.update_data(mode=mode)
    await _advance(callback.message, state, "mode")


# ------------------------------------------------------------------ قدمِ ۱: نامِ کوچک (+ نامِ دوکلمه‌ای)
@router.message(RS.waiting_first_name, F.text)
async def reg_first_name(message: Message, state: FSMContext) -> None:
    name, error = validate_person_name(message.text)
    if error:
        await message.answer(texts.REG_NAME_BAD_LENGTH if error == "length" else texts.REG_NAME_BAD_CHARS)
        return
    if len(name.split()) >= 2:
        await state.update_data(pending_first_name=name)
        await state.set_state(RS.confirming_first_name)
        await message.answer(texts.reg_first_name_two_words(name), reply_markup=keyboards.reg_first_name_choice_keyboard())
        return
    await state.update_data(first_name=name)
    await _advance(message, state, "first_name")


@router.callback_query(RS.confirming_first_name, F.data == "reg_fn_keep")
async def cb_fn_keep(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await callback.answer()
    await state.update_data(first_name=data["pending_first_name"])
    await _advance(callback.message, state, "first_name")


@router.callback_query(RS.confirming_first_name, F.data == "reg_fn_split")
async def cb_fn_split(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    first, last = split_last_word(data["pending_first_name"])
    first, first_error = validate_person_name(first)
    last, last_error = validate_person_name(last)
    await callback.answer()
    if first_error or last_error:
        await _prompt(callback.message, state, "first_name")
        return
    await state.update_data(first_name=first, last_name=last)
    await _advance(callback.message, state, "last_name")  # نامِ خانوادگی همین‌جا گرفته شد


@router.callback_query(RS.confirming_first_name, F.data == "reg_fn_edit")
async def cb_fn_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _prompt(callback.message, state, "first_name")


# ------------------------------------------------------------------ قدمِ ۲: نامِ خانوادگی
@router.message(RS.waiting_last_name, F.text)
async def reg_last_name(message: Message, state: FSMContext) -> None:
    name, error = validate_person_name(message.text)
    if error:
        await message.answer(texts.REG_NAME_BAD_LENGTH if error == "length" else texts.REG_NAME_BAD_CHARS)
        return
    await state.update_data(last_name=name)
    await _advance(message, state, "last_name")


# ------------------------------------------------------------------ قدمِ ۳: موبایل (+OTP طبقِ AUTH_MODE)
@router.message(RS.waiting_phone, F.contact)
async def reg_phone_contact(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner_id_of_contact = message.contact.user_id
    if owner_id_of_contact is not None and owner_id_of_contact != message.from_user.id:
        await message.answer(texts.REG_PHONE_NOT_YOURS)
        return
    await _handle_phone_input(message, state, session, message.contact.phone_number)


@router.message(RS.waiting_phone, F.text)
async def reg_phone_text(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await _handle_phone_input(message, state, session, message.text)


async def _handle_phone_input(message: Message, state: FSMContext, session: AsyncSession, raw_phone: str) -> None:
    normalized = normalize_iran_phone(raw_phone)
    if normalized is None:
        await message.answer(texts.INVALID_PHONE)
        return
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if await shop_owner_service.find_other_by_phone(session, normalized, exclude_owner_id=owner.id if owner else None):
        await message.answer(texts.REG_PHONE_TAKEN)
        return

    await state.update_data(phone_number=normalized, phone_verified=settings.auth_mode == AuthMode.TEST)
    if settings.auth_mode == AuthMode.SMS:
        await _send_phone_otp(message, state, session)
    else:
        await _advance(message, state, "phone")


# ------------------------------------------------------------------ قدمِ ۴: ایمیل (+OTP طبقِ AUTH_MODE)
@router.message(RS.waiting_email, F.text)
async def reg_email(message: Message, state: FSMContext, session: AsyncSession) -> None:
    email = message.text.strip()
    if not is_valid_email(email):
        await message.answer(texts.INVALID_EMAIL)
        return
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if await shop_owner_service.find_other_by_email(session, email, exclude_owner_id=owner.id if owner else None):
        await message.answer(texts.REG_EMAIL_TAKEN)
        return

    await state.update_data(email=email, email_verified=settings.auth_mode == AuthMode.TEST)
    if settings.auth_mode == AuthMode.EMAIL:
        await _send_email_otp(message, state, session)
    else:
        await _advance(message, state, "email")


async def _send_phone_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))
    admin_settings_row = await get_admin_settings(session)
    phone = data["phone_number"]
    # A3: درِ سرویسِ پیامک، سقفِ ساعتیِ هر شماره و جایگزینِ روشنِ «کد در چت» همه در یک نقطه.
    delivery = await otp_service.send_phone_code(
        session, shop_owner_id=owner.id, purpose="registration_phone", phone=phone, admin_settings=admin_settings_row
    )
    if delivery.reason == "rate_limited":
        # سقفِ ساعتی خوردیم: کد را نشان نمی‌دهیم (وگرنه سقف بی‌معناست) و کاربر به گامِ شماره برمی‌گردد.
        await state.set_state(RS.waiting_phone)
        await message.answer(texts.OTP_RATE_LIMITED)
        return
    await message.answer(texts.otp_sent_sms(phone) if delivery.delivered else texts.test_mode_otp_notice(delivery.code))

    await message.answer(texts.REG_OTP_HINT)
    await state.set_state(RS.waiting_phone_otp)


async def _send_email_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    owner = await shop_owner_service.get_or_create_shop_owner(session, message.from_user.id, data.get("referred_by_code"))
    code = await otp_service.generate_otp(session, owner.id, "registration_email")

    try:
        await email_service.send_otp_email(data["email"], code)
        await message.answer(texts.otp_sent_email(data["email"]))
    except email_service.EmailServiceError:
        logger.exception("ارسالِ ایمیلِ OTP ناموفق بود.")
        await message.answer(texts.test_mode_otp_notice(code))

    await message.answer(texts.REG_OTP_HINT)
    await state.set_state(RS.waiting_email_otp)


@router.message(RS.waiting_phone_otp, F.text)
async def reg_phone_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if owner is None or not await otp_service.verify_otp(session, owner.id, "registration_phone", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return
    await state.update_data(phone_verified=True)
    await _advance(message, state, "phone")


@router.message(RS.waiting_email_otp, F.text)
async def reg_email_otp(message: Message, state: FSMContext, session: AsyncSession) -> None:
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if owner is None or not await otp_service.verify_otp(session, owner.id, "registration_email", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return
    await state.update_data(email_verified=True)
    await _advance(message, state, "email")


# ------------------------------------------------------------------ قدمِ ۵: مرورِ نهایی
@router.callback_query(RS.reviewing, F.data.startswith("reg_edit:"))
async def cb_reg_edit(callback: CallbackQuery, state: FSMContext) -> None:
    step = callback.data.split(":", 1)[1]
    if step not in ("first_name", "last_name", "phone", "email", "mode"):
        await callback.answer(texts.REG_STALE_BUTTON, show_alert=True)
        return
    await callback.answer()
    await state.update_data(return_to_review=True)
    await _prompt(callback.message, state, step)


@router.callback_query(RS.reviewing, F.data == "reg_confirm")
async def cb_reg_confirm(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()  # اول پاک کن: دابل‌تپ نباید دو بار ثبت/خوش‌آمد بسازه
    await callback.answer()
    if any(not data.get(key) for key in ("mode", "first_name", "last_name", "phone_number", "email")):
        await state.update_data(referred_by_code=data.get("referred_by_code"))
        await callback.message.answer(texts.REG_INCOMPLETE)
        await _start_registration(callback.message, state)
        return

    owner = await shop_owner_service.get_or_create_shop_owner(session, callback.from_user.id, data.get("referred_by_code"))
    owner = await shop_owner_service.complete_registration(
        session, owner, data["first_name"], data["last_name"], data["phone_number"], data["email"],
        bool(data.get("phone_verified")), bool(data.get("email_verified")),
        business_mode=data["mode"], username=callback.from_user.username,
    )
    try:
        await callback.message.edit_reply_markup(reply_markup=NO_INLINE_KEYBOARD)
    except TelegramBadRequest:
        pass
    await callback.message.answer(texts.registration_complete_welcome(owner.first_name), reply_markup=ReplyKeyboardRemove())
    await _offer_trial_or_panel(callback.message, session, owner)


# دکمه‌یِ اینلاینِ ثبت‌نام بعد از ری‌استارت/انصراف/اتمام: پیامِ مودبانه، نه سکوت
@router.callback_query(F.data.startswith("reg_"))
async def cb_reg_stale(callback: CallbackQuery) -> None:
    await callback.answer(texts.REG_STALE_BUTTON, show_alert=True)


@router.callback_query(F.data == "activate_trial")
async def cb_activate_trial(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    if await wallet_service.has_ever_had_wallet_activity(session, owner):
        await callback.answer("قبلاً از اعتبار آزمایشی استفاده کرده‌ای.", show_alert=True)
        return
    admin_settings = await get_admin_settings(session)
    try:
        await wallet_service.add_charge(
            session,
            owner,
            admin_settings.wallet_trial_credit_toman,
            reason=WalletTransactionReason.TRIAL,
            reference="trial",
        )
    except IntegrityError:
        # دو تپِ هم‌زمان رویِ همان دکمه: چکِ «فعالیت داشته؟» هر دو رد می‌کند چون هیچ‌کدام هنوز
        # چیزی ننوشته. کلیدِ `charge:trial:owner:{id}` در دفتر تنها سدِ واقعی است ⇒ یکی می‌برد.
        await session.rollback()
        logger.info("تلاشِ دوباره برایِ اعتبارِ آزمایشیِ فروشگاه‌دار %s رد شد.", owner.id)
        await callback.answer("قبلاً از اعتبار آزمایشی استفاده کرده‌ای.", show_alert=True)
        return
    await callback.answer()
    await callback.message.edit_text(texts.trial_activated(admin_settings.wallet_trial_credit_toman))
    await callback.message.answer(texts.PANEL_WELCOME_BACK, reply_markup=keyboards.shop_owner_panel_keyboard(owner.business_mode, bale_visible=await bale_bot_service.visible_for(session)))


@router.message(Command("panel"))
async def cmd_panel(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    if owner is None or not owner.registration_completed:
        await message.answer(texts.ASK_TO_USE_PANEL_BUTTONS)
        return
    await _offer_trial_or_panel(message, session, owner)
