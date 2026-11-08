"""
پنلِ فروشگاه‌دار — «💬 دستیارِ مدیریتی» (فازِ ۴-د). فقط‌خواندنی: AI فقط یه خلاصه‌یِ آماریِ از پیش‌محاسبه‌شده
برایِ فروشگاهِ *همین* فروشگاه‌دار می‌بینه (owner_assistant_service.build_digest) و هیچ ابزاری نداره.

هزینه: از کیف‌پول (OWNER_ASSISTANT)، چکِ موجودی قبل از AI، کسر فقط بعدِ موفقیت؛ محدودیتِ نرخِ جدا.
ورود/خروج: «💬 دستیارِ مدیریتی» / «🔚 پایان» / /cancel؛ دکمه‌هایِ دیگه‌یِ منو از گفتگو خارج می‌کنن (بندِ ۴۱).
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_shop_bot, panel_keyboard
from app.bots.main_bot.states import AssistantStates
from app.database.models import WalletTransactionReason
from app.services import (
    ai_billing,
    ai_pool_service,
    ai_service,
    owner_assistant_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

router = Router(name="assistant")


@router.message(F.text == "💬 دستیارِ مدیریتی")
async def open_assistant(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    admin_settings = await get_admin_settings(session)
    estimate = wallet_service.estimate_owner_assistant_cost(admin_settings, wallet_service.OWNER_ASSISTANT_TYPICAL_TOKENS)
    await state.set_state(AssistantStates.active)
    await state.update_data(assistant_history=[])
    await message.answer(texts.assistant_intro(estimate), reply_markup=keyboards.assistant_keyboard())


@router.message(AssistantStates.active, F.text == texts.ASSISTANT_END_BUTTON)
async def end_assistant(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    tenant_mode = shop_bot.tenant_mode if shop_bot else None
    await message.answer(texts.ASSISTANT_END_TEXT, reply_markup=await panel_keyboard(session, tenant_mode))


@router.message(AssistantStates.active, F.text)
async def assistant_question(message: Message, session: AsyncSession, state: FSMContext) -> None:
    question = (message.text or "").strip()
    if not question:
        return
    if len(question) > owner_assistant_service.QUESTION_MAX_CHARS:
        await message.answer(texts.ASSISTANT_TOO_LONG)
        return

    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    admin_settings = await get_admin_settings(session)

    # چک‌ها (بدونِ هزینه): نرخ ← موجودی ← کلیدِ AI
    if not ai_billing.allow_request(ai_billing.KIND_ASSISTANT, shop_bot.id, message.from_user.id):
        await message.answer(texts.ASSISTANT_RATE_LIMITED)
        return
    estimate = wallet_service.estimate_owner_assistant_cost(admin_settings, wallet_service.OWNER_ASSISTANT_TYPICAL_TOKENS)
    if not ai_billing.has_funds(owner, estimate):
        await message.answer(texts.ASSISTANT_NO_FUNDS)
        return
    ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
    if ai is None:
        await message.answer(texts.GENERIC_ERROR)
        return

    digest = await owner_assistant_service.build_digest(session, shop_bot, owner)
    system_prompt = owner_assistant_service.build_system_prompt(digest)
    data = await state.get_data()
    history = owner_assistant_service.trim_history(data.get("assistant_history"))

    try:
        await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
        ai_result = await ai.get_reply(system_prompt, history, question)
    except ai_service.AiServiceError:
        logger.exception("فراخوانیِ هوش مصنوعی برایِ دستیارِ مدیریتی ناموفق بود.")
        await message.answer(texts.GENERIC_ERROR)
        return

    reply = owner_assistant_service.clamp_reply(ai_result.text)
    if not reply:
        await message.answer(texts.ASSISTANT_EMPTY_REPLY)
        return

    cost = wallet_service.estimate_owner_assistant_cost(admin_settings, ai_result.total_tokens)
    await ai_billing.charge_owner(session, owner, admin_settings, cost, WalletTransactionReason.OWNER_ASSISTANT, message.bot)

    history.extend([{"role": "user", "content": question}, {"role": "assistant", "content": reply}])
    await state.update_data(assistant_history=owner_assistant_service.trim_history(history))
    await message.answer(reply)
