"""P43 · مواردِ ۳۰/۳۱/۱۰ — صفحه‌هایِ گزارشِ نگهبانِ محتوا.

«🛡 نگهبانِ محتوا» در *هر دو* پنل (فروشگاهی و مشاوره‌ای) فهرستِ گزارش‌هایِ باز را می‌دهد و هر
گزارش یکِ کارت دارد با سه فعل:

• «👁 گفتگو» و «👤 مشخصاتِ کاربر» ⇒ همان صفحه‌هایِ موجود (در مودِ فروشگاهی `crm_conv/crm_card`،
  در مودِ مشاوره‌ای `cc_card`). کیبوردِ تازه‌ای برایِ دیدنِ چت نساختیم: همان صفحه خواسته‌شده از
  قبل وجود دارد و دو راهِ جدا برایِ دیدنِ یکِ گفتگو یعنی دو جا باگ.
• «🚫 بلاک / ✅ رفعِ بلاک» ⇒ همان `Customer.is_blocked` و همان میدل‌ورِ رباتِ فروشگاه (موردِ ۳۱).
• «✅ بررسی شد» ⇒ گزارش بسته می‌شود و در ممیزی ثبت می‌گردد؛ هیچ پیامی پاک نمی‌شود.

همه‌ی شناسه‌ها از `callback_data` می‌آیند، پس هر مسیر اول `report.shop_bot_id == shop_bot.id` را
چک می‌کند. ادمینِ پلتفرم فهرستِ همهٔ فروشگاه‌ها را می‌بیند (`mod_admin_list`) و رویِ کارتِ او
دکمهٔ گفتگو/مشخصات نیست: دیدنِ چتِ مشتریِ یکِ فروشگاه برایِ ادمین، جدا ازِ گزارشِ خودش نیازمندِ
صفحهٔ تازه + ممیزی است و در صفِ بعد نشسته است.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts
from app.bots.main_bot.handlers.owner_common import (
    parse_suffix_int,
    require_shop_bot,
    require_shop_bot_cb,
    safe_edit,
)
from app.config import settings
from app.database.models import AuditEventType, Customer, ModerationReport, ShopBot, TenantMode
from app.services import admin_role_service, audit_log_service, crm_service, moderation_service

router = Router(name="moderation_reports")

LIST_PAGE_SIZE = 8


def _page_of(data: str | None, part: int = 1) -> int:
    bits = (data or "").split(":")
    if len(bits) > part and bits[part].isdecimal():
        return int(bits[part])
    return 0


def _deep_links(shop_bot, customer_id: int | None) -> tuple[str | None, str | None]:
    """(گفتگو، مشخصات) به مودِ همان کسب‌وکار؛ بی‌مشتری هیچ‌کدام ساخته نمی‌شود."""
    if customer_id is None:
        return None, None
    if shop_bot is not None and shop_bot.tenant_mode == TenantMode.CONSULTATION:
        return f"cc_card:{customer_id}:0", f"cc_card:{customer_id}:0"
    return f"crm_conv:{customer_id}:0", f"crm_card:{customer_id}"


async def _is_platform_admin(session: AsyncSession, telegram_id: int) -> bool:
    return telegram_id in settings.admin_ids or await admin_role_service.is_operator(session, telegram_id)


async def _screen(session: AsyncSession, shop_bot_ids: list[int] | None, page: int) -> tuple[str, object]:
    offset = max(page, 0) * LIST_PAGE_SIZE
    reports = await moderation_service.list_reports(session, shop_bot_ids, limit=LIST_PAGE_SIZE, offset=offset)
    total = await moderation_service.count_reports(session, shop_bot_ids)
    total_pages = max(1, -(-total // LIST_PAGE_SIZE))
    if not reports:
        return texts.MODERATION_REPORTS_EMPTY, keyboards.empty_screen_keyboard()
    return (
        texts.moderation_reports_list_text(reports, page=page, total_pages=total_pages, total=total),
        keyboards.moderation_reports_list_keyboard(reports, page, total_pages),
    )


async def _owned_report(session: AsyncSession, shop_bot, report_id: int | None) -> ModerationReport | None:
    if report_id is None:
        return None
    report = await moderation_service.get_report(session, report_id)
    if report is None or report.shop_bot_id != shop_bot.id:
        return None
    return report


async def _customer(session: AsyncSession, report: ModerationReport) -> Customer | None:
    if report.customer_id is None:
        return None
    return await session.get(Customer, report.customer_id)


async def _card(
    report: ModerationReport,
    customer: Customer | None,
    shop_bot,
    *,
    shop_line: str | None = None,
    back: str = "mod_list:0",
    with_links: bool = True,
):
    chat_cb, profile_cb = _deep_links(shop_bot, report.customer_id) if with_links else (None, None)
    return (
        texts.moderation_report_card(report, texts.crm_customer_label(customer) if customer else "—", shop_line=shop_line),
        keyboards.moderation_report_keyboard(
            report.id, blocked=bool(customer and customer.is_blocked), chat_cb=chat_cb, profile_cb=profile_cb, back_cb=back
        ),
    )


# ============================================================================= ۱) پنلِ فروشگاه‌دار
@router.message(F.text == texts.MODERATION_GUARD_BUTTON)
@router.message(Command("moderation"))
async def open_guard(message: Message, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot(message, session)
    if shop_bot is None:
        return
    text, markup = await _screen(session, [shop_bot.id], 0)
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("mod_list:"))
async def cb_guard_list(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    await callback.answer()
    text, markup = await _screen(session, [shop_bot.id], _page_of(callback.data))
    await safe_edit(callback, text, markup)


@router.callback_query(F.data.startswith("mod_open:"))
async def cb_report_open(callback: CallbackQuery, session: AsyncSession) -> None:
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    report = await _owned_report(session, shop_bot, parse_suffix_int(callback.data, "mod_open:"))
    if report is None:
        await callback.answer(texts.MODERATION_REPORT_NOT_FOUND, show_alert=True)
        return
    await callback.answer()
    text, markup = await _card(report, await _customer(session, report), shop_bot)
    await safe_edit(callback, text, markup)


@router.callback_query(F.data.startswith(("mod_block:", "mod_unblock:")))
async def cb_report_block(callback: CallbackQuery, session: AsyncSession) -> None:
    """موردِ ۳۱: «مسدود» همان ستونی است که میدل‌ورِ رباتِ فروشگاه جلوِ مشتری را می‌گیرد."""
    shop_bot = await require_shop_bot_cb(callback, session)
    if shop_bot is None:
        return
    want_block = callback.data.startswith("mod_block:")
    report = await _owned_report(
        session, shop_bot, parse_suffix_int(callback.data, "mod_block:" if want_block else "mod_unblock:")
    )
    customer = None if report is None else await _customer(session, report)
    if report is None or customer is None:
        await callback.answer(texts.MODERATION_REPORT_NOT_FOUND, show_alert=True)
        return
    await crm_service.set_blocked(session, customer, want_block)
    await audit_log_service.log(
        session,
        AuditEventType.CUSTOMER_BLOCK_CHANGED,
        shop_bot_id=shop_bot.id,
        actor_telegram_id=callback.from_user.id,
        details=f"customer={customer.id} blocked={want_block} report={report.id} (نگهبانِ محتوا)",
    )
    await session.commit()
    text, markup = await _card(report, customer, shop_bot)
    await safe_edit(callback, text, markup)
    await callback.answer(texts.MODERATION_BLOCK_RESULT[want_block])


@router.callback_query(F.data.startswith("mod_done:"))
async def cb_report_done(callback: CallbackQuery, session: AsyncSession) -> None:
    """✅ بررسی شد ⇒ گزارش از فهرستِ «باز» می‌رود؛ پیامِ مشتری و ردیفِ ممیزی پاک نمی‌شوند."""
    is_admin = await _is_platform_admin(session, callback.from_user.id)
    shop_bot = None
    if not is_admin:
        shop_bot = await require_shop_bot_cb(callback, session)
        if shop_bot is None:
            return
    report = await moderation_service.get_report(session, parse_suffix_int(callback.data, "mod_done:"))
    if report is None or (shop_bot is not None and report.shop_bot_id != shop_bot.id):
        await callback.answer(texts.MODERATION_REPORT_NOT_FOUND, show_alert=True)
        return
    if not report.reviewed:
        await moderation_service.mark_reviewed(session, report)
        await audit_log_service.log(
            session,
            AuditEventType.MODERATION_REVIEWED,
            shop_bot_id=report.shop_bot_id,
            actor_telegram_id=callback.from_user.id,
            details=f"report={report.id} action={report.action} scope={report.scope}",
        )
        await session.commit()
    await callback.answer(texts.MODERATION_REPORT_REVIEWED)
    text, markup = await _screen(session, None if is_admin else [shop_bot.id], 0)
    await safe_edit(callback, text, markup)


# ============================================================================= ۲) دیدبانِ ادمین (موردِ ۳۰)
@router.callback_query(F.data.startswith("mod_admin_list:"))
async def cb_admin_list(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_platform_admin(session, callback.from_user.id):
        await callback.answer(texts.ADMIN_ONLY_COMMAND, show_alert=True)
        return
    await callback.answer()
    text, markup = await _screen(session, None, _page_of(callback.data))
    await safe_edit(callback, text, markup)


@router.callback_query(F.data.startswith("mod_admin_open:"))
async def cb_admin_open(callback: CallbackQuery, session: AsyncSession) -> None:
    if not await _is_platform_admin(session, callback.from_user.id):
        await callback.answer(texts.ADMIN_ONLY_COMMAND, show_alert=True)
        return
    report = await moderation_service.get_report(session, parse_suffix_int(callback.data, "mod_admin_open:"))
    if report is None:
        await callback.answer(texts.MODERATION_REPORT_NOT_FOUND, show_alert=True)
        return
    shop_bot = await session.get(ShopBot, report.shop_bot_id)
    shop_line = (
        f"🏪 گزارشِ فروشگاهِ «{shop_bot.bot_username or shop_bot.id}»" if shop_bot else "🏪 گزارشِ یکِ فروشگاهِ حذف‌شده"
    )
    await callback.answer()
    text, markup = await _card(
        report, await _customer(session, report), shop_bot, shop_line=shop_line, back="mod_admin_list:0", with_links=False
    )
    await safe_edit(callback, text, markup)
