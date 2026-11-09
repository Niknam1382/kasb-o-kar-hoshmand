"""P43 · مواردِ ۳۰/۳۱/۱۰ — کارتِ گزارشِ نگهبانِ محتوا.

سه چیز را یک‌جا درست می‌کند:
۱) هر برخورد با قانون، یکِ ردیفِ `moderation_reports` می‌شود (پیش ازِ این فقط ممیزی بود).
۲) کارتِ گزارش برایِ صاحبِ کسب‌وکار (و برایِ ادمین اگر قانونِ سراسری بوده) **دکمه** دارد:
   گفتگو، مشخصاتِ کاربر، بلاکِ واقعی، و بستنِ گزارش (موردِ ۱۰).
۳) مسیرِ نوشتن و مسیرِ شبکه از هم جداست: اول ردیف‌ها commit می‌شوند (قاعدهٔ ۷)، بعد پیام می‌رود؛
   اگر تلگرام لحظه‌ای قطع باشد، گزارش از دست نمی‌رود و در فهرستِ «باز» می‌ماند.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import keyboards, texts as main_texts
from app.bots.shop_bot import texts as shop_texts
from app.config import settings
from app.database.models import Customer, ModerationReport, ShopBot, ShopOwner
from app.services import crm_service

logger = logging.getLogger(__name__)

ACTION_WARN = "warn"
ACTION_BLOCK = "block"
ACTION_REVIEW = "review"


def _customer_label(customer: Customer | None) -> str:
    if customer is None:
        return "مشتریِ حذف‌شده"
    return main_texts.crm_customer_label(customer)


async def send_report_cards(
    main_bot: Bot,
    session: AsyncSession,
    *,
    shop_bot: ShopBot,
    owner: ShopOwner | None,
    customer: Customer | None,
    report: ModerationReport,
    to_admins: bool,
) -> None:
    """کارتِ گزارش ⇒ صاحبِ کسب‌وکار، و اگر `to_admins` باشد ⇒ ادمین‌هایِ پلتفرم.

    قانونِ مسیر (موردِ ۳۰): گزارشِ قانونِ *خودِ فروشگاه* فقط به همان صاحبِ کسب‌وکار می‌رود؛
    گزارشِ قانونِ *سراسری* به او و به ادمین می‌رود، و کارتِ ادمین خطِ «فروشگاه/مالک» دارد تا
    بداند این گزارش از کدام کسب‌وکار آمده است.
    """
    label = _customer_label(customer)
    chat_cb, profile_cb = _deep_links(shop_bot, report.customer_id)
    if owner is not None:
        card = main_texts.moderation_report_card(report, label)
        markup = keyboards.moderation_report_keyboard(report.id, blocked=bool(customer and customer.is_blocked), chat_cb=chat_cb, profile_cb=profile_cb)
        try:
            await main_bot.send_message(owner.telegram_id, card, reply_markup=markup)
        except TelegramAPIError:
            logger.exception("کارتِ گزارشِ نگهبانِ محتوا به فروشگاه‌دار %s نرفت (گزارش %s در فهرستِ باز می‌ماند).", owner.telegram_id, report.id)
    if to_admins:
        shop_line = f"🏪 فروشگاه: {shop_bot.bot_username or shop_bot.id} · مالک: {(owner.first_name or owner.username) if owner else '—'}"
        admin_card = main_texts.moderation_report_card(report, label, shop_line=shop_line)
        # کارتِ ادمین عمداً دکمهٔ گفتگو/مشخصات ندارد: دیدنِ چتِ مشتریِ یکِ فروشگاه برایِ ادمین
        # صفحهٔ تازه + ممیزی می‌خواهد و در صفِ بعد نشسته است.
        admin_markup = keyboards.moderation_report_keyboard(
            report.id, blocked=bool(customer and customer.is_blocked), chat_cb=None, profile_cb=None, back_cb="mod_admin_list:0"
        )
        for admin_id in settings.admin_ids:
            try:
                await main_bot.send_message(admin_id, admin_card, reply_markup=admin_markup)
            except TelegramAPIError:
                logger.exception("کارتِ گزارشِ نگهبانِ محتوا به ادمین %s نرفت (گزارش %s).", admin_id, report.id)


async def reply_to_customer(shop_bot_instance: Bot, customer_tg_id: int, action: str) -> None:
    """پاسخِ دیدنیِ مشتری بسته به اکشن — «هشدار» چیزی به مشتری نمی‌گوید (موردِ ۳۱)."""
    if action == ACTION_WARN:
        return
    try:
        await shop_bot_instance.send_message(customer_tg_id, shop_texts.MODERATION_BLOCKED_REPLY)
    except TelegramAPIError:
        logger.exception("پیامِ نگهبانِ محتوا به مشتری %s نرفت.", customer_tg_id)


def _deep_links(shop_bot: ShopBot, customer_id: int | None) -> tuple[str | None, str | None]:
    """همان صفحه‌هایی که فروشگاه‌دار از «👥 مشتری‌ها» / «💬 گفتگوها و کاربران» می‌بیند — بدونِ
    ساختنِ یکِ راهِ دوم برایِ دیدنِ گفتگو."""
    from app.database.models import TenantMode

    if customer_id is None:
        return None, None
    if shop_bot.tenant_mode == TenantMode.CONSULTATION:
        return f"cc_card:{customer_id}:0", f"cc_card:{customer_id}:0"
    return f"crm_conv:{customer_id}:0", f"crm_card:{customer_id}"


async def block_customer(session: AsyncSession, customer: Customer) -> None:
    """موردِ ۳۱: «مسدود» باید واقعاً مسدود کند — همان ستون و همان میدل‌وری که «👥 مشتری‌ها» می‌زند."""
    await crm_service.set_blocked(session, customer, True)
