"""پروفایلِ فروشگاه‌دار (A2) + تغییرِ نوعِ کسب‌وکار (A3). «👤 پروفایل من» و «✏️ ویرایش اطلاعات» یکی‌ان."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import safe_edit
from app.bots.main_bot.states import ProfileStates as PS
from app.config import AuthMode, settings
from app.database.models import AuditEventType, ShopOwner
from app.services import audit_log_service, email_service, order_service, otp_service, shop_bot_service, shop_owner_service
from app.services.admin_settings_service import get_admin_settings
from app.utils.validators import is_valid_email, mask_phone, normalize_iran_phone, validate_person_name

logger = logging.getLogger(__name__)
router = Router(name="profile")

_FIELD_STATE = {"first_name": PS.waiting_first_name, "last_name": PS.waiting_last_name, "phone": PS.waiting_phone, "email": PS.waiting_email}


def _mask_email(email: str) -> str:
    name, _, domain = email.partition("@")
    return f"{name[:1]}***@{domain}"


async def _owner(event, session: AsyncSession) -> ShopOwner | None:
    owner = await shop_owner_service.get_by_telegram_id(session, event.from_user.id)
    return owner if owner is not None and owner.registration_completed else None


async def _card(session: AsyncSession, owner: ShopOwner) -> tuple[str, object]:
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    return texts.owner_profile_text(owner, shop_bot, owner.wallet_balance_toman), keyboards.profile_keyboard()


async def _send_card(message: Message, session: AsyncSession, owner: ShopOwner) -> None:
    text, markup = await _card(session, owner)
    await message.answer(text, reply_markup=markup)


async def _audit(session: AsyncSession, owner: ShopOwner, tg_id: int, detail: str, event=AuditEventType.OWNER_PROFILE_UPDATED) -> None:
    await audit_log_service.log(session, event, actor_telegram_id=tg_id, details=detail)


# ------------------------------------------------------------------ نمایش (دکمه‌هایِ قدیمی هم همین‌جا می‌رسن)
@router.message(F.text.in_({"👤 پروفایل من", "✏️ ویرایش اطلاعات", "🔀 نوعِ کسب‌وکار"}))
async def open_profile(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    owner = await _owner(message, session)
    if owner is None:
        await message.answer(texts.PROFILE_NOT_REGISTERED)
        return
    await _send_card(message, session, owner)


@router.message(F.text == "📞 پشتیبانی")
async def open_platform_support(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    extra = texts.platform_support_lines(await get_admin_settings(session))
    await message.answer(extra or texts.PROFILE_SUPPORT_NOT_SET)


@router.callback_query(F.data == "pf_back")
async def cb_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    owner = await _owner(callback, session)
    await callback.answer()
    if owner is not None:
        text, markup = await _card(session, owner)
        await safe_edit(callback, text, markup)


@router.callback_query(F.data == "pf_support")
async def cb_support(callback: CallbackQuery, session: AsyncSession) -> None:
    await callback.answer()
    extra = texts.platform_support_lines(await get_admin_settings(session))
    await callback.message.answer(extra or texts.PROFILE_SUPPORT_NOT_SET)


# ------------------------------------------------------------------ ویرایشِ فیلدها
@router.callback_query(F.data.startswith("pf_edit:"))
async def cb_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    owner = await _owner(callback, session)
    if owner is None or field not in _FIELD_STATE:
        await callback.answer(texts.PROFILE_STALE, show_alert=True)
        return
    await callback.answer()
    await state.set_state(_FIELD_STATE[field])
    await callback.message.answer(texts.profile_ask(field))


async def _save_name(message: Message, session: AsyncSession, state: FSMContext, field: str) -> None:
    owner = await _owner(message, session)
    name, error = validate_person_name(message.text)
    if owner is None:
        await state.clear()
        await message.answer(texts.PROFILE_NOT_REGISTERED)
        return
    if error:
        await message.answer(texts.REG_NAME_BAD_LENGTH if error == "length" else texts.REG_NAME_BAD_CHARS)
        return
    await shop_owner_service.update_name(session, owner, **{field: name})
    await _audit(session, owner, message.from_user.id, f"{field} عوض شد")
    await state.clear()
    await message.answer(texts.PROFILE_UPDATED)
    await _send_card(message, session, owner)


@router.message(PS.waiting_first_name, F.text)
async def pf_first_name(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_name(message, session, state, "first_name")


@router.message(PS.waiting_last_name, F.text)
async def pf_last_name(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _save_name(message, session, state, "last_name")


async def _finish(message: Message, session: AsyncSession, state: FSMContext, owner: ShopOwner, detail: str) -> None:
    await _audit(session, owner, message.from_user.id, detail)
    await state.clear()
    await message.answer(texts.PROFILE_UPDATED)
    await _send_card(message, session, owner)


@router.message(PS.waiting_phone, F.text)
async def pf_phone(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _owner(message, session)
    phone = normalize_iran_phone(message.text)
    if owner is None:
        await state.clear()
        return
    if phone is None:
        await message.answer(texts.INVALID_PHONE)
        return
    if await shop_owner_service.find_other_by_phone(session, phone, exclude_owner_id=owner.id):
        await message.answer(texts.REG_PHONE_TAKEN)
        return
    if settings.auth_mode != AuthMode.SMS:
        await shop_owner_service.update_phone(session, owner, phone, settings.auth_mode == AuthMode.TEST)
        await _finish(message, session, state, owner, f"phone → {mask_phone(phone)}")
        return
    row = await get_admin_settings(session)
    # A3: همان منطقِ واحدِ ثبت‌نام — درِ پیامک، سقفِ ساعتی و جایگزینِ «کد در چت».
    delivery = await otp_service.send_phone_code(
        session, shop_owner_id=owner.id, purpose="profile_phone", phone=phone, admin_settings=row
    )
    if delivery.reason == "rate_limited":
        await state.clear()
        await message.answer(texts.OTP_RATE_LIMITED)
        return
    await message.answer(texts.otp_sent_sms(phone) if delivery.delivered else texts.test_mode_otp_notice(delivery.code))
    await message.answer(texts.PROFILE_OTP_NOTE)
    await state.update_data(new_phone=phone)
    await state.set_state(PS.waiting_phone_otp)


@router.message(PS.waiting_phone_otp, F.text)
async def pf_phone_otp(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _owner(message, session)
    data = await state.get_data()
    if owner is None or not data.get("new_phone"):
        await state.clear()
        return
    if not await otp_service.verify_otp(session, owner.id, "profile_phone", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return
    await shop_owner_service.update_phone(session, owner, data["new_phone"], True)
    await _finish(message, session, state, owner, f"phone → {mask_phone(data['new_phone'])}")


@router.message(PS.waiting_email, F.text)
async def pf_email(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _owner(message, session)
    email = message.text.strip()
    if owner is None:
        await state.clear()
        return
    if not is_valid_email(email):
        await message.answer(texts.INVALID_EMAIL)
        return
    if await shop_owner_service.find_other_by_email(session, email, exclude_owner_id=owner.id):
        await message.answer(texts.REG_EMAIL_TAKEN)
        return
    if settings.auth_mode != AuthMode.EMAIL:
        await shop_owner_service.update_email(session, owner, email, settings.auth_mode == AuthMode.TEST)
        await _finish(message, session, state, owner, f"email → {_mask_email(email)}")
        return
    code = await otp_service.generate_otp(session, owner.id, "profile_email")
    try:
        await email_service.send_otp_email(email, code)
        await message.answer(texts.otp_sent_email(email))
    except email_service.EmailServiceError:
        await message.answer(texts.test_mode_otp_notice(code))
    await message.answer(texts.PROFILE_OTP_NOTE)
    await state.update_data(new_email=email)
    await state.set_state(PS.waiting_email_otp)


@router.message(PS.waiting_email_otp, F.text)
async def pf_email_otp(message: Message, session: AsyncSession, state: FSMContext) -> None:
    owner = await _owner(message, session)
    data = await state.get_data()
    if owner is None or not data.get("new_email"):
        await state.clear()
        return
    if not await otp_service.verify_otp(session, owner.id, "profile_email", message.text.strip()):
        await message.answer(texts.OTP_INVALID_OR_EXPIRED)
        return
    await shop_owner_service.update_email(session, owner, data["new_email"], True)
    await _finish(message, session, state, owner, f"email → {_mask_email(data['new_email'])}")


# ------------------------------------------------------------------ نوعِ کسب‌وکار (A3): کارت ← هشدار ← تاییدِ دوباره ← ثبت
async def _blocked_by_open_orders(session: AsyncSession, owner: ShopOwner) -> bool:
    shop_bot = await shop_bot_service.get_by_owner(session, owner)
    return shop_bot is not None and await order_service.count_open_orders(session, shop_bot.id) > 0


@router.callback_query(F.data == "pf_mode")
async def cb_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _owner(callback, session)
    if owner is None:
        await callback.answer(texts.PROFILE_STALE, show_alert=True)
        return
    if await _blocked_by_open_orders(session, owner):
        await callback.answer(texts.TENANT_MODE_BLOCKED, show_alert=True)
        return
    await callback.answer()
    target = "sales" if owner.business_mode == "consultation" else "consultation"
    await safe_edit(callback, texts.tenant_mode_ask_text(owner.business_mode, target), keyboards.tenant_mode_ask_keyboard(target))


@router.callback_query(F.data.startswith("tenant_mode_ask:"))
async def cb_mode_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _owner(callback, session)
    try:
        target = shop_owner_service.normalize_business_mode(callback.data.split(":", 1)[1])
    except ValueError:
        target = None
    if owner is None or target is None:
        await callback.answer(texts.PROFILE_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, texts.tenant_mode_confirm_text(target), keyboards.tenant_mode_confirm_keyboard(target))


@router.callback_query(F.data.startswith("set_tenant_mode:"))
async def cb_set_mode(callback: CallbackQuery, session: AsyncSession) -> None:
    owner = await _owner(callback, session)
    try:
        mode = shop_owner_service.normalize_business_mode(callback.data.split(":", 1)[1])
    except ValueError:
        mode = None
    if owner is None or mode is None:
        await callback.answer(texts.PROFILE_STALE, show_alert=True)
        return
    if await _blocked_by_open_orders(session, owner):  # بینِ دو تاییدِ کاربر ممکنه سفارش اومده باشه
        await callback.answer(texts.TENANT_MODE_BLOCKED, show_alert=True)
        return
    await callback.answer()
    old = owner.business_mode
    await shop_owner_service.set_business_mode(session, owner, mode)
    await _audit(session, owner, callback.from_user.id, f"{old} → {mode}", AuditEventType.OWNER_BUSINESS_MODE_CHANGED)
    await safe_edit(callback, texts.tenant_mode_saved_confirmation(mode))
    await callback.message.answer(texts.PANEL_WELCOME_BACK, reply_markup=keyboards.shop_owner_panel_keyboard(mode))

