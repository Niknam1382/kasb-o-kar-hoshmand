"""پ۶۶ · موردِ ۲۴-ب — دو صفحهٔ اختصاصیِ مودِ مشاوره‌ای: «🧮 گزارشِ جلسات» و «🎯 بازگشتِ مخاطب».

چرا این فایل: پ۵۸ فقط *دروازه* گذاشت (مشاوره ⇒ «این بخش فروشگاهی است») ولی صفحه‌ای که جایش را
بگیرد نساخت. اینجا همان دو کار، به زبانِ خودِ مشاوره ساخته می‌شود — بدونِ کلمهٔ «سفارش» و بدونِ
هیچ چیزِ فروشگاهی:

• «🧮 گزارشِ جلسات» از همان `accounting_service` می‌خواند، ولی با `consultation=True` ⇒ فقط
  ردیف‌هایِ `type = consultation`. فروشِ خالص = ارزشِ جلسه‌هایِ تاییدشده، و «پرفروش‌ترین‌ها» و
  «عملکردِ کمپین» نشان داده نمی‌شوند (در این مود معنا ندارند).
• «🎯 بازگشتِ مخاطب» از همان `crm_service` بخش‌بندی می‌گیرد و با همان `CustomerBroadcastStates`
  پیش می‌رود ⇒ هیچ منطقِ ارسالِ دومی اینجا نیست؛ فقط فهرستِ مخاطبانِ آن بخش در FSM می‌نشیند.

هر دو صفحه فقط در مودِ مشاوره باز می‌شوند (`require_consultation_mode_cb`) — همان دروازهٔ معکوسِ
پ۵۸، چون کیبوردِ inlineِ کهنه رویِ پیامِ قبلی می‌ماند و متنِ کال‌بک را می‌شود دست‌کاری کرد.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import (
    require_consultation_mode_cb,
    require_shop_bot_cb,
    safe_edit,
)
from app.bots.main_bot.states import CustomerBroadcastStates
from app.services import accounting_service, crm_service, excel_export_service

logger = logging.getLogger(__name__)

router = Router(name="consult_screens")

# مخاطبانِ هر بخش در FSM می‌مانند (همان قراردادِ CRM)، پس سقف لازم است: ۲۰۰۰ شناسه ≈ ۱۲ کیلوبایت JSON.
AUDIENCE_LIMIT = 2_000
_PERIODS = ("today", "week", "month30", "jmonth")


def _period_key(data: str | None, prefix: str) -> str:
    key = (data or "")[len(prefix) :]
    return key if key in _PERIODS else "today"


async def _report_screen(session: AsyncSession, shop_bot, period_key: str, now=None):
    report = await accounting_service.build_report(session, shop_bot.id, period_key, now, consultation=True)
    return texts.consult_reports_text(report), keyboards.consult_reports_keyboard(period_key)


async def _return_screen(session: AsyncSession, shop_bot):
    stats, truncated = await crm_service.load_stats(session, shop_bot.id, exclude_blocked=True)
    counts = crm_service.segment_counts(stats)
    if not sum(counts.values()):
        return texts.CONSULT_RETURN_EMPTY, keyboards.empty_screen_keyboard()
    return texts.consult_return_text(counts, len(stats), truncated), keyboards.consult_return_keyboard(counts)


@router.callback_query(F.data == "cre_open")
async def reports_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_consultation_mode_cb(callback, shop_bot):
        return
    text, keyboard = await _report_screen(session, shop_bot, "today")
    await callback.answer()
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("crep:"))
async def reports_period(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_consultation_mode_cb(callback, shop_bot):
        return
    text, keyboard = await _report_screen(session, shop_bot, _period_key(callback.data, "crep:"))
    await callback.answer()
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("crep_xlsx:"))
async def reports_excel(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_consultation_mode_cb(callback, shop_bot):
        return
    report = await accounting_service.build_report(
        session, shop_bot.id, _period_key(callback.data, "crep_xlsx:"), consultation=True
    )
    content = excel_export_service.build_accounting_workbook(report, consultation=True)
    await callback.answer()
    await callback.message.answer_document(
        BufferedInputFile(content, filename=texts.EXCEL_ACCOUNTING_FILENAME), caption=texts.ACCOUNTING_EXCEL_READY
    )


@router.callback_query(F.data == "cret_open")
async def return_open(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_consultation_mode_cb(callback, shop_bot):
        return
    text, keyboard = await _return_screen(session, shop_bot)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("cret_seg:"))
async def return_segment(callback: CallbackQuery, state: FSMContext, session: AsyncSession) -> None:
    """فقط «متنِ پیام را بنویس» را شروع می‌کند؛ ارسالِ واقعی کارِ همان جریانِ پیامِ همگانیِ پنل است."""
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    if not await require_consultation_mode_cb(callback, shop_bot):
        return
    segment = (callback.data or "").split(":", 1)[1]
    if segment not in crm_service.SEGMENT_KEYS:
        await callback.answer(texts.CONSULT_RETURN_STALE, show_alert=True)
        return
    stats, _ = await crm_service.load_stats(session, shop_bot.id, exclude_blocked=True)
    members = crm_service.partition(stats)[segment]
    if not members:
        await callback.answer(texts.CONSULT_RETURN_EMPTY, show_alert=True)
        return
    ids = [int(stat.customer_id) for stat in members[:AUDIENCE_LIMIT]]
    await state.clear()
    await state.set_state(CustomerBroadcastStates.waiting_message)
    await state.update_data(broadcast_customer_ids=ids)
    await callback.answer()
    await callback.message.answer(
        texts.consult_return_ask(segment, len(ids)) + ("" if len(members) <= AUDIENCE_LIMIT else f"\n⚠️ فقط {AUDIENCE_LIMIT} نفرِ اول.")
    )
