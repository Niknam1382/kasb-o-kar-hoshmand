"""P18 · B9: گام‌هایِ پیش‌فرضِ چک‌اوت — روشن/خاموش و متنِ پرسش، per-shop.

ورود از «📝 سوال‌هایِ چک‌اوتِ سبد» (همان‌جا که سوالاتِ سفارشی نوشته می‌شوند). پیکربندی در یک ستونِ
متنیِ JSON رویِ `ShopBot` ذخیره می‌شود و `NULL` یعنی «همه‌یِ گام‌ها روشن با متنِ پیش‌فرض» ⇒ فروشگاه‌هایی
که دست نمی‌زنند دقیقاً مثلِ امروز چک‌اوت می‌شوند. قاعده‌یِ ایمنی: آدرس و موبایل هم‌زمان خاموش نمی‌شوند.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import (
    require_sales_mode_cb,
    require_shop_bot,
    require_shop_bot_cb,
    safe_edit,
)
from app.bots.main_bot.states import ShopSettingsStates
from app.services import checkout_config_service

router = Router(name="checkout_steps")


def _screen(shop_bot):
    steps = checkout_config_service.parse(shop_bot.checkout_config)
    return texts.checkout_steps_text(steps), keyboards.checkout_steps_keyboard(steps)


async def _save(session: AsyncSession, shop_bot, steps) -> None:
    shop_bot.checkout_config = checkout_config_service.dump(steps)
    await session.flush()


@router.callback_query(F.data == "cs_open")
async def steps_open(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_sales_mode_cb(callback, shop_bot):
        return
    await callback.answer()
    text, keyboard = _screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data == "cs_back")
async def steps_back(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_sales_mode_cb(callback, shop_bot):
        return
    await callback.answer()
    await safe_edit(
        callback,
        texts.checkout_questions_current(shop_bot) + "\n\n" + texts.ASK_CHECKOUT_QUESTIONS,
        keyboards.checkout_questions_keyboard(),
    )


@router.callback_query(F.data.startswith("cs_toggle:"))
async def step_toggle(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_sales_mode_cb(callback, shop_bot):
        return
    key = (callback.data or "").split(":", 1)[1]
    steps = checkout_config_service.parse(shop_bot.checkout_config)
    if key not in steps:
        await callback.answer(texts.CHECKOUT_STEPS_STALE, show_alert=True)
        return
    updated = checkout_config_service.set_enabled(steps, key, not steps[key].enabled)
    if updated is None:
        await callback.answer(texts.CHECKOUT_STEPS_GUARD, show_alert=True)
        return
    await _save(session, shop_bot, updated)
    await state.clear()
    await callback.answer(texts.CHECKOUT_STEPS_SAVED)
    text, keyboard = _screen(shop_bot)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("cs_ask:"))
async def step_question_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_sales_mode_cb(callback, shop_bot):
        return
    key = (callback.data or "").split(":", 1)[1]
    steps = checkout_config_service.parse(shop_bot.checkout_config)
    if key not in steps:
        await callback.answer(texts.CHECKOUT_STEPS_STALE, show_alert=True)
        return
    await state.clear()
    await state.set_state(ShopSettingsStates.waiting_checkout_step_question)
    await state.update_data(checkout_step_key=key)
    await callback.answer()
    await callback.message.answer(texts.checkout_step_text(steps, key))
    await callback.message.answer(texts.CHECKOUT_STEP_QUESTION_ASK)


@router.message(ShopSettingsStates.waiting_checkout_step_question, F.text)
async def step_question_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    data = await state.get_data()
    key = data.get("checkout_step_key")
    steps = checkout_config_service.parse(shop_bot.checkout_config)
    if key not in steps:
        await state.clear()
        await message.answer(texts.CHECKOUT_STEPS_STALE)
        return
    updated = checkout_config_service.set_question(steps, key, message.text)
    if updated is None:
        await message.answer(texts.CHECKOUT_STEP_QUESTION_TOO_LONG)  # state می‌ماند تا کوتاه‌تر بنویسد
        return
    await _save(session, shop_bot, updated)
    await state.clear()
    await message.answer(texts.CHECKOUT_STEPS_SAVED)
    await message.answer(
        texts.checkout_step_text(updated, key), reply_markup=keyboards.checkout_step_keyboard(key, updated[key].enabled)
    )
