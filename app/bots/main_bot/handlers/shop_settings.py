"""
پنلِ فروشگاه‌دار — «⚙️ تنظیماتِ ربات فروشگاه» (فازِ ۶-الف). فعلاً: مدتِ تجمیعِ پیام‌هایِ مشتری (۲ تا ۶۰ ثانیه).
هزینه‌یِ توکن با فروشگاه‌داره، پس تصمیمِ این تنظیم با خودشه (نه ادمینِ پلتفرم). تنظیم‌هایِ بعدی همین‌جا اضافه می‌شن.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import parse_suffix_int, require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import ShopSettingsStates
from app.services import shop_bot_service
from app.utils.validators import normalize_telegram_username, to_e164_iran

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
    await callback.answer()
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
