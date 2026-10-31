"""
پنلِ فروشگاه‌دار — «👥 مشتری‌ها» (فازِ ۴-ج): بخش‌بندیِ قاعده‌محور، کارتِ مشتری، یادداشت/برچسب،
«📣 پیام به این بخش» (با زیرساختِ پیامِ همگانیِ موجود) و «🧠 خلاصه‌یِ هوشمند» (AI، فقط با تایید و هزینه‌یِ نمایش‌داده‌شده).

منطقِ بخش‌بندی/اعتبارسنجی توی app/services/crm_service.py ـه. هر callback با get_owned_customer مالکیت رو
چک می‌کنه (شناسه از callback_data میاد = قابلِ دستکاری). نامِ مشتری متنِ کاربره: همیشه متنِ ساده.
"""
from __future__ import annotations

import datetime
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import parse_suffix_int, require_shop_bot, require_shop_bot_cb, safe_edit
from app.bots.main_bot.states import CrmStates, CustomerBroadcastStates
from app.database.models import ShopBot, WalletTransactionReason
from app.services import (
    ai_billing,
    ai_pool_service,
    ai_service,
    conversation_service,
    crm_service,
    crm_summary_service,
    shop_owner_service,
    wallet_service,
)
from app.services.admin_settings_service import get_admin_settings

logger = logging.getLogger(__name__)

router = Router(name="crm")

# جلوگیریِ دابل‌تپ روی «بساز»: هم‌زمان فقط یه خلاصه به‌ازایِ هر (فروشگاه، مشتری) (درون‌پردازه‌ای).
_summary_inflight: set[tuple[int, int]] = set()


# =============================================================================
# نما و بخش‌ها
# =============================================================================
async def _overview_payload(session: AsyncSession, shop_bot: ShopBot):
    stats, truncated = await crm_service.load_stats(session, shop_bot.id)
    if not stats:
        return texts.CRM_EMPTY, None
    counts = crm_service.segment_counts(stats)
    return texts.crm_overview_text(counts, len(stats), truncated), keyboards.crm_overview_keyboard(counts)


