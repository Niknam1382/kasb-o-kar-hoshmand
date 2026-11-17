"""پ۱۰۹ · «🌐 پنلِ وب» در پنلِ فروشگاه‌دار: صدورِ لینکِ یکبارمصرف و ابطالِ لینک‌هایِ فعال.

چرا این فایل جدا از `panel.py` (که خودش بزرگ است): تنها کارِ اینجا ساختنِ یکِ ردیفِ نشست و
فرستادنِ لینکش به *همین چت* است. نوشتنِ داده از مرورگر در `app/web/panel.py` و
`web_panel_service` انجام می‌شود، پس این دو هندلر هیچ منطقِ کسب‌وکاری را تکرار نمی‌کنند.

دو نکتهٔ ایمنی:
• لینک فقط به چتی می‌رود که خودش احراز شده (`message.from_user.id` — همان شناسه‌ای که ردیفِ نشست با
  آن ساخته می‌شود)؛ هیچ شناسه‌ای از کاربر گرفته نمی‌شود و به کسی جز او داده نمی‌شود.
• پیش ازِ فرستادنِ پیام `commit()` می‌شود (قاعدهٔ ۷). اگر ارسالِ پیام شکست بخورد، ردیفِ لینک
  بی‌استفاده می‌ماند و با مهلتِ ۱۵ دقیقه خودش می‌میرد — برعکسِ ساختنِ لینکی که ردیفش نباشد.
"""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_shop_bot, require_shop_bot_cb, safe_edit
from app.config import settings
from app.services import web_panel_service

logger = logging.getLogger(__name__)

router = Router(name="web_panel")


@router.message(F.text == texts.WEB_PANEL_BUTTON)
async def open_web_panel(message: Message, state: FSMContext, session: AsyncSession) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None or message.from_user is None:
        return
    if not web_panel_service.enabled():
        await message.answer(texts.WEB_PANEL_DISABLED)
        return
    if not (settings.webhook_base_url or "").strip():
        await message.answer(texts.WEB_PANEL_NO_ADDRESS)
        return
    link = await web_panel_service.issue_link(session, message.from_user.id, settings.webhook_base_url)
    if link is None:
        await message.answer(texts.WEB_PANEL_NO_ADDRESS)
        return
    await session.commit()
    await message.answer(
        f"{texts.WEB_PANEL_INTRO.format(texts.WEB_PANEL_MINUTES)}\n\n{texts.WEB_PANEL_LINK_TITLE}\n{link}",
        reply_markup=keyboards.web_panel_keyboard(),
    )


@router.callback_query(StateFilter(None), F.data == "web_panel_revoke")
async def revoke_links(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None or callback.from_user is None:
        return
    count = await web_panel_service.revoke_for_owner(session, callback.from_user.id)
    await session.commit()
    note = texts.WEB_PANEL_REVOKED.format(count) if count else texts.WEB_PANEL_NONE_ACTIVE
    await safe_edit(callback, f"🔐 ابطالِ لینک‌هایِ وب\n\n{note}\n\nفروشگاه: {shop_bot.bot_username or '—'}")
    await callback.answer()
