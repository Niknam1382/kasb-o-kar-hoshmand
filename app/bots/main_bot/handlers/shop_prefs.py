"""P18 · A5: مهلت‌ها و حافظه‌یِ per-shop — هندلرهایِ «⚙️ تنظیماتِ ربات فروشگاه › ⏱ مهلت‌ها و حافظه».

این پنج تنظیم پیش‌تر در پنلِ ادمینِ پلتفرم بودند و ادمین برایِ همه تصمیم می‌گرفت؛ حالا ستونِ
per-shop رویِ خودِ `ShopBot` است و `NULL` یعنی «پیش‌فرضِ سراسری». مودِ مشاوره‌ای فقط آنچه معنا دارد
را می‌بیند (پاکسازیِ مکالمه و حافظه‌یِ کانالِ دانش) — نه سفارش و پرداخت.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import ShopSettingsStates
from app.database.models import TenantMode
from app.services import shop_bot_service, shop_prefs_service
from app.services.admin_settings_service import get_admin_settings

router = Router(name="shop_prefs")


def _prefs(shop_bot) -> tuple:
    return shop_prefs_service.prefs_for(shop_bot.tenant_mode == TenantMode.CONSULTATION)


def _pref_and_value(data: str | None, prefix: str) -> tuple[object | None, str]:
    """«sp_pref_set:order_reservation_minutes:45» با پیشوندِ «sp_pref_set:» ⇒ (pref, "45")."""
    raw = data or ""
    if not raw.startswith(prefix):
        return None, ""
    parts = raw[len(prefix) :].split(":", 1)
    return shop_prefs_service.BY_KEY.get(parts[0]), (parts[1] if len(parts) == 2 else "")


async def _menu(shop_bot, session: AsyncSession):
    admin_settings = await get_admin_settings(session)
    return texts.shop_prefs_text(shop_bot, admin_settings, _prefs(shop_bot)), keyboards.shop_prefs_menu_keyboard(
        shop_bot, admin_settings, _prefs(shop_bot)
    )


@router.callback_query(F.data == "sp_prefs_open")
async def prefs_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = await _menu(shop_bot, session)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "sp_prefs_back")
async def prefs_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    await safe_edit(
        callback,
        texts.shop_settings_text(shop_bot, shop_bot_service.DEFAULT_MESSAGE_BATCH_SECONDS),
        keyboards.shop_settings_keyboard(shop_bot),
    )


@router.callback_query(F.data.startswith("sp_pref:"))
async def pref_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    pref = shop_prefs_service.BY_KEY.get((callback.data or "").split(":", 1)[1])
    if pref is None or pref not in _prefs(shop_bot):
        await callback.answer(texts.SHOP_PREFS_STALE, show_alert=True)
        return
    admin_settings = await get_admin_settings(session)
    await callback.answer()
    await safe_edit(
        callback,
        texts.shop_pref_text(shop_bot, admin_settings, pref),
        keyboards.shop_pref_edit_keyboard(shop_bot, pref),
    )


@router.callback_query(F.data.startswith("sp_pref_set:"))
async def pref_set(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    pref, raw = _pref_and_value(callback.data, "sp_pref_set:")
    if pref is None or pref not in _prefs(shop_bot) or not raw.isdecimal():
        await callback.answer(texts.SHOP_PREFS_STALE, show_alert=True)
        return
    try:
        await shop_prefs_service.set_value(session, shop_bot, pref, int(raw))
    except ValueError:
        await callback.answer(texts.SHOP_PREFS_STALE, show_alert=True)
        return
    await state.clear()
    await callback.answer(texts.SHOP_PREF_SAVED)
    admin_settings = await get_admin_settings(session)
    await safe_edit(
        callback,
        texts.shop_pref_text(shop_bot, admin_settings, pref),
        keyboards.shop_pref_edit_keyboard(shop_bot, pref),
    )


@router.callback_query(F.data.startswith("sp_pref_reset:"))
async def pref_reset(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    pref = shop_prefs_service.BY_KEY.get((callback.data or "").split(":", 1)[1])
    if pref is None or pref not in _prefs(shop_bot):
        await callback.answer(texts.SHOP_PREFS_STALE, show_alert=True)
        return
    await shop_prefs_service.set_value(session, shop_bot, pref, None)
    await state.clear()
    await callback.answer(texts.SHOP_PREF_RESET_DONE)
    admin_settings = await get_admin_settings(session)
    await safe_edit(
        callback,
        texts.shop_pref_text(shop_bot, admin_settings, pref),
        keyboards.shop_pref_edit_keyboard(shop_bot, pref),
    )


@router.callback_query(F.data == "sp_pref_back")
async def pref_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, keyboard = await _menu(shop_bot, session)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("sp_pref_custom:"))
async def pref_custom_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    pref = shop_prefs_service.BY_KEY.get((callback.data or "").split(":", 1)[1])
    if pref is None or pref not in _prefs(shop_bot):
        await callback.answer(texts.SHOP_PREFS_STALE, show_alert=True)
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_pref_value)
    await state.update_data(pref_key=pref.key)
    await callback.answer()
    await callback.message.answer(texts.shop_pref_ask(pref))


@router.message(ShopSettingsStates.waiting_pref_value, F.text)
async def pref_custom_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    data = await state.get_data()
    pref = shop_prefs_service.BY_KEY.get(data.get("pref_key"))
    if pref is None or pref not in _prefs(shop_bot):
        await state.clear()
        await message.answer(texts.SHOP_PREFS_STALE)
        return
    value = shop_prefs_service.parse_value(pref, message.text)
    if value is None:
        await message.answer(texts.shop_pref_invalid(pref))  # state می‌ماند تا دوباره بنویسد
        return
    await shop_prefs_service.set_value(session, shop_bot, pref, value)
    await state.clear()
    await message.answer(texts.SHOP_PREF_SAVED)
    admin_settings = await get_admin_settings(session)
    await message.answer(
        texts.shop_pref_text(shop_bot, admin_settings, pref), reply_markup=keyboards.shop_pref_edit_keyboard(shop_bot, pref)
    )