@router.message(F.text == "👥 مشتری‌ها")
async def open_crm(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, keyboard = await _overview_payload(session, shop_bot)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "crm_home")
async def crm_home(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    text, keyboard = await _overview_payload(session, shop_bot)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


def _parse_segment_callback(data: str | None) -> tuple[str, int] | None:
    """«crm_seg:loyal:2» → ('loyal', 2)؛ هر چیزِ نامعتبر → None."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "crm_seg" or parts[1] not in crm_service.SEGMENT_KEYS or not parts[2].isdecimal():
        return None
    return parts[1], int(parts[2])


@router.callback_query(F.data.startswith("crm_seg:"))
async def crm_segment(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parsed = _parse_segment_callback(callback.data)
    if parsed is None:
        await callback.answer(texts.CRM_STALE_BUTTON, show_alert=True)
        return
    segment_key, page = parsed
    stats, _ = await crm_service.load_stats(session, shop_bot.id)
    members = crm_service.partition(stats)[segment_key]
    if not members:
        text, keyboard = await _overview_payload(session, shop_bot)
        await callback.answer(texts.CRM_SEGMENT_EMPTY, show_alert=True)
        await safe_edit(callback, text, keyboard)
        return
    page_members, page, total_pages = crm_service.paginate(members, page)
    await callback.answer()
    await safe_edit(
        callback,
        texts.crm_segment_text(segment_key, page_members, len(members), page, total_pages, crm_service.PAGE_SIZE),
        keyboards.crm_segment_keyboard(segment_key, page_members, page, total_pages, crm_service.PAGE_SIZE),
    )


# =============================================================================
# کارتِ مشتری
# =============================================================================
async def _card_payload(session: AsyncSession, shop_bot: ShopBot, customer_id: int | None):
    customer = await crm_service.get_owned_customer(session, customer_id, shop_bot.id)
    if customer is None:
        return None
    stats, _ = await crm_service.load_stats(session, shop_bot.id, customer_id=customer.id)
    if not stats:
        return None
    orders = await crm_service.recent_orders(session, shop_bot.id, customer.id)
    return texts.crm_card_text(stats[0], customer, orders), keyboards.crm_card_keyboard(customer.id, stats[0].segment)


@router.callback_query(F.data.startswith("crm_card:"))
async def crm_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await state.clear()
    payload = await _card_payload(session, shop_bot, parse_suffix_int(callback.data, "crm_card:"))
    if payload is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, payload[0], payload[1])


# =============================================================================
# یادداشت و برچسب
# =============================================================================
@router.callback_query(F.data.startswith("crm_note:"))
async def crm_note_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_note:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    await state.clear()
    await state.set_state(CrmStates.waiting_note)
    await state.update_data(crm_customer_id=customer.id)
    await callback.answer()
    await callback.message.answer(texts.CRM_NOTE_ASK, reply_markup=keyboards.crm_clear_keyboard("note", customer.id))


@router.message(CrmStates.waiting_note, F.text)
async def crm_note_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    data = await state.get_data()
    customer = await crm_service.get_owned_customer(session, data.get("crm_customer_id"), shop_bot.id)
    if customer is None:
        await state.clear()
        await message.answer(texts.CRM_NOT_FOUND)
        return
    try:
        note = await crm_service.set_notes(session, customer, message.text)
    except crm_service.CrmError:
        await message.answer(texts.CRM_NOTE_TOO_LONG)
        return
    await state.clear()
    await message.answer(texts.CRM_NOTE_SAVED if note else texts.CRM_NOTE_CLEARED)
    payload = await _card_payload(session, shop_bot, customer.id)
    if payload is not None:
        await message.answer(payload[0], reply_markup=payload[1])


@router.callback_query(F.data.startswith("crm_note_clear:"))
async def crm_note_clear(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_note_clear:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    await state.clear()
    await crm_service.set_notes(session, customer, None)
    await callback.answer(texts.CRM_NOTE_CLEARED)
    payload = await _card_payload(session, shop_bot, customer.id)
    if payload is not None:
        await callback.message.answer(payload[0], reply_markup=payload[1])


@router.callback_query(F.data.startswith("crm_tags:"))
async def crm_tags_start(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_tags:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    await state.clear()
    await state.set_state(CrmStates.waiting_tags)
    await state.update_data(crm_customer_id=customer.id)
    await callback.answer()
    await callback.message.answer(texts.CRM_TAGS_ASK, reply_markup=keyboards.crm_clear_keyboard("tags", customer.id))


@router.message(CrmStates.waiting_tags, F.text)
async def crm_tags_received(message: Message, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        await state.clear()
        return
    data = await state.get_data()
    customer = await crm_service.get_owned_customer(session, data.get("crm_customer_id"), shop_bot.id)
    if customer is None:
        await state.clear()
        await message.answer(texts.CRM_NOT_FOUND)
        return
    try:
        tags = await crm_service.set_tags(session, customer, message.text)
    except crm_service.CrmError as exc:
        await message.answer(texts.CRM_TAG_TOO_LONG if exc.code == "tag_too_long" else texts.CRM_TOO_MANY_TAGS)
        return
    await state.clear()
    await message.answer(texts.CRM_TAGS_SAVED if tags else texts.CRM_TAGS_CLEARED)
    payload = await _card_payload(session, shop_bot, customer.id)
    if payload is not None:
        await message.answer(payload[0], reply_markup=payload[1])


@router.callback_query(F.data.startswith("crm_tags_clear:"))
async def crm_tags_clear(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_tags_clear:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    await state.clear()
    await crm_service.set_tags(session, customer, None)
    await callback.answer(texts.CRM_TAGS_CLEARED)
    payload = await _card_payload(session, shop_bot, customer.id)
    if payload is not None:
        await callback.message.answer(payload[0], reply_markup=payload[1])


# =============================================================================
# پیام به یه بخش (زیرساختِ پیامِ همگانیِ موجود؛ بدونِ هزینه)
# =============================================================================
@router.callback_query(F.data.startswith("crm_bcast:"))
async def crm_segment_broadcast(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    segment_key = (callback.data or "")[len("crm_bcast:") :]
    if segment_key not in crm_service.SEGMENT_KEYS:
        await callback.answer(texts.CRM_STALE_BUTTON, show_alert=True)
        return
    stats, _ = await crm_service.load_stats(session, shop_bot.id)
    members = crm_service.partition(stats)[segment_key]
    if not members:
        await callback.answer(texts.CRM_BROADCAST_EMPTY, show_alert=True)
        return
    await state.clear()
    await state.set_state(CustomerBroadcastStates.waiting_message)
    await state.update_data(broadcast_customer_ids=[stat.telegram_id for stat in members])
    await callback.answer()
    await callback.message.answer(texts.crm_broadcast_ask(texts.CRM_SEGMENT_LABELS[segment_key], len(members)))


# =============================================================================
# خلاصه‌یِ هوشمندِ مشتری (AI + کیف‌پول)
# =============================================================================
@router.callback_query(F.data.startswith("crm_sum:"))
async def crm_summary_confirm(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_sum:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    admin_settings = await get_admin_settings(session)
    estimate = wallet_service.estimate_crm_summary_cost(admin_settings, wallet_service.CRM_SUMMARY_TYPICAL_TOKENS)
    await callback.answer()
    await safe_edit(callback, texts.crm_summary_confirm_text(estimate), keyboards.crm_summary_confirm_keyboard(customer.id))


@router.callback_query(F.data.startswith("crm_sum_go:"))
async def crm_summary_run(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    customer = await crm_service.get_owned_customer(session, parse_suffix_int(callback.data, "crm_sum_go:"), shop_bot.id)
    if customer is None:
        await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
        return
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    admin_settings = await get_admin_settings(session)
    estimate = wallet_service.estimate_crm_summary_cost(admin_settings, wallet_service.CRM_SUMMARY_TYPICAL_TOKENS)
    back = keyboards.crm_back_to_card_keyboard(customer.id)

    # ترتیبِ چک‌ها: موجودی ← محدودیتِ نرخ ← هم‌زمانی ← پیش‌نیازها؛ هیچ‌کدوم هزینه‌ای ندارن.
    if not ai_billing.has_funds(owner, estimate):
        await callback.answer(texts.CRM_SUMMARY_NO_FUNDS, show_alert=True)
        return
    if not ai_billing.allow_request(ai_billing.KIND_CRM_SUMMARY, shop_bot.id, callback.from_user.id):
        await callback.answer(texts.CRM_SUMMARY_RATE_LIMITED, show_alert=True)
        return
    inflight_key = (shop_bot.id, customer.id)
    if inflight_key in _summary_inflight:
        await callback.answer(texts.CRM_SUMMARY_BUSY, show_alert=True)
        return

    _summary_inflight.add(inflight_key)
    try:
        messages = await conversation_service.get_recent_history(session, customer.id, crm_summary_service.SUMMARY_MESSAGE_LIMIT)
        if not messages:
            await callback.answer()
            await safe_edit(callback, texts.CRM_SUMMARY_NO_CONVERSATION, back)
            return
        ai = await ai_pool_service.build_ai_service(session, admin_settings, "chat")
        if ai is None:
            await callback.answer(texts.GENERIC_ERROR, show_alert=True)
            return
        stats, _ = await crm_service.load_stats(session, shop_bot.id, customer_id=customer.id)
        if not stats:
            await callback.answer(texts.CRM_NOT_FOUND, show_alert=True)
            return
        stat = stats[0]
        days_since = None
        if stat.last_activity is not None:
            days_since = max(0, (datetime.datetime.now(datetime.timezone.utc) - stat.last_activity).days)
        user_message = crm_summary_service.build_user_message(
            texts.CRM_SEGMENT_LABELS.get(stat.segment, stat.segment), stat.success_count, stat.net_toman, days_since, messages
        )

        await callback.answer()
        await safe_edit(callback, texts.CRM_SUMMARY_WORKING)
        try:
            await session.commit()  # آزاد کردنِ اتصالِ دیتابیس قبل از انتظارِ AI (ظرفیت؛ فازِ ۶-الف)
            ai_result = await crm_summary_service.generate_summary(ai, user_message)
        except ai_service.AiServiceError:
            logger.exception("فراخوانیِ هوش مصنوعی برایِ خلاصه‌یِ CRM ناموفق بود.")
            await safe_edit(callback, texts.GENERIC_ERROR, back)
            return

        summary = crm_summary_service.clamp_reply(ai_result.text)
        if not summary:
            await safe_edit(callback, texts.CRM_SUMMARY_EMPTY_REPLY, back)
            return

        cost = wallet_service.estimate_crm_summary_cost(admin_settings, ai_result.total_tokens)
        await ai_billing.charge_owner(session, owner, admin_settings, cost, WalletTransactionReason.CRM_SUMMARY, callback.bot)
        await safe_edit(callback, texts.crm_summary_result(summary, cost), back)
    finally:
        _summary_inflight.discard(inflight_key)
