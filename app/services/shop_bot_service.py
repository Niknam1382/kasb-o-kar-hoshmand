from __future__ import annotations

import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopBot, ShopOwner, TenantMode
from app.utils.encryption import encrypt_token


async def get_by_owner(session: AsyncSession, owner: ShopOwner | None) -> ShopBot | None:
    if owner is None:
        return None
    result = await session.execute(select(ShopBot).where(ShopBot.shop_owner_id == owner.id))
    return result.scalar_one_or_none()


async def get_by_id(session: AsyncSession, shop_bot_id: int) -> ShopBot | None:
    return await session.get(ShopBot, shop_bot_id)


async def get_by_bot_telegram_id(session: AsyncSession, bot_telegram_id: int) -> ShopBot | None:
    result = await session.execute(select(ShopBot).where(ShopBot.bot_telegram_id == bot_telegram_id))
    return result.scalar_one_or_none()


async def get_all_active(session: AsyncSession) -> list[ShopBot]:
    result = await session.execute(select(ShopBot).where(ShopBot.is_active.is_(True)))
    return list(result.scalars().all())


async def upsert_shop_bot(
    session: AsyncSession, owner: ShopOwner, raw_token: str, bot_telegram_id: int, bot_username: str
) -> ShopBot:
    shop_bot = await get_by_owner(session, owner)
    encrypted = encrypt_token(raw_token)
    if shop_bot is None:
        shop_bot = ShopBot(
            shop_owner_id=owner.id,
            encrypted_token=encrypted,
            bot_telegram_id=bot_telegram_id,
            bot_username=bot_username,
            webhook_secret_token=secrets.token_urlsafe(32),
            # A3: مودِ رباتِ تازه از مودِ فروشگاه‌دار (انتخابِ ثبت‌نام/پروفایل) میاد، نه پیش‌فرضِ ثابت
            tenant_mode=TenantMode.CONSULTATION if getattr(owner, "business_mode", None) == "consultation" else TenantMode.SALES,
        )
        session.add(shop_bot)
    else:
        shop_bot.encrypted_token = encrypted
        shop_bot.bot_telegram_id = bot_telegram_id
        shop_bot.bot_username = bot_username
        shop_bot.is_active = True
        shop_bot.disabled_reason = None
    await session.flush()
    return shop_bot


# =============================================================================
# فازِ ۶-الف — مدتِ تجمیعِ پیام‌هایِ مشتری
# =============================================================================
DEFAULT_MESSAGE_BATCH_SECONDS = 8  # E2: ۳ ← ۸ (مشتری‌ها معمولاً چند پیامِ پشتِ‌هم می‌فرستن)
MESSAGE_BATCH_MIN_SECONDS = 2
MESSAGE_BATCH_MAX_SECONDS = 60


def _decimal_digits(raw) -> str | None:
    """ارقامِ فارسی/عربی ← لاتین؛ اگر چیزی جز رقم باشد None.
    `isdecimal` و نه `isdigit`: «²/①» را می‌پذیرد ولی `int()` رویشان ValueError می‌دهد."""
    if raw is None:
        return None
    digits = str(raw).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    return digits if digits.isdecimal() else None


def parse_batch_seconds(raw) -> int | None:
    """ورودیِ فروشگاه‌دار (متن/عدد، ارقامِ فارسی هم) → عددِ صحیحِ ۲..۶۰؛ نامعتبر → None."""
    digits = _decimal_digits(raw)
    if digits is None:
        return None
    value = int(digits)
    if value < MESSAGE_BATCH_MIN_SECONDS or value > MESSAGE_BATCH_MAX_SECONDS:
        return None
    return value


async def set_message_batch_seconds(session: AsyncSession, shop_bot: ShopBot, seconds: int | None) -> None:
    """seconds=None → برگشت به پیش‌فرضِ سیستم. مقدارِ خارج از ۲..۶۰ → ValueError."""
    if seconds is not None and not (MESSAGE_BATCH_MIN_SECONDS <= seconds <= MESSAGE_BATCH_MAX_SECONDS):
        raise ValueError("message_batch_seconds_out_of_range")
    shop_bot.message_batch_seconds = seconds
    await session.flush()


# =============================================================================
# P18 · B5 — زمانِ گزارشِ دوره‌ایِ هر فروشگاه (روزِ هفته + ساعت، به وقتِ تهران)
# =============================================================================
REPORT_HOUR_MIN = 0
REPORT_HOUR_MAX = 23
REPORT_WEEKDAY_MIN = 0
REPORT_WEEKDAY_MAX = 6


def parse_report_hour(raw) -> int | None:
    """ورودیِ فروشگاه‌دار → ساعتِ ۰..۲۳ به وقتِ تهران؛ نامعتبر → None."""
    digits = _decimal_digits(raw)
    if digits is None:
        return None
    value = int(digits)
    if value < REPORT_HOUR_MIN or value > REPORT_HOUR_MAX:
        return None
    return value


def valid_report_weekday(value) -> bool:
    return isinstance(value, int) and REPORT_WEEKDAY_MIN <= value <= REPORT_WEEKDAY_MAX


async def set_report_schedule(
    session: AsyncSession, shop_bot: ShopBot, *, weekday: int | None = None, hour: int | None = None, enabled: bool | None = None
) -> None:
    """هر سه پارامتر اختیاری‌اند؛ مقدارِ نامعتبر → ValueError (هیچ نیمه‌نوشتنی اتفاق نمی‌افتد)."""
    if weekday is not None and not valid_report_weekday(weekday):
        raise ValueError("weekly_report_weekday_out_of_range")
    if hour is not None and not (REPORT_HOUR_MIN <= hour <= REPORT_HOUR_MAX):
        raise ValueError("weekly_report_hour_out_of_range")
    if weekday is not None:
        shop_bot.weekly_report_weekday = weekday
    if hour is not None:
        shop_bot.weekly_report_hour = hour
    if enabled is not None:
        shop_bot.weekly_report_enabled = enabled
    await session.flush()


async def get_map_by_owner_ids(session: AsyncSession, owner_ids: list[int]) -> dict[int, ShopBot | None]:
    """{owner_id: ShopBot | None} با یه کوئری (بدونِ N+1)."""
    result: dict[int, ShopBot | None] = {owner_id: None for owner_id in owner_ids}
    if owner_ids:
        rows = await session.execute(select(ShopBot).where(ShopBot.shop_owner_id.in_(owner_ids)))
        for shop_bot in rows.scalars().all():
            result[shop_bot.shop_owner_id] = shop_bot
    return result
