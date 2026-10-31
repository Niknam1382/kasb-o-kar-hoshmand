"""P18 · A5: تنظیماتِ per-shop که پیش‌تر سراسریِ ادمین بودند.

`NULL` رویِ هر ستون یعنی «همان پیش‌فرضِ سراسریِ `AdminSettings`» ⇒ فروشگاهی که هیچ چیزی را تغییر نداده
دقیقاً مثلِ قبل رفتار می‌کند و هیچ مهاجرتِ داده‌ای لازم نیست. ادمینِ پلتفرم دیگر این‌ها را از پنلِ خودش
تنظیم نمی‌کند (تصمیم با فروشگاه‌دار است، چون هزینه و تجربه‌یِ کار با خودشِ اوست)، ولی ستون‌هایِ سراسری
به‌عنوانِ پیش‌فرض باقی می‌مانند.
"""
from __future__ import annotations

import dataclasses

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import ShopBot
from app.services.payment_settings_service import normalize_digits


@dataclasses.dataclass(frozen=True)
class IntPref:
    """یک تنظیمِ عددیِ per-shop. `key` ستونِ رویِ ShopBot و `admin_key` ستونِ پیش‌فرضِ سراسری است."""

    key: str
    admin_key: str
    presets: tuple[int, ...]
    low: int
    high: int
    zero_disables: bool
    consultation: bool  # در پنلِ مشاوره هم معنا دارد؟


PAYMENT_RESERVATION = IntPref(
    key="payment_reservation_minutes",
    admin_key="payment_reservation_minutes",
    presets=(15, 30, 60, 120),
    low=5,
    high=10080,
    zero_disables=False,
    consultation=False,
)
ORDER_RESERVATION = IntPref(
    key="order_reservation_minutes",
    admin_key="order_reservation_minutes",
    presets=(15, 30, 60, 120),
    low=1,
    high=10080,
    zero_disables=False,
    consultation=False,
)
CONFIRMATION_TIMEOUT = IntPref(
    key="order_confirmation_timeout_minutes",
    admin_key="order_customer_confirmation_timeout_minutes",
    presets=(30, 60, 180, 720),
    low=5,
    high=10080,
    zero_disables=False,
    consultation=False,
)
CONVERSATION_RETENTION = IntPref(
    key="conversation_retention_days",
    admin_key="conversation_retention_days",
    presets=(30, 90, 180, 365),
    low=0,
    high=3650,
    zero_disables=True,
    consultation=True,
)
KNOWLEDGE_ITEMS = IntPref(
    key="knowledge_items_limit",
    admin_key="knowledge_items_limit",
    presets=(5, 10, 15, 30),
    low=1,
    high=100,
    zero_disables=False,
    consultation=True,
)

ALL_PREFS: tuple[IntPref, ...] = (
    PAYMENT_RESERVATION,
    ORDER_RESERVATION,
    CONFIRMATION_TIMEOUT,
    CONVERSATION_RETENTION,
    KNOWLEDGE_ITEMS,
)
BY_KEY: dict[str, IntPref] = {pref.key: pref for pref in ALL_PREFS}
# این چهارتایی که پیش‌تر از پنلِ ادمین تنظیم می‌شدند و دیگر نباید دکمه‌ای آنجا داشته باشند (A5 + بازه‌هایِ W5).
REMOVED_FROM_ADMIN: frozenset[str] = frozenset(
    {pref.admin_key for pref in ALL_PREFS}
    | {
        "payment_deadline_min_minutes",
        "payment_deadline_max_minutes",
        "review_hold_min_hours",
        "review_hold_max_hours",
    }
)


def prefs_for(consultation: bool) -> tuple[IntPref, ...]:
    """تنظیم‌هایِ معنادار برایِ همان مود: در مشاوره سفارش/پرداختی نیست، پس مهلت‌هایشان هم معنا ندارد."""
    return tuple(pref for pref in ALL_PREFS if pref.consultation or not consultation)


def resolve(pref: IntPref, shop_bot: ShopBot | None, admin_settings) -> int:
    """مقدارِ مؤثر: per-shop اگر تنظیم شده، وگرنه پیش‌فرضِ سراسری. همیشه داخلِ بازه‌یِ ایمنی clamp می‌شود."""
    value = getattr(shop_bot, pref.key, None) if shop_bot is not None else None
    if value is None:
        value = getattr(admin_settings, pref.admin_key, None) if admin_settings is not None else None
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = pref.low
    return max(pref.low, min(pref.high, value))


async def resolve_for_shop(session: AsyncSession, pref: IntPref, shop_bot_id: int | None, admin_settings) -> int:
    """وقتی فقط شناسه‌یِ فروشگاه در دست است (`session.get` از identity map می‌خواند، پس کوئریِ اضافه نمی‌زند)."""
    shop_bot = await session.get(ShopBot, shop_bot_id) if shop_bot_id is not None else None
    return resolve(pref, shop_bot, admin_settings)


async def retention_by_shop(session: AsyncSession, admin_settings) -> dict[int, int]:
    """{shop_bot_id: روزِ نگهداریِ مکالمه} برایِ *همه‌یِ* فروشگاه‌ها — جابِ پاکسازی به آن نیاز دارد."""
    default = resolve(CONVERSATION_RETENTION, None, admin_settings)
    rows = await session.execute(select(ShopBot.id, ShopBot.conversation_retention_days))
    return {shop_bot_id: default if days is None else max(0, min(CONVERSATION_RETENTION.high, int(days))) for shop_bot_id, days in rows.all()}


async def confirmation_timeout_by_shop(session: AsyncSession, admin_settings) -> dict[int, int]:
    """{shop_bot_id: دقیقه‌یِ مهلتِ تاییدِ مشتری} برایِ جابِ انقضایِ سفارش."""
    default = resolve(CONFIRMATION_TIMEOUT, None, admin_settings)
    rows = await session.execute(select(ShopBot.id, ShopBot.order_confirmation_timeout_minutes))
    return {
        shop_bot_id: default if minutes is None else max(CONFIRMATION_TIMEOUT.low, min(CONFIRMATION_TIMEOUT.high, int(minutes)))
        for shop_bot_id, minutes in rows.all()
    }


def parse_value(pref: IntPref, raw) -> int | None:
    """ورودیِ آزادِ فروشگاه‌دار (ارقامِ فارسی هم) → عددِ داخلِ بازه؛ نامعتبر ⇒ None."""
    text = normalize_digits(str(raw or "").strip())
    if not text.isascii() or not text.isdecimal() or len(text) > 6:
        return None
    value = int(text)
    return value if pref.low <= value <= pref.high else None


async def set_value(session: AsyncSession, shop_bot: ShopBot, pref: IntPref, value: int | None) -> None:
    """value=None ⇒ بازگشت به پیش‌فرضِ سراسری. خارجِ بازه ⇒ ValueError (هیچ نیمه‌نوشتنی رخ نمی‌دهد)."""
    if value is not None and not (pref.low <= int(value) <= pref.high):
        raise ValueError(f"{pref.key}_out_of_range")
    setattr(shop_bot, pref.key, None if value is None else int(value))
    await session.flush()
