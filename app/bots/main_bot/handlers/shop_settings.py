"""
پنلِ فروشگاه‌دار — «⚙️ تنظیماتِ ربات فروشگاه» (فازِ ۶-الف). مواردِ per-shop که هزینه/تجربه‌شان با
خودِ فروشگاه‌دار است: مدتِ تجمیعِ پیام‌هایِ مشتری (۲ تا ۶۰ ثانیه)، زمانِ گزارشِ دوره‌ای (P18 · B5) و
پشتیبانیِ مشتری‌ها (D1/D2). تنظیم‌هایِ بعدی همین‌جا اضافه می‌شن.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.services.admin_settings_service import get_admin_settings  # noqa: E402
from app.bots.main_bot.handlers.owner_common import parse_suffix_int, require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import ShopSettingsStates
from app.services import bot_branding_service, shop_bot_service
from app.utils.validators import fa_text, normalize_telegram_username, to_e164_iran

router = Router(name="shop_settings")


def _screen(shop_bot):
    text = texts.shop_settings_text(shop_bot, shop_bot_service.DEFAULT_MESSAGE_BATCH_SECONDS)
    return text, keyboards.shop_settings_keyboard(shop_bot)


@router.message(F.text == texts.SHOP_SETTINGS_BUTTON)
async def open_shop_settings(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, keyboard = _screen(shop_bot)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("bs_batch:"))
async def batch_preset(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    seconds = shop_bot_service.parse_batch_seconds(parse_suffix_int(callback.data, "bs_batch:"))
    if seconds is None:
        await callback.answer(texts.SHOP_SETTINGS_STALE, show_alert=True)
        return
    await shop_bot_service.set_message_batch_seconds(session, shop_bot, seconds)
    text, keyboard = _screen(shop_bot)
    await callback.answer(texts.BATCH_SECONDS_SAVED)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "bs_batch_reset")
async def batch_reset(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await shop_bot_service.set_message_batch_seconds(session, shop_bot, None)
    text, keyboard = _screen(shop_bot)
    await callback.answer(texts.BATCH_SECONDS_RESET)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "bs_batch_custom")
async def batch_custom_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_batch_seconds)
    await callback.answer()
    await callback.message.answer(texts.BATCH_SECONDS_ASK)


@router.message(ShopSettingsStates.waiting_batch_seconds, F.text)
async def batch_custom_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    seconds = shop_bot_service.parse_batch_seconds(message.text)
    if seconds is None:
        await message.answer(texts.BATCH_SECONDS_INVALID)
        return
    await shop_bot_service.set_message_batch_seconds(session, shop_bot, seconds)
    await state.clear()
    await message.answer(texts.BATCH_SECONDS_SAVED)
    text, keyboard = _screen(shop_bot)
    await message.answer(text, reply_markup=keyboard)


# ------------------------------------------------------------------ P18 · B5: زمانِ گزارشِ دوره‌ای (روزِ هفته + ساعتِ تهران)
def _report_screen(shop_bot):
    return texts.report_schedule_text(shop_bot), keyboards.shop_report_keyboard(shop_bot)


@router.callback_query(F.data == "rp_open")
async def report_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _report_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "rp_back")
async def report_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "rp_toggle")
async def report_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    now_enabled = not shop_bot.weekly_report_enabled
    await shop_bot_service.set_report_schedule(session, shop_bot, enabled=now_enabled)
    await callback.answer(texts.switch_toast("گزارشِ دوره‌ای", now_enabled))
    text, keyboard = _report_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("rp_day:"))
async def report_weekday(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    weekday = parse_suffix_int(callback.data, "rp_day:")
    if weekday is None or not shop_bot_service.valid_report_weekday(weekday):
        await callback.answer(texts.SHOP_SETTINGS_STALE, show_alert=True)
        return
    await shop_bot_service.set_report_schedule(session, shop_bot, weekday=weekday)
    await callback.answer(texts.REPORT_SCHEDULE_SAVED)
    text, keyboard = _report_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("rp_hour:"))
async def report_hour_preset(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    hour = parse_suffix_int(callback.data, "rp_hour:")
    if hour is None or not (shop_bot_service.REPORT_HOUR_MIN <= hour <= shop_bot_service.REPORT_HOUR_MAX):
        await callback.answer(texts.SHOP_SETTINGS_STALE, show_alert=True)
        return
    await shop_bot_service.set_report_schedule(session, shop_bot, hour=hour)
    await callback.answer(texts.REPORT_SCHEDULE_SAVED)
    text, keyboard = _report_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "rp_hour_custom")
async def report_hour_custom_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_report_hour)
    await callback.answer()
    await callback.message.answer(texts.REPORT_HOUR_ASK)


@router.message(ShopSettingsStates.waiting_report_hour, F.text)
async def report_hour_custom_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    hour = shop_bot_service.parse_report_hour(message.text)
    if hour is None:
        await message.answer(texts.REPORT_HOUR_INVALID)
        return
    await shop_bot_service.set_report_schedule(session, shop_bot, hour=hour)
    await state.clear()
    await message.answer(texts.REPORT_SCHEDULE_SAVED)
    text, keyboard = _report_screen(shop_bot)
    await message.answer(text, reply_markup=keyboard)


# ------------------------------------------------------------------ P18 · A2: بیوگرافیِ ربات (متنِ خودِ فروشگاه‌دار)
def _branding_screen(shop_bot, admin_settings):
    return (
        texts.branding_owner_text(shop_bot, admin_settings.branding_text),
        keyboards.shop_branding_keyboard(shop_bot),
    )


@router.callback_query(F.data == "br_open")
async def branding_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _branding_screen(shop_bot, await get_admin_settings(session))
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "br_back")
async def branding_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "br_edit")
async def branding_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_branding_text)
    await callback.answer()
    await callback.message.answer(texts.BRANDING_OWNER_ASK)


@router.message(ShopSettingsStates.waiting_branding_text, F.text)
async def branding_text_received(message: Message, session: AsyncSession, state: FSMContext, bot_manager) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    raw = message.text.strip()
    if raw in {"خالی", "پاک کن", "-"}:
        shop_bot.branding_owner_text = None
    elif bot_branding_service.valid_owner_text(raw):
        shop_bot.branding_owner_text = raw.strip()
    else:
        await message.answer(texts.BRANDING_OWNER_INVALID)  # state می‌ماند تا کوتاه‌تر بنویسد
        return
    await session.flush()
    await state.clear()
    admin_settings = await get_admin_settings(session)
    # بیو باید رویِ رباتِ *خودِ فروشگاه* نوشته شود؛ message.bot در این پنل رباتِ اصلی است.
    outcome = await bot_branding_service.apply_for_shop_bot(bot_manager, session, shop_bot)
    await message.answer(_branding_save_message(outcome))
    text, keyboard = _branding_screen(shop_bot, admin_settings)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "bs_stock")
async def stock_threshold_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """P21-D (F7): خودِ فروشگاه‌دار تعیین می‌کند کِی از اتمامِ موجودی باخبر شود (NULL ⇒ خاموش)."""
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_stock_threshold)
    await callback.answer()
    await callback.message.answer(texts.ASK_STOCK_THRESHOLD)


@router.message(ShopSettingsStates.waiting_stock_threshold, F.text)
async def stock_threshold_entered(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    raw = message.text.strip()
    if raw in {"خالی", "پاک کن", "-"}:
        shop_bot.low_stock_alert_threshold = None
        saved = texts.STOCK_THRESHOLD_OFF
    elif raw.isdecimal() and 1 <= int(raw) <= 1000:
        shop_bot.low_stock_alert_threshold = int(raw)
        saved = fa_text(texts.STOCK_THRESHOLD_SAVED, value=int(raw))
    else:
        await message.answer(texts.STOCK_THRESHOLD_INVALID)
        return
    await session.flush()
    await state.clear()
    await message.answer(saved)
    text, keyboard = _screen(shop_bot)
    await message.answer(text, reply_markup=keyboard)


def _branding_save_message(outcome: str) -> str:
    if outcome == bot_branding_service.SKIPPED:
        return texts.BRANDING_NOT_CONFIGURED
    if outcome == bot_branding_service.NO_TRANSPORT:
        return texts.BRANDING_OWNER_SAVED_NOT_CONNECTED
    if outcome == bot_branding_service.ERROR:
        return texts.BRANDING_OWNER_SAVE_RETRY
    return texts.BRANDING_OWNER_SAVED


def _branding_check_message(outcome: str) -> str:
    if outcome == bot_branding_service.UNCHANGED:
        return texts.BRANDING_CHECK_HEALTHY
    if outcome == bot_branding_service.TAMPERED:
        return texts.BRANDING_CHECK_TAMPERED
    if outcome == bot_branding_service.REMOVED:
        return texts.BRANDING_CHECK_REMOVED
    if outcome == bot_branding_service.APPLIED:
        return texts.BRANDING_CHECK_RESTORED
    if outcome == bot_branding_service.NO_TRANSPORT:
        return texts.BRANDING_CHECK_NOT_CONNECTED
    if outcome == bot_branding_service.SKIPPED:
        return texts.BRANDING_CHECK_NO_TEXT
    return texts.BRANDING_CHECK_ERROR


@router.callback_query(F.data == "br_check")
async def branding_check_now(callback: CallbackQuery, session: AsyncSession, bot_manager) -> None:
    """P21-A: «همین الان چک کن» — بیو رویِ رباتِ تلگرام و بله‌یِ *همین* فروشگاه بازبینی می‌شود.

    `_apply_to_bot` هیچ‌وقت رباتِ اصلی را نمی‌گیرد؛ این هندلر فقط shop_bot می‌دهد و خودِ سرویس
    ترنسپورت را از منیجر می‌خواند.
    """
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    outcome = await bot_branding_service.apply_for_shop_bot(bot_manager, session, shop_bot)
    admin_settings = await get_admin_settings(session)
    bot_branding_service.mark_checked(shop_bot, bot_branding_service.interval_of(admin_settings) * 60)
    await session.flush()
    text, keyboard = _branding_screen(shop_bot, admin_settings)
    await callback.message.answer(_branding_check_message(outcome))
    await callback.message.edit_text(text, reply_markup=keyboard)


# ------------------------------------------------------------------ پشتیبانیِ مشتری‌ها (D1/D2): حالتِ direct؛ مشتری فقط همین شناسه رو می‌بینه
def _support_screen(shop_bot):
    return texts.shop_support_text(shop_bot), keyboards.shop_support_keyboard(shop_bot)


@router.callback_query(F.data == "sp_open")
async def support_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _support_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "sp_back")
async def support_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = _screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "sp_toggle")
async def support_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    turning_on = not shop_bot.support_enabled
    if turning_on and not (shop_bot.support_contact_username or shop_bot.support_contact_phone):
        await callback.answer(texts.SUPPORT_NEEDS_CONTACT, show_alert=True)
        return
    shop_bot.support_enabled = turning_on
    await session.flush()
    await callback.answer(texts.switch_toast("پشتیبانیِ مستقیم", turning_on))
    text, keyboard = _support_screen(shop_bot)
    await safe_edit(callback, text, keyboard)


_SUPPORT_STATES = {
    "username": ShopSettingsStates.waiting_support_username,
    "phone": ShopSettingsStates.waiting_support_phone,
    "text": ShopSettingsStates.waiting_support_text,
}


@router.callback_query(F.data.startswith("sp_edit:"))
async def support_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    field = callback.data.split(":", 1)[1]
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if field not in _SUPPORT_STATES:
        await callback.answer(texts.SUPPORT_SETTINGS_STALE, show_alert=True)
        return
    await callback.answer()
    await state.set_state(_SUPPORT_STATES[field])
    await callback.message.answer(texts.SUPPORT_ASK[field])


async def _support_value_received(message: Message, session: AsyncSession, state: FSMContext, field: str) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    raw = message.text.strip()
    if raw in texts.SUPPORT_CLEAR_WORDS:
        value = None
    elif field == "username":
        value = normalize_telegram_username(raw)
        if value is None:
            await message.answer(texts.INVALID_SUPPORT_USERNAME)
            return
    elif field == "phone":
        value = to_e164_iran(raw)
        if value is None:
            await message.answer(texts.INVALID_SUPPORT_PHONE)
            return
    else:
        value = raw
    setattr(shop_bot, f"support_contact_{field}", value)
    # B7: ثبتِ هر راهِ تماس ⇒ دکمه‌یِ پشتیبانی برایِ مشتری همیشه هست (قبلاً فروشگاه‌دار باید جداگانه
    # «✅ فعال‌کردن» را می‌زد و چون نمی‌دانست، مشتری هیچ‌وقت دکمه را نمی‌دید).
    shop_bot.support_enabled = bool(shop_bot.support_contact_username or shop_bot.support_contact_phone)
    await session.flush()
    await state.clear()
    await message.answer(texts.ADMIN_SETTING_SAVED)
    text, keyboard = _support_screen(shop_bot)
    await message.answer(text, reply_markup=keyboard)


@router.message(ShopSettingsStates.waiting_support_username, F.text)
async def support_username_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _support_value_received(message, session, state, "username")


@router.message(ShopSettingsStates.waiting_support_phone, F.text)
async def support_phone_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _support_value_received(message, session, state, "phone")


@router.message(ShopSettingsStates.waiting_support_text, F.text)
async def support_text_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await _support_value_received(message, session, state, "text")
