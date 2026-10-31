"""P18 · C2: «💬 گفتگوها و کاربران» — نسخه‌یِ ساده‌یِ پنلِ مشاوره‌ای.

CRMِ فروشگاهی («👥 مشتری‌ها» با بخش‌بندی، یادداشت، برچسب و خلاصه‌یِ AI) مخصوصِ فروشگاه است؛ در مودِ
مشاوره‌ای فقط همین لازم است: چه کسانی پیام داده‌اند، متنِ گفتگو، و بلاک/رفعِ بلاک. بلاک از همان
ستونِ `Customer.is_blocked` و همان میدل‌ورِ رباتِ فروشگاه (B4) استفاده می‌کند ⇒ یک رفتار در هر دو مود.

هر callback با `crm_service.get_owned_customer` مالکیت را چک می‌کند (شناسه از callback_data می‌آید).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import require_shop_bot, require_shop_bot_cb, safe_edit
from app.database.models import AuditEventType, TenantMode
from app.services import audit_log_service, conversation_service, crm_service, customer_service

router = Router(name="consult_contacts")


def _parse_card_callback(data: str | None) -> tuple[int, int] | None:
    """«cc_card:12:1» → (12, 1)؛ هر چیزِ نامعتبر → None."""
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != "cc_card" or not parts[1].isdecimal() or not parts[2].isdecimal():
        return None
    return int(parts[1]), int(parts[2])


async def _list_screen(session: AsyncSession, shop_bot, page: int):
    members, page, total_pages, total = await customer_service.list_recent_paged(
        session, shop_bot.id, page, texts.CONSULT_CONTACTS_PAGE_SIZE
    )
    if not members:
        return texts.CONSULT_CONTACTS_EMPTY, None
    return (
        texts.consult_contacts_text(members, total, page, total_pages),
        keyboards.consult_contacts_keyboard(members, page, total_pages),
    )


async def _contact_screen(session: AsyncSession, shop_bot, customer_id: int, page: int):
    """None ⇒ مخاطب پیدا نشد یا گفتگویی ندارد (فروشگاهِ دیگر هرگز نمایش داده نمی‌شود)."""
    customer = await crm_service.get_owned_customer(session, customer_id, shop_bot.id)
    if customer is None:
        return None
    messages, page, total_pages, total = await conversation_service.get_history_page(
        session, customer.id, page, conversation_service.CONVERSATION_PAGE_SIZE
    )
    status = "🚫 بلاک است" if customer.is_blocked else "✅ فعال"
    if not total:
        body = texts.CRM_CONVERSATION_EMPTY
    else:
        body = texts.crm_conversation_text(texts.crm_customer_label(customer), messages, page, total_pages, total)
    text = f"{status}\n\n{body}"
    return text, keyboards.consult_contact_keyboard(customer.id, customer.is_blocked, page, total_pages)


@router.message(F.text == texts.CONSULT_CONTACTS_BUTTON)
async def open_contacts(message: Message, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    if shop_bot.tenant_mode != TenantMode.CONSULTATION:
        # C2: این صفحه مخصوصِ مشاوره است؛ در فروشگاهی همان داده‌ها در «👥 مشتری‌ها» هست.
        await message.answer(texts.CONSULT_CONTACTS_SALES_HINT)
        return
    text, keyboard = await _list_screen(session, shop_bot, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.startswith("cc_list:"))
async def contacts_list(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    raw = (callback.data or "").split(":", 1)[1]
    page = int(raw) if raw.isdecimal() else 0
    text, keyboard = await _list_screen(session, shop_bot, page)
    await callback.answer()
    await safe_edit(callback, text, keyboard)


@router.callback_query(F.data.startswith("cc_card:"))
async def contact_card(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    await state.clear()
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    parsed = _parse_card_callback(callback.data)
    if parsed is None:
        await callback.answer(texts.CONSULT_CONTACTS_STALE, show_alert=True)
        return
    screen = await _contact_screen(session, shop_bot, parsed[0], parsed[1])
    if screen is None:
        await callback.answer(texts.CONSULT_CONTACTS_STALE, show_alert=True)
        return
    await callback.answer()
    await safe_edit(callback, screen[0], screen[1])


async def _set_blocked(callback: CallbackQuery, session: AsyncSession, prefix: str, blocked: bool) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    raw = (callback.data or "").split(":", 1)[1]
    customer_id = int(raw) if raw.isdecimal() else None
    customer = await crm_service.get_owned_customer(session, customer_id, shop_bot.id)
    if customer is None:
        await callback.answer(texts.CONSULT_CONTACTS_STALE, show_alert=True)
        return
    # دو کالبکِ جدا ⇒ دابل‌تپ وضعیت را برنمی‌گرداند (B4).
    await crm_service.set_blocked(session, customer, blocked)
    await audit_log_service.log(
        session,
        AuditEventType.CUSTOMER_BLOCK_CHANGED,
        shop_bot_id=shop_bot.id,
        actor_telegram_id=callback.from_user.id,
        details=f"customer={customer.id} blocked={blocked}",
    )
    screen = await _contact_screen(session, shop_bot, customer.id, 0)
    await callback.answer(texts.CONSULT_BLOCK_DONE if blocked else texts.CONSULT_UNBLOCK_DONE)
    if screen is not None:
        await safe_edit(callback, screen[0], screen[1])


@router.callback_query(F.data.startswith("cc_block:"))
async def block_contact(callback: CallbackQuery, session: AsyncSession) -> None:
    await _set_blocked(callback, session, "cc_block:", True)


@router.callback_query(F.data.startswith("cc_unblock:"))
async def unblock_contact(callback: CallbackQuery, session: AsyncSession) -> None:
    await _set_blocked(callback, session, "cc_unblock:", False)
