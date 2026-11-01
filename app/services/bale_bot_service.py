"""P19: رباتِ بله‌یِ *خودِ* هر فروشگاه (رباتِ هوشمند روی بله، با همان حسابداریِ کیف‌پول).

سه چیز را یک‌جا نگه می‌دارد تا «رباتِ بله» در کدهایِ پراکنده گم نشود:

۱) **کلیدِ رونماییِ ادمین** (`AdminSettings.bale_shop_bots_enabled`): تا روشن نشده، نه دکمه‌یِ ثبتِ
   توکن در پنلِ فروشگاه‌دار دیده می‌شود و نه هیچ اتصالِ بله‌ای شروع می‌شود. ویژگی آماده است ولی پنهان.
۲) **ساختِ Botِ بله**: بله با همان طرحِ Telegram Bot API کار می‌کند، پس یک `AiohttpSession` با
   `TelegramAPIServer.from_base(BALE_API_BASE)` کلِ روترِ موجودِ رباتِ فروشگاهی (هوش مصنوعی، سبد،
   چک‌اوت، پرداخت، سفارش) را بدونِ هیچ هندلرِ تازه‌ای روی بله فعال می‌کند — و چون همان هندلرها همان
   کسرِ کیف‌پول را انجام می‌دهن، هزینه‌ها دقیقاً مثلِ تلگرام حساب می‌شود.
۳) **پلتفرمِ هویت**: شناسه‌یِ عددیِ کاربر فقط داخلِ یک سرویسِ پیام‌رسان یکتاست. پس `ShopBot` از
   `bale_bot_id` و `Customer` از `(telegram_id, platform)` خوانده می‌شود؛ وگرنه دو آدمِ غریبه
   (یک تلگرامی و یک بله‌ای با عددِ یکسان) تاریخچه، سبد و بلاکِ مشترک می‌گرفتند.

توکنِ خام هرگز لاگ یا در پیامِ کاربری برگردانده نمی‌شود؛ نمایش فقط ماسک‌شده است.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import ShopBot
from app.services import bale_service

logger = logging.getLogger(__name__)

MAX_TOKEN_LENGTH = 512
MIN_TOKEN_LENGTH = 20


def enabled(admin_settings) -> bool:
    """کلیدِ رونماییِ ادمین (پیش‌فرض false ⇒ ویژگی پنهان است)."""
    return bool(getattr(admin_settings, "bale_shop_bots_enabled", False))


async def visible_for(session: AsyncSession) -> bool:
    """همان کلید، فقط از دیتابیس — تا پنلِ فروشگاه‌دار بداند دکمه را نشان دهد یا نه."""
    from app.services.admin_settings_service import get_admin_settings  # import محلی: چرخه‌یِ import نشود

    return enabled(await get_admin_settings(session))


def valid_token_input(raw: str | None) -> bool:
    """فرمتِ توکن: بدونِ فاصله/خطِ جدید و با طولِ معقول. مقدارِ خام هرگز لاگ نمی‌شود."""
    text = (raw or "").strip()
    return MIN_TOKEN_LENGTH <= len(text) <= MAX_TOKEN_LENGTH and not any(ch.isspace() for ch in text)


def build_bot(raw_token: str) -> Bot:
    """یه Botِ aiogram که درخواست‌هاش به سرویسِ بله می‌ره (نه api.telegram.org).

    پرچمِ `bale_platform` روی خودِ شیء نشسته چون تشخیصِ پلتفرم نباید به رشته‌یِ آدرسِ داخلیِ
    aiogram یا به مقدارِ BALE_API_BASE در `.env` وابسته باشد.
    """
    session = AiohttpSession(api=TelegramAPIServer.from_base(settings.bale_api_base))
    bot = Bot(token=raw_token.strip(), session=session)
    bot.bale_platform = True
    return bot


async def fetch_identity(raw_token: str) -> dict:
    """getMe روی بله. استثنا نمی‌خورد: `bale_service.BaleError` را به caller می‌دهیم تا پیامِ درست بدهد."""
    result = await bale_service.get_me(raw_token.strip())
    if not isinstance(result, dict) or not isinstance(result.get("id"), int):
        raise bale_service.BaleError("پاسخِ getMe بله ناشناخته بود.")
    return result


async def get_by_bale_bot_id(session: AsyncSession, bale_bot_id: int) -> ShopBot | None:
    result = await session.execute(select(ShopBot).where(ShopBot.bale_bot_id == bale_bot_id))
    return result.scalar_one_or_none()


async def apply_token(session: AsyncSession, shop_bot: ShopBot, raw_token: str, identity: dict) -> None:
    """توکن (رمزنگاری‌شده توسط TypeDecorator) + شناسه و نامِ کاربریِ رباتِ بله."""
    shop_bot.bale_encrypted_token = raw_token.strip()
    shop_bot.bale_bot_id = int(identity["id"])
    shop_bot.bale_bot_username = (identity.get("username") or "")[:64] or None
    shop_bot.bale_bot_enabled = True
    await session.flush()


async def clear_token(session: AsyncSession, shop_bot: ShopBot) -> None:
    shop_bot.bale_encrypted_token = None
    shop_bot.bale_bot_id = None
    shop_bot.bale_bot_username = None
    shop_bot.bale_bot_enabled = True
    await session.flush()


def raw_token(shop_bot: ShopBot | None) -> str:
    """توکنِ خامِ بله‌یِ این فروشگاه (فقط برایِ ساختنِ اتصال؛ هرگز به کاربر نشان داده نمی‌شود)."""
    return (shop_bot.bale_encrypted_token if shop_bot is not None else None) or ""


def token_masked(shop_bot: ShopBot | None) -> str:
    token = raw_token(shop_bot)
    if not token:
        return "تنظیم‌نشده"
    tail = token[-4:] if len(token) > 4 else ""
    return f"●●●●{tail}"


def connectable(shop_bot: ShopBot | None) -> bool:
    """هم توکن داشته باشد هم سوییچِ خودِ فروشگاه روشن باشد."""
    return bool(shop_bot is not None and raw_token(shop_bot) and shop_bot.bale_bot_enabled)
