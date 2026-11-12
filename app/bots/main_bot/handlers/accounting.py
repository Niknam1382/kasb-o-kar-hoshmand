"""
پنلِ فروشگاه‌دار — «🧮 حسابداری» (فازِ ۴-ه): گزارشِ فقط‌خواندنیِ فروش/تخفیف/کمپین + خروجیِ اکسل.
منطقِ محاسبه توی app/services/accounting_service.py ـه؛ اینجا فقط نمایش. هیچ‌چیز تغییر نمی‌کنه.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import (
    require_sales_mode,
    require_shop_bot,
    require_shop_bot_cb,
    safe_edit,
)
from app.services import accounting_service, excel_export_service

router = Router(name="accounting")


def _period_key(data: str | None, prefix: str) -> str:
    key = (data or "")[len(prefix) :]
    return key if key in accounting_service.PERIOD_KEYS else "today"


@router.message(F.text == "🧮 حسابداری")
async def open_accounting(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    if not await require_sales_mode(message, shop_bot):
        return
    report = await accounting_service.build_report(session, shop_bot.id, "today")
    await message.answer(texts.accounting_report_text(report), reply_markup=keyboards.accounting_keyboard("today"))


@router.callback_query(F.data.startswith("acct:"))
async def accounting_period(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    key = _period_key(callback.data, "acct:")
    report = await accounting_service.build_report(session, shop_bot.id, key)
    await callback.answer()
    await safe_edit(callback, texts.accounting_report_text(report), keyboards.accounting_keyboard(key))


@router.callback_query(F.data.startswith("acct_xlsx:"))
async def accounting_excel(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    key = _period_key(callback.data, "acct_xlsx:")
    report = await accounting_service.build_report(session, shop_bot.id, key)
    content = excel_export_service.build_accounting_workbook(report)
    await callback.answer()
    await callback.message.answer_document(
        BufferedInputFile(content, filename=texts.EXCEL_ACCOUNTING_FILENAME), caption=texts.ACCOUNTING_EXCEL_READY
    )
