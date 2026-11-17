"""
کمک‌کننده‌هایِ مشترکِ هندلرهایِ پنلِ فروشگاه‌دار در فازِ ۴ (سوال‌هایِ بی‌جواب، CRM، دستیار،
حسابداری). عمداً از campaigns.py کپی نشده (اون فایلِ تست‌شده دست‌نخورده می‌مونه)؛ رفتارِ
همه‌شون دقیقاً همونه.
"""
from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bots.main_bot import texts
from app.database.models import ShopBot, TenantMode
from app.services import shop_bot_service, shop_owner_service


def sales_mode(shop_bot: ShopBot) -> bool:
    """یکِ منبع برایِ «آیا این فروشگاه کاتالوگ/سبد/سفارش دارد؟» (پ۵۸ · موردِ ۲۴)."""
    return shop_bot.tenant_mode == TenantMode.SALES


async def require_sales_mode(message: Message, shop_bot: ShopBot) -> bool:
    """دروازهٔ ورودیِ صفحه‌هایِ فروشگاهی برایِ مودِ مشاوره‌ای؛ True ⇒ ادامه بده.

    دکمه‌ها از منویِ مشاوره‌ای حذف شده‌اند، ولی کیبوردِ قدیمیِ تلگرام تا یکِ منویِ تازه عوض
    نشود آن‌ها را نگه می‌دارد و متنِ دکمه را می‌شود تایپ هم کرد — پس دروازه باید همین‌جا باشد،
    نه فقط در کیبورد.
    """
    if sales_mode(shop_bot):
        return True
    await message.answer(texts.MODE_SALES_ONLY)
    return False


async def require_sales_mode_cb(callback: CallbackQuery, shop_bot: ShopBot) -> bool:
    if sales_mode(shop_bot):
        return True
    await callback.answer(texts.MODE_SALES_ONLY, show_alert=True)
    return False


async def require_consultation_mode(message: Message, shop_bot: ShopBot) -> bool:
    """دروازهٔ معکوسِ صفحه‌هایِ پ۶۶ (گزارشِ جلسات و بازگشتِ مخاطب): True ⇒ ادامه بده.

    این دو صفحه در منویِ *فقطِ مشاوره‌ای* می‌آیند، ولی کیبوردِ inlineِ کهنه رویِ پیام‌هایِ قبلی
    می‌ماند و `callback_data` را می‌شود دست‌کاری کرد ⇒ دروازه لازم است (همان دلیلی که پ۵۸ برایِ
    سمتِ فروشگاهی نوشت). پیامش هم عمداً جداست: «به «💬 گفتگوها و کاربران» برو» نه «فقط فروشگاهی».
    """
    if not sales_mode(shop_bot):
        return True
    await message.answer(texts.MODE_CONSULTATION_ONLY)
    return False


async def require_consultation_mode_cb(callback: CallbackQuery, shop_bot: ShopBot) -> bool:
    if not sales_mode(shop_bot):
        return True
    await callback.answer(texts.MODE_CONSULTATION_ONLY, show_alert=True)
    return False


async def require_shop_bot(message: Message, session: AsyncSession) -> ShopBot | None:
    owner = await shop_owner_service.get_by_telegram_id(session, message.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await message.answer(texts.SHOP_BOT_NOT_SET_UP)
        return None
    return shop_bot


async def require_shop_bot_cb(callback: CallbackQuery, session: AsyncSession) -> ShopBot | None:
    owner = await shop_owner_service.get_by_telegram_id(session, callback.from_user.id)
    shop_bot = await shop_bot_service.get_by_owner(session, owner) if owner else None
    if shop_bot is None:
        await callback.answer(texts.SHOP_BOT_NOT_SET_UP, show_alert=True)
        return None
    return shop_bot


async def safe_edit(callback: CallbackQuery, text: str, reply_markup=None) -> None:
    """edit_text ـی که «message is not modified» (دابل‌تپ) رو بی‌صدا نادیده می‌گیره."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def panel_keyboard(session: AsyncSession, tenant_mode=None) -> ReplyKeyboardMarkup:
    """منویِ پنلِ فروشگاه‌دار، با سوئیچ‌هایِ ادمین که دکمه کم/زیاد می‌کنند (P42 · موردِ ۳۵، P49-الف).

    هشت نقطه در کد «بازگشت به پنل» می‌سازند؛ اگر عددِ سوئیچ از یکِ منبع نیاید، در بعضی
    صفحه‌ها دکمه‌ها می‌مانند و در بعضی می‌روند — همان ناهماهنگی که مالکِ محصول گزارش کرد.
    """
    from app.bots.main_bot import keyboards
    from app.services import web_panel_service
    from app.services.admin_settings_service import get_admin_settings

    admin_settings = await get_admin_settings(session)
    return keyboards.shop_owner_panel_keyboard(
        tenant_mode,
        knowledge_gap=admin_settings.knowledge_gap_enabled,
        # P49-الف: دکمهٔ «🟣 اینستاگرام» فقط با رونماییِ سراسریِ ادمین در می‌آید (از اتصالِ خودِ
        # فروشگاه مستقل است، تا فروشگاه‌دار بتواند راهنما/اتصال را همین‌جا پیدا کند).
        instagram=bool(admin_settings.instagram_enabled),
        # پ۱۱۴: دو شرطِ مستقل — سوئیچِ سراسریِ ادمین و تنظیم‌شدنِ رازِ پنجرهٔ وب. تا هیچ‌کدام
        # برقرار نباشد دکمه از پنل می‌رود (نه پیامِ «خاموش است» بعد ازِ زدنِ دکمه).
        web_panel=bool(admin_settings.web_panel_enabled) and web_panel_service.enabled(),
    )


def parse_suffix_int(data: str | None, prefix: str) -> int | None:
    """عددِ بعد از پیشوندِ callback_data (مثلاً «gap_answer:12» با پیشوندِ «gap_answer:» → ۱۲).
    callback_data قابلِ دستکاریه؛ هر چیزِ غیرِ عددی/منفی → None."""
    if not data or not data.startswith(prefix):
        return None
    raw = data[len(prefix) :]
    return int(raw) if raw.isdecimal() else None  # isdecimal: «²/①» نه (int() می‌ترکه)
