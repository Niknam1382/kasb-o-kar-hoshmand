"""
پنلِ فروشگاه‌دار — «🧩 سوال‌هایِ بی‌جواب» و «📚 پرسش‌وپاسخ‌هایِ تاییدشده» (فازِ ۴-الف/ب).

منطق (ثبتِ خلأ، تجمیع، سقف‌ها، ساختِ پرسش‌وپاسخ) توی app/services/knowledge_service.py ـه؛ اینجا فقط
گفتگو با فروشگاه‌دار. هر callback با get_owned_gap/get_owned_learned مالکیت رو چک می‌کنه (شناسه از
callback_data میاد = قابلِ دستکاری). سوالِ مشتری غیرِ قابلِ اعتماده: همیشه متنِ ساده نشون داده می‌شه.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import parse_suffix_int, require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import KnowledgeStates
from app.database.models import KnowledgeGapStatus, ShopBot
from app.services import knowledge_service
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

router = Router(name="knowledge")


def _collapsed_len(text: str) -> int:
    return len(" ".join((text or "").split()))


# =============================================================================
# ۴-الف: فهرستِ سوال‌هایِ بی‌جواب
# =============================================================================
async def _gaps_payload(session: AsyncSession, shop_bot: ShopBot, page: int):
    page_size = knowledge_service.GAPS_PAGE_SIZE
    gaps, total = await knowledge_service.list_open_gaps(session, shop_bot.id, page, page_size)
    if total > 0 and not gaps and page > 0:
        # صفحه‌یِ آخر بعدِ «نادیده گرفتنِ» آخرین مورد خالی شده؛ برمی‌گردیم به آخرین صفحه‌یِ موجود.
        last_page = max(0, (total + page_size - 1) // page_size - 1)
        gaps, total = await knowledge_service.list_open_gaps(session, shop_bot.id, last_page, page_size)
        page = last_page
    admin_settings = await get_admin_settings(session)
    note = "" if admin_settings.knowledge_gap_enabled else f"\n\n{texts.GAPS_DETECTION_OFF_NOTE}"
    if total == 0:
        return texts.GAPS_EMPTY + note, keyboards.empty_screen_keyboard()
    return texts.gaps_page_text(gaps, total, page, page_size) + note, keyboards.gaps_list_keyboard(gaps, page, total, page_size)


@router.message(F.text == "🧩 سوال‌هایِ بی‌جواب")
async def open_gaps(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, keyboard = await _gaps_payload(session, shop_bot, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("gap_list:"))
async def gaps_page(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    page = parse_suffix_int(callback.data, "gap_list:") or 0
    text, keyboard = await _gaps_payload(session, shop_bot, page)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("gap_dismiss:"))
async def gap_dismiss(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    gap = await knowledge_service.get_owned_gap(session, parse_suffix_int(callback.data, "gap_dismiss:"), shop_bot.id)
    if gap is None:
        await callback.answer(texts.GAP_NOT_FOUND, show_alert=True)
        return
    if not await knowledge_service.dismiss_gap(session, gap):
        await callback.answer(texts.GAP_NOT_OPEN, show_alert=True)
        return
    text, keyboard = await _gaps_payload(session, shop_bot, 0)
    await callback.answer(texts.GAP_DISMISSED)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("gap_answer:"))
async def gap_answer_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    gap = await knowledge_service.get_owned_gap(session, parse_suffix_int(callback.data, "gap_answer:"), shop_bot.id)
    if gap is None:
        await callback.answer(texts.GAP_NOT_FOUND, show_alert=True)
        return
    if gap.status != KnowledgeGapStatus.OPEN:
        await callback.answer(texts.GAP_NOT_OPEN, show_alert=True)
        return
    await state.clear()
    await state.set_state(KnowledgeStates.waiting_gap_answer)
    await state.update_data(gap_id=gap.id)
    await callback.answer()
    await callback.message.answer(texts.gap_answer_prompt(gap.question_text))


@router.message(KnowledgeStates.waiting_gap_answer, F.text)
async def gap_answer_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    answer = (message.text or "").strip()
    if not answer:
        await message.answer(texts.GAP_ANSWER_EMPTY)
        return
    if _collapsed_len(answer) > knowledge_service.LEARNED_ANSWER_MAX_LEN:
        await message.answer(texts.GAP_ANSWER_TOO_LONG)
        return

    data = await state.get_data()
    gap = await knowledge_service.get_owned_gap(session, data.get("gap_id"), shop_bot.id)
    if gap is None or gap.status != KnowledgeGapStatus.OPEN:
        await state.clear()
        await message.answer(texts.GAP_NOT_OPEN)
        return

    await state.update_data(answer=answer)
    await state.set_state(KnowledgeStates.waiting_gap_confirm)
    await message.answer(texts.gap_answer_preview(gap.question_text, answer), reply_markup=keyboards.gap_confirm_keyboard())


@router.callback_query(KnowledgeStates.waiting_gap_confirm, F.data == "gap_save_confirm")
async def gap_save_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    # state.clear() عمداً اولِ کاره (قفلِ دابل‌تپ؛ همون الگویِ cart_checkout_confirm).
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    gap = await knowledge_service.get_owned_gap(session, data.get("gap_id"), shop_bot.id)
    if gap is None:
        await callback.answer(texts.GAP_NOT_FOUND, show_alert=True)
        return
    try:
        await knowledge_service.answer_gap(session, gap, data.get("answer"))
    except knowledge_service.KnowledgeError as exc:
        await callback.answer()
        if exc.code == "limit_reached":
            await safe_edit(callback, texts.LEARNED_LIMIT_REACHED)
        elif exc.code == "gap_not_open":
            await safe_edit(callback, texts.GAP_NOT_OPEN)
        else:
            await safe_edit(callback, texts.GAP_ANSWER_EMPTY)
        return
    await callback.answer()
    await safe_edit(callback, texts.GAP_SAVED)


@router.callback_query(KnowledgeStates.waiting_gap_confirm, F.data == "gap_save_cancel")
async def gap_save_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, texts.GAP_SAVE_CANCELLED)


# =============================================================================
# ۴-ب: پرسش‌وپاسخ‌هایِ تاییدشده
# =============================================================================
async def _learned_list_payload(session: AsyncSession, shop_bot: ShopBot, page: int):
    page_size = knowledge_service.LEARNED_PAGE_SIZE
    items, total = await knowledge_service.list_learned(session, shop_bot.id, page, page_size)
    if total > 0 and not items and page > 0:
        last_page = max(0, (total + page_size - 1) // page_size - 1)
        items, total = await knowledge_service.list_learned(session, shop_bot.id, last_page, page_size)
        page = last_page
    if total == 0:
        # حتی با لیستِ خالی دکمه‌یِ «➕ افزودنِ دستی» باید باشه.
        return texts.LEARNED_EMPTY, keyboards.learned_list_keyboard([], 0, 0, page_size)
    return texts.learned_list_text(total), keyboards.learned_list_keyboard(items, page, total, page_size)


@router.message(F.text == "📚 پرسش‌وپاسخ‌هایِ تاییدشده")
async def open_learned(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, keyboard = await _learned_list_payload(session, shop_bot, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("learned_list:"))
async def learned_page(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    page = parse_suffix_int(callback.data, "learned_list:") or 0
    text, keyboard = await _learned_list_payload(session, shop_bot, page)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


async def _owned_learned_or_alert(callback: CallbackQuery, session: AsyncSession, shop_bot: ShopBot, prefix: str):
    item = await knowledge_service.get_owned_learned(session, parse_suffix_int(callback.data, prefix), shop_bot.id)
    if item is None:
        await callback.answer(texts.GAP_NOT_FOUND, show_alert=True)
    return item


@router.callback_query(F.data.startswith("learned_view:"))
async def learned_view(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    item = await _owned_learned_or_alert(callback, session, shop_bot, "learned_view:")
    if item is None:
        return
    await callback.answer()
    await safe_edit(callback, texts.learned_detail_text(item), keyboards.learned_detail_keyboard(item))


@router.callback_query(F.data.startswith("learned_toggle:"))
async def learned_toggle(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    item = await _owned_learned_or_alert(callback, session, shop_bot, "learned_toggle:")
    if item is None:
        return
    await knowledge_service.set_learned_active(session, item, not item.is_active)
    await callback.answer(texts.LEARNED_TOGGLED_ON if item.is_active else texts.LEARNED_TOGGLED_OFF)
    await safe_edit(callback, texts.learned_detail_text(item), keyboards.learned_detail_keyboard(item))


@router.callback_query(F.data.startswith("learned_delete:"))
async def learned_delete_ask(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    item = await _owned_learned_or_alert(callback, session, shop_bot, "learned_delete:")
    if item is None:
        return
    await callback.answer()
    await safe_edit(callback, texts.LEARNED_DELETE_ASK, keyboards.learned_delete_confirm_keyboard(item.id))


@router.callback_query(F.data.startswith("learned_delete_yes:"))
async def learned_delete_yes(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    item = await _owned_learned_or_alert(callback, session, shop_bot, "learned_delete_yes:")
    if item is None:
        return
    await knowledge_service.delete_learned(session, item)
    text, keyboard = await _learned_list_payload(session, shop_bot, 0)
    await callback.answer(texts.LEARNED_DELETED)
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("learned_edit:"))
async def learned_edit_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    item = await _owned_learned_or_alert(callback, session, shop_bot, "learned_edit:")
    if item is None:
        return
    await state.clear()
    await state.set_state(KnowledgeStates.waiting_edit_answer)
    await state.update_data(learned_id=item.id)
    await callback.answer()
    await callback.message.answer(texts.ASK_LEARNED_NEW_ANSWER)


@router.message(KnowledgeStates.waiting_edit_answer, F.text)
async def learned_edit_received(message: Message, state: FSMContext, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    answer = (message.text or "").strip()
    if not answer:
        await message.answer(texts.GAP_ANSWER_EMPTY)
        return
    if _collapsed_len(answer) > knowledge_service.LEARNED_ANSWER_MAX_LEN:
        await message.answer(texts.GAP_ANSWER_TOO_LONG)
        return
    data = await state.get_data()
    await state.clear()
    item = await knowledge_service.get_owned_learned(session, data.get("learned_id"), shop_bot.id)
    if item is None:
        await message.answer(texts.GAP_NOT_FOUND)
        return
    await knowledge_service.update_learned_answer(session, item, answer)
    await message.answer(texts.LEARNED_ANSWER_UPDATED)
    await message.answer(texts.learned_detail_text(item), reply_markup=keyboards.learned_detail_keyboard(item))


@router.callback_query(F.data == "learned_add")
async def learned_add_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    await state.set_state(KnowledgeStates.waiting_manual_question)
    await callback.answer()
    await callback.message.answer(texts.ASK_MANUAL_QUESTION)


@router.message(KnowledgeStates.waiting_manual_question, F.text)
async def learned_manual_question(message: Message, state: FSMContext) -> None:
    question = (message.text or "").strip()
    if not question:
        await message.answer(texts.MANUAL_QUESTION_EMPTY)
        return
    if _collapsed_len(question) > knowledge_service.LEARNED_QUESTION_MAX_LEN:
        await message.answer(texts.MANUAL_QUESTION_TOO_LONG)
        return
    await state.update_data(question=question)
    await state.set_state(KnowledgeStates.waiting_manual_answer)
    await message.answer(texts.ASK_MANUAL_ANSWER)


@router.message(KnowledgeStates.waiting_manual_answer, F.text)
async def learned_manual_answer(message: Message, state: FSMContext) -> None:
    answer = (message.text or "").strip()
    if not answer:
        await message.answer(texts.GAP_ANSWER_EMPTY)
        return
    if _collapsed_len(answer) > knowledge_service.LEARNED_ANSWER_MAX_LEN:
        await message.answer(texts.GAP_ANSWER_TOO_LONG)
        return
    data = await state.get_data()
    await state.update_data(answer=answer)
    await state.set_state(KnowledgeStates.waiting_manual_confirm)
    await message.answer(
        texts.gap_answer_preview(data.get("question", ""), answer), reply_markup=keyboards.learned_manual_confirm_keyboard()
    )


@router.callback_query(KnowledgeStates.waiting_manual_confirm, F.data == "learned_manual_confirm")
async def learned_manual_confirmed(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    data = await state.get_data()
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    try:
        await knowledge_service.create_learned_answer(session, shop_bot.id, data.get("question"), data.get("answer"))
    except knowledge_service.KnowledgeError as exc:
        await callback.answer()
        await safe_edit(callback, texts.LEARNED_LIMIT_REACHED if exc.code == "limit_reached" else texts.GAP_ANSWER_EMPTY)
        return
    await callback.answer()
    await safe_edit(callback, texts.GAP_SAVED)


@router.callback_query(KnowledgeStates.waiting_manual_confirm, F.data == "learned_manual_cancel")
async def learned_manual_cancelled(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer()
    await safe_edit(callback, texts.GAP_SAVE_CANCELLED)


@router.callback_query(F.data.in_({"gap_save_confirm", "gap_save_cancel", "learned_manual_confirm", "learned_manual_cancel"}))
async def stale_knowledge_button(callback: CallbackQuery) -> None:
    """دکمه‌یِ تاییدِ کهنه (مثلاً بعدِ /cancel یا ری‌استارتِ ربات که FSM رو پاک کرده)."""
    await callback.answer(texts.KNOWLEDGE_STALE_BUTTON, show_alert=True)


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
